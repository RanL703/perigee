"""Read-only agent features layered over deterministic API facts."""

import asyncio
import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, TypeVar

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from perigee.config import OllamaConfig

from .guardrails import sanitize_advisory_text
from .schemas import (
    AgentQueryPayload,
    AgentQueryResponse,
    InsightsPayload,
    InsightsResponse,
    RecommendationPayload,
    RecommendationResponse,
)

logger = logging.getLogger(__name__)
PayloadT = TypeVar("PayloadT", bound=BaseModel)

QUERY_PROMPT = """You are Ask Perigee, a read-only analyst assistant.
Use only the dashboard context returned by get_dashboard_context, which contains the
screening stats (stats) and every currently flagged conjunction event (events, pre-sorted
by risk score descending). You can: summarize the whole screening picture, name the most
urgent alert, rank or compare events, filter by risk tier or object type (payload/debris/
rocket body), find the closest pass or highest relative velocity, count events matching a
condition, and describe any single event in the list. Answer the user's question directly
and briefly using those facts. Never invent records, numbers, timestamps, or event IDs;
if the context is insufficient, say exactly that you do not have enough information.
Do not claim collision probability, operational certainty, or recommend maneuvers.
Return only the requested structured response. Referenced IDs must be copied exactly.
"""

DETERMINISTIC_FALLBACK = "I don't have enough information to answer that from the current screening results."

RECOMMENDATION_PROMPT = """You are Perigee's read-only triage advisor.
Use only the event facts returned by get_event_facts. Write one or two sentences for a
human analyst describing a safe review priority. Preserve the deterministic risk tier.
Never give maneuver, avoidance, approval, rejection, or probability advice; never invent
facts. This is public-TLE screening, not an operational collision prediction. Return only
the requested structured response.
"""

INSIGHTS_PROMPT = """You are Perigee's read-only pattern summarizer.
Use only the aggregate event facts returned by get_event_aggregates. Report at most four
descriptive observations grounded in those facts. Do not predict, infer probability, or
recommend maneuvers. If there are no events, return an empty insights list. Copy related
event IDs exactly and return only the requested structured response.
"""


class AgentFeatures:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def _model(self) -> ChatOllama:
        return ChatOllama(
            model=self.config.model,
            base_url=self.config.base_url,
            temperature=0,
            reasoning=False,
            timeout=self.config.timeout_seconds,
        )

    def _run(
        self,
        facts: dict[str, Any],
        prompt: str,
        schema: type[PayloadT],
        tool_name: str,
        *,
        user_message: str | None = None,
    ) -> PayloadT:
        facts_json = json.dumps(facts, default=str, separators=(",", ":"))

        @tool
        def read_context() -> str:
            """Return the explicitly scoped, read-only API context."""
            return facts_json

        agent = create_agent(
            model=self._model(),
            tools=[read_context],
            system_prompt=prompt,
            response_format=schema,
        )
        base_message = user_message or "Use the read-only context now. Return only the requested schema."
        last_error: Exception | None = None
        for instruction in (base_message, "RETRY: the previous response was invalid. Call the context tool, then emit only valid structured output with no extra fields or prose."):
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": instruction}]},
                    config={"recursion_limit": 6},
                )
                payload = result.get("structured_response")
                if isinstance(payload, schema):
                    return payload
                # Qwen often answers correctly in prose while skipping the
                # provider's structured-output call. Coerce the final message
                # into the schema (JSON first, then single-field prose);
                # anything unusable still fails closed through the retry.
                messages = result.get("messages", [])
                content = next(
                    (
                        getattr(message, "content", "")
                        for message in reversed(messages)
                        if getattr(message, "content", "")
                    ),
                    "",
                )
                coerced = self._coerce_payload(content, schema)
                if coerced is not None:
                    return coerced
                last_error = TypeError("Agent did not return validated structured output")
            except Exception as exc:  # noqa: BLE001 - retry once, then fail closed
                last_error = exc
        raise TypeError("Agent did not return validated structured output") from last_error

    @staticmethod
    def _coerce_payload(content: str, schema: type[PayloadT]) -> PayloadT | None:
        text = content.strip()
        candidates: list[str] = []
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            candidates.append(json_match.group(0))
        candidates.append(text)
        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except ValueError:
                continue
            if isinstance(data, dict):
                try:
                    return schema.model_validate(data)
                except ValueError:
                    continue
        # Schemas with exactly one required string field (query answers,
        # recommendations) accept grounded prose directly; guardrail
        # sanitisation still applies afterwards.
        string_fields = [
            name for name, field in schema.model_fields.items() if field.annotation is str
        ]
        if len(string_fields) == 1 and len(schema.model_fields) == 1 and text:
            try:
                return schema.model_validate({string_fields[0]: text})
            except ValueError:
                return None
        return None

    @staticmethod
    def _validate_text(text: str, *, allow_empty: bool = False) -> str:
        if not allow_empty and not text.strip():
            raise ValueError("Agent text field is empty")
        # Strip guarded sentences (probability figures, maneuver directives)
        # instead of discarding the entire grounded answer; fail closed only
        # when nothing advisory-safe remains.
        return sanitize_advisory_text(text)

    @staticmethod
    def _validate_ids(ids: list[str]) -> list[str]:
        if len(ids) > 10 or any(not re.fullmatch(r"[0-9a-fA-F-]{36}", value) for value in ids):
            raise ValueError("Agent returned an invalid event ID")
        return ids

    async def query(self, question: str, context: dict[str, Any]) -> AgentQueryResponse:
        if not self.config.enabled:
            return self._deterministic_query(question, context, provider_error=None)
        try:
            payload = await asyncio.wait_for(asyncio.to_thread(self._run, {"question": question, **context}, QUERY_PROMPT, AgentQueryPayload, "get_dashboard_context", user_message=f"Analyst question: {question}\nUse the read-only context tool, then answer it from that data only."), self.config.timeout_seconds + 5)
            answer = self._validate_text(payload.answer)
            referenced = self._validate_ids(payload.referenced_event_ids)
            return AgentQueryResponse(answer=answer, referenced_event_ids=referenced, source="ollama", model=self.config.model)
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Ask Perigee unavailable: %s", exc)
            return self._deterministic_query(question, context, provider_error=str(exc))

    @staticmethod
    def _deterministic_query(question: str, context: dict[str, Any], *, provider_error: str | None) -> AgentQueryResponse:
        """Grounded template answer built from the same read-only context.

        Keeps Ask Perigee useful when Ollama is disabled or fails: the answer
        is composed deterministically from the exact facts the agent would
        have received — never invented.
        """
        events = context.get("events") or []
        stats = context.get("stats") or {}
        if not events:
            return AgentQueryResponse(answer=DETERMINISTIC_FALLBACK, source="template", model=AgentFeatures._model_name(context), provider_error=provider_error)

        lowered = question.lower()
        top = max(events, key=lambda event: (float(event["risk_score"]), -event["tca"].timestamp() if hasattr(event["tca"], "timestamp") else 0))

        def label(event: dict[str, Any]) -> str:
            return f"{event['object_a_name']} × {event['object_b_name']}"

        if any(term in lowered for term in ("debris", "payload", "rocket")):
            kind = next((term for term in ("debris", "payload", "rocket") if term in lowered), "debris")
            matches = [
                event
                for event in events
                if kind in (str(event.get("object_a_type", "")), str(event.get("object_b_type", "")))
                or kind in label(event).lower()
            ]
            if matches:
                listed = "; ".join(f"{label(event)} ({event['risk_tier']}, score {float(event['risk_score']):.0f})" for event in matches[:3])
                answer = f"{len(matches)} of {len(events)} flagged events involve {kind}: {listed}."
            else:
                answer = f"No flagged events currently involve {kind}; all {len(events)} tracked close approaches are between other object types."
        elif any(term in lowered for term in ("urgent", "priority", "worst", "most")) or "summar" in lowered or "picture" in lowered or "overview" in lowered:
            tiers = Counter(str(event["risk_tier"]) for event in events)
            tracked = stats.get("objects_tracked")
            scope = f" across {tracked} tracked objects" if tracked else ""
            fastest = max(events, key=lambda event: float(event["relative_velocity_kmps"]))
            closest = min(events, key=lambda event: float(event["miss_distance_km"]))
            answer = (
                f"The current screen flags {len(events)} close approaches{scope}: "
                f"{tiers.get('critical', 0)} critical, {tiers.get('elevated', 0)} elevated, {tiers.get('low', 0)} low. "
                f"Highest priority is {label(top)} at score {float(top['risk_score']):.0f} ({top['risk_tier']}); "
                f"the closest pass is {closest['miss_distance_km']} km and the fastest is {fastest['relative_velocity_kmps']} km/s."
            )
        else:
            answer = (
                f"{label(top)} is the highest-priority flagged event at score {float(top['risk_score']):.0f} ({top['risk_tier']}). "
                f"{len(events)} events are flagged in total; ask for a summary, a tier filter, or a specific pair for details."
            )
        return AgentQueryResponse(answer=answer, referenced_event_ids=[str(top["id"])], source="template", model=AgentFeatures._model_name(context), provider_error=provider_error)

    @staticmethod
    def _model_name(context: dict[str, Any]) -> str:
        model = context.get("model")
        return str(model) if model else OllamaConfig().model

    async def recommendation(self, facts: dict[str, Any], screened_at: datetime) -> RecommendationResponse:
        if not self.config.enabled:
            return RecommendationResponse(recommendation="Review the latest tracking data and compare the next screening cycle before deciding on priority.", source="template", model=self.config.model, screened_at=screened_at.isoformat())
        try:
            payload = await asyncio.wait_for(asyncio.to_thread(self._run, facts, RECOMMENDATION_PROMPT, RecommendationPayload, "get_event_facts"), self.config.timeout_seconds + 5)
            text = payload.recommendation.lower()
            self._validate_text(text)
            return RecommendationResponse(**payload.model_dump(), source="ollama", model=self.config.model, screened_at=screened_at.isoformat())
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Event recommendation unavailable: %s", exc)
            return RecommendationResponse(recommendation="Review TLE freshness and tracking coverage, then compare the next screening cycle before deciding on priority.", source="template", model=self.config.model, screened_at=screened_at.isoformat(), provider_error=str(exc))

    async def insights(self, context: dict[str, Any]) -> InsightsResponse:
        if not context.get("events"):
            return InsightsResponse(insights=[], source="template", model=self.config.model)
        if not self.config.enabled:
            return InsightsResponse(insights=[], source="template", model=self.config.model, provider_error="Ollama is disabled")
        try:
            payload = await asyncio.wait_for(asyncio.to_thread(self._run, context, INSIGHTS_PROMPT, InsightsPayload, "get_event_aggregates"), self.config.timeout_seconds + 5)
            for insight in payload.insights:
                self._validate_text(insight.observation)
                self._validate_ids(insight.related_event_ids)
            return InsightsResponse(**payload.model_dump(), source="ollama", model=self.config.model)
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Event insights unavailable: %s", exc)
            return InsightsResponse(insights=[], source="template", model=self.config.model, provider_error=str(exc))

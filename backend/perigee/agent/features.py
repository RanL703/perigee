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

QUERY_PROMPT = """You are Ask Perigee, a read-only analyst assistant for satellite conjunction screening.
Tools:
- get_dashboard_context: screening stats, the conversation so far, and every currently
  flagged conjunction event (pre-sorted by risk score descending).
- search_catalog: look up ANY tracked object by name substring — flagged or not — for its
  NORAD ID and type. Use it whenever the question mentions an object that is not in the
  flagged events.

You can: summarize the whole screening picture; name the most urgent alert; rank, compare,
or filter events by risk tier or object type (payload/debris/rocket body); describe any
flagged event; report whether a specific object is or is not involved in any flagged event;
and discuss what measures an analyst could take next — monitoring, verification, review
priorities, and what information would be worth gathering. Stay on the topic of orbital
screening and space safety.

Ground every fact in tool output; never invent records, numbers, timestamps, or event IDs;
if the tools are insufficient, say exactly that you do not have enough information.
Advisory boundary: never state a numeric collision-probability figure and never direct
anyone to execute a maneuver or command; describing options for human review is fine.
Never announce which tools you called, never ask clarifying questions, and never request
more information from the user — after the tool call(s), immediately emit the structured
response that answers the analyst's question.
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

    def _model(self, num_predict: int | None = None) -> ChatOllama:
        return ChatOllama(
            model=self.config.model,
            base_url=self.config.base_url,
            temperature=0,
            reasoning=False,
            num_predict=num_predict,
            # Keep weights resident between demo questions; a cold reload was
            # causing the first query of a session to time out and fall back.
            keep_alive="30m",
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
        num_predict: int | None = None,
    ) -> PayloadT:
        catalog = facts.get("catalog") or []

        @tool
        def get_dashboard_context() -> str:
            """Return the explicitly scoped, read-only screening context."""
            return json.dumps(
                {key: value for key, value in facts.items() if key != "catalog"},
                default=str,
                separators=(",", ":"),
            )

        tools = [get_dashboard_context]
        if catalog:
            @tool
            def search_catalog(query: str) -> str:
                """Find tracked objects by name substring (any object, flagged or not)."""
                needle = query.lower().strip()
                matches = [
                    {"norad_id": obj["norad_id"], "name": obj["name"], "object_type": str(obj.get("object_type", ""))}
                    for obj in catalog
                    if needle in str(obj.get("name", "")).lower()
                ][:10]
                return json.dumps({"matches": len(matches), "objects": matches})

            tools.append(search_catalog)

        agent = create_agent(
            model=self._model(num_predict),
            tools=tools,
            system_prompt=prompt,
            response_format=schema,
        )
        base_message = (
            user_message
            or "Use the read-only context now, then immediately emit the requested structured response."
        )
        retry_message = f"{base_message}\nRETRY: your previous output was invalid — call the needed tool(s), then emit only valid structured output with no extra fields or prose."
        last_error: Exception | None = None
        for instruction in (base_message, retry_message):
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
        # Schemas whose only REQUIRED field is a single string (query answers
        # with optional referenced IDs, recommendations) accept grounded prose
        # directly; guardrail sanitisation still applies afterwards.
        required_fields = [
            name for name, field in schema.model_fields.items() if field.is_required()
        ]
        if len(required_fields) == 1 and schema.model_fields[required_fields[0]].annotation is str and text:
            try:
                return schema.model_validate({required_fields[0]: text})
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
        history = context.get("history") or []
        history_text = "\n".join(
            f"{'User' if turn.get('role') == 'user' else 'Perigee'}: {turn.get('content', '')}"
            for turn in history[-6:]
        )
        user_message = (
            f"Analyst question: {question}\n"
            + (f"Conversation so far:\n{history_text}\n" if history_text else "")
            + "Call the tools you need, then immediately emit the structured response answering the question above. Do not ask for clarification and do not describe your tools."
        )
        facts = {"question": question, **context}
        if not self.config.enabled:
            return self._deterministic_query(question, facts, provider_error=None)
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(self._run, facts, QUERY_PROMPT, AgentQueryPayload, "get_dashboard_context", user_message=user_message, num_predict=700),
                self.config.timeout_seconds + 5,
            )
            answer = self._validate_text(payload.answer)
            referenced = list(dict.fromkeys(self._validate_ids(payload.referenced_event_ids)))
            return AgentQueryResponse(answer=answer, referenced_event_ids=referenced, source="ollama", model=self.config.model)
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Ask Perigee unavailable: %s", str(exc) or type(exc).__name__)
            return self._deterministic_query(question, facts, provider_error=str(exc) or type(exc).__name__)

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

        # Catalog lookup for objects that may not be part of any flagged event.
        for obj in context.get("catalog") or []:
            name = str(obj.get("name", ""))
            if len(name) > 3 and name.lower() in lowered:
                involved = [event for event in events if name in (str(event["object_a_name"]), str(event["object_b_name"]))]
                kind = str(obj.get("object_type", "")).replace("_", " ")
                if involved:
                    answer = f"{name} ({kind}, NORAD {obj['norad_id']}) appears in {len(involved)} flagged event(s): " + "; ".join(f"{label(event)} ({event['risk_tier']}, score {float(event['risk_score']):.0f})" for event in involved[:3]) + "."
                else:
                    answer = f"{name} ({kind}, NORAD {obj['norad_id']}) is tracked in the catalog but is not involved in any of the {len(events)} currently flagged close approaches."
                return AgentQueryResponse(answer=answer, referenced_event_ids=[str(event["id"]) for event in involved[:1]], source="template", model=AgentFeatures._model_name(context), provider_error=provider_error)

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

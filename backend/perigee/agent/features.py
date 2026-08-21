"""Read-only agent features layered over deterministic API facts."""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, TypeVar

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from perigee.config import OllamaConfig

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
Use only the dashboard context returned by get_dashboard_context. Answer the user's
question directly and briefly. Never invent records, numbers, timestamps, or event IDs;
if the context is insufficient, say exactly that you do not have enough information.
Do not claim collision probability, operational certainty, or recommend maneuvers.
Return only the requested structured response. Referenced IDs must be copied exactly.
"""

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

    def _run(self, facts: dict[str, Any], prompt: str, schema: type[PayloadT], tool_name: str) -> PayloadT:
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
        last_error: Exception | None = None
        for instruction in (
            "Use the read-only context now. Return only the requested schema.",
            "RETRY: the previous response was invalid. Call the context tool, then emit only valid structured output with no extra fields or prose.",
        ):
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": instruction}]},
                    config={"recursion_limit": 5},
                )
                payload = result.get("structured_response")
                if isinstance(payload, schema):
                    return payload
                last_error = TypeError("Agent did not return validated structured output")
            except Exception as exc:  # noqa: BLE001 - retry once, then fail closed
                last_error = exc
        raise TypeError("Agent did not return validated structured output") from last_error

    @staticmethod
    def _validate_text(text: str, *, allow_empty: bool = False) -> str:
        if not allow_empty and not text.strip():
            raise ValueError("Agent text field is empty")
        forbidden = ("maneuver", "avoidance", "probability", "approve", "reject", "execute command")
        if any(term in text.lower() for term in forbidden):
            raise ValueError("Agent output violated advisory guardrails")
        return text

    @staticmethod
    def _validate_ids(ids: list[str]) -> list[str]:
        if len(ids) > 10 or any(not re.fullmatch(r"[0-9a-fA-F-]{36}", value) for value in ids):
            raise ValueError("Agent returned an invalid event ID")
        return ids

    async def query(self, question: str, context: dict[str, Any]) -> AgentQueryResponse:
        if not self.config.enabled:
            return AgentQueryResponse(answer="AI features are disabled; use the dashboard filters to inspect results.", source="template", model=self.config.model)
        try:
            payload = await asyncio.wait_for(asyncio.to_thread(self._run, {"question": question, **context}, QUERY_PROMPT, AgentQueryPayload, "get_dashboard_context"), self.config.timeout_seconds + 5)
            self._validate_text(payload.answer)
            self._validate_ids(payload.referenced_event_ids)
            return AgentQueryResponse(**payload.model_dump(), source="ollama", model=self.config.model)
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Ask Perigee unavailable: %s", exc)
            return AgentQueryResponse(answer="I don't have enough information to answer that from the current screening results.", source="template", model=self.config.model, provider_error=str(exc))

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

"""Bounded LangChain agent backed by a local Ollama model.

The agent is deliberately advisory. Orbital propagation, scoring, and factor
values are computed before this module is called and are never delegated to an
LLM. If Ollama is disabled or unavailable, deterministic copy is returned.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from perigee.config import OllamaConfig
from perigee.narrative.templates import event_summary, factor_caption

from .schemas import AgentExplanationPayload, AgentExplanationResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Perigee's local, read-only conjunction-triage explanation assistant.

Mission: translate the deterministic screening facts returned by get_screening_facts into
a concise explanation a non-specialist analyst can act on. The tool output is the sole
source of truth. Call get_screening_facts exactly once before composing the answer.

Safety and accuracy rules:
1. Never invent, estimate, round, or overwrite a number, name, timestamp, risk tier, or
   factor contribution. If a fact is missing, say so briefly instead of guessing.
2. Explain screening evidence only. Do not call this an operational collision prediction,
   probability, confirmed collision, or conjunction assessment from a tracking authority.
3. Do not recommend, approve, or reject maneuvers. Operator focus may only suggest review
   actions such as validating TLE freshness, checking tracking coverage, or comparing the
   next screening cycle.
4. Preserve the supplied risk tier and connect the explanation to the largest factor
   contributions. Keep the explanation to 2-3 sentences and operator_focus to 1-3 items.
5. Return only the requested structured response; do not emit Markdown, headings, JSON
   fences, tool traces, or additional fields. Use plain language and units from the facts.

Required fields:
- headline: one factual sentence naming both objects and the miss distance.
- explanation: concise evidence-based reason for the supplied tier.
- operator_focus: safe verification/review actions only (never maneuver advice).
- caveat: explicitly note that this uses public TLE screening data and is not operational.
"""


class OllamaAssistant:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def _fallback(self, facts: dict[str, Any], error: str | None = None) -> AgentExplanationResponse:
        factors = facts.get("factor_breakdown", {})
        dominant = max(
            factors,
            key=lambda name: float(factors[name].get("contribution", 0)),
            default="miss_distance",
        )
        dominant_factor = factors.get(dominant, {})
        miss_distance = float(facts["miss_distance_km"])
        tca = facts["tca"]
        if isinstance(tca, str):
            tca = datetime.fromisoformat(tca)
        headline = event_summary(facts["object_a_name"], facts["object_b_name"], miss_distance, tca)
        explanation = factor_caption(
            dominant,
            float(dominant_factor.get("raw_value", miss_distance)),
            float(dominant_factor.get("contribution", 0)),
        )
        return AgentExplanationResponse(
            headline=headline,
            explanation=f"This is ranked {facts['risk_tier']} with a score of {facts['risk_score']:.1f}/100. {explanation}",
            operator_focus=[
                "Review updated tracking data as the closest-approach time nears.",
                "Compare this event with the next screening cycle for trend changes.",
            ],
            caveat="This is a public-TLE screening result, not an operational collision-avoidance prediction.",
            source="template",
            model=self.config.model,
            provider_error=error,
        )

    def _invoke(self, facts: dict[str, Any]) -> AgentExplanationPayload:
        facts_json = json.dumps(facts, default=str, separators=(",", ":"))

        @tool
        def get_screening_facts() -> str:
            """Return the deterministic conjunction facts computed by Perigee."""
            return facts_json

        model = ChatOllama(
            model=self.config.model,
            base_url=self.config.base_url,
            temperature=0,
            # Qwen exposes a thinking mode that is useful for open-ended chat but
            # adds avoidable latency to this bounded, structured explanation call.
            reasoning=False,
            timeout=self.config.timeout_seconds,
        )
        agent = create_agent(
            model=model,
            tools=[get_screening_facts],
            system_prompt=SYSTEM_PROMPT,
            response_format=AgentExplanationPayload,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Explain this conjunction event for an analyst."}]},
            config={"recursion_limit": 6},
        )
        structured = result.get("structured_response")
        if isinstance(structured, AgentExplanationPayload):
            return self._validate_payload(structured)

        # Qwen occasionally follows the schema semantically but emits Markdown
        # headings instead of the provider's structured tool call. Coerce only
        # the four explicit fields; anything incomplete or unsafe still fails
        # closed to the deterministic template fallback.
        messages = result.get("messages", [])
        content = next(
            (getattr(message, "content", "") for message in reversed(messages) if getattr(message, "content", "")),
            "",
        )
        candidate = self._parse_markdown_payload(content)
        if candidate is None:
            raise TypeError("Ollama agent returned no validated structured response")
        return self._validate_payload(candidate)

    @staticmethod
    def _parse_markdown_payload(content: str) -> AgentExplanationPayload | None:
        def section(name: str, next_names: tuple[str, ...] = (), *, collapse: bool = True) -> str:
            stops = "|".join(re.escape(item) for item in next_names)
            pattern = rf"(?is)(?:^|\n)\s*\**{re.escape(name)}\**\s*:\s*(.*?)(?=\n\s*\**(?:{stops})\**\s*:|\Z)"
            match = re.search(pattern, content)
            if not match:
                return ""
            value = match.group(1).strip()
            return re.sub(r"\s+", " ", value).strip(" -*") if collapse else value

        headline = section("Headline", ("Explanation", "Operator Focus", "Caveat"))
        explanation = section("Explanation", ("Operator Focus", "Caveat"))
        focus_text = section("Operator Focus", ("Caveat",), collapse=False)
        caveat = section("Caveat")
        operator_focus = [
            re.sub(r"^\s*[-*]\s*", "", item).strip()
            for item in re.split(r"\s*(?:\n|;)+\s*", focus_text)
            if item.strip().strip("*-").strip()
        ][:3]
        if not headline or not explanation or not operator_focus or not caveat:
            return None
        return AgentExplanationPayload(
            headline=headline,
            explanation=explanation,
            operator_focus=operator_focus,
            caveat=caveat,
        )

    @staticmethod
    def _validate_payload(payload: AgentExplanationPayload) -> AgentExplanationPayload:
        forbidden = ("maneuver", "avoidance", "probability", "approve", "reject", "execute command")
        text = " ".join((payload.headline, payload.explanation, payload.caveat, *payload.operator_focus)).lower()
        if any(term in text for term in forbidden):
            raise ValueError("Ollama response contained operational maneuver advice")
        if "public" not in payload.caveat.lower() or "tle" not in payload.caveat.lower():
            raise ValueError("Ollama response omitted the public-TLE caveat")
        return payload

    async def explain(self, facts: dict[str, Any]) -> AgentExplanationResponse:
        if not self.config.enabled:
            return self._fallback(facts, "Ollama is disabled")
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(self._invoke, facts), timeout=self.config.timeout_seconds + 5
            )
            return AgentExplanationResponse(
                **payload.model_dump(), source="ollama", model=self.config.model
            )
        except Exception as exc:  # noqa: BLE001 - optional provider must fail soft
            logger.warning("Ollama explanation unavailable: %s", exc)
            return self._fallback(facts, str(exc))

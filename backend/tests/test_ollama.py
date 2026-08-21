import asyncio
from datetime import UTC, datetime, timedelta

from perigee.agent.features import AgentFeatures
from perigee.agent.ollama import OllamaAssistant
from perigee.agent.schemas import AgentQueryPayload
from perigee.config import OllamaConfig
from pydantic import ValidationError


def _facts() -> dict[str, object]:
    return {
        "object_a_name": "ISS (ZARYA)",
        "object_b_name": "TEST DEBRIS",
        "risk_score": 82.5,
        "risk_tier": "critical",
        "miss_distance_km": 1.2,
        "relative_velocity_kmps": 12.4,
        "tca": datetime.now(UTC) + timedelta(hours=6),
        "factor_breakdown": {
            "miss_distance": {"raw_value": 1.2, "contribution": 48.0},
            "relative_velocity": {"raw_value": 12.4, "contribution": 16.5},
        },
    }


def test_disabled_ollama_returns_deterministic_template() -> None:
    result = asyncio.run(OllamaAssistant(OllamaConfig(enabled=False)).explain(_facts()))

    assert result.source == "template"
    assert result.model == "qwen3.5:9b"
    assert "critical" in result.explanation
    assert result.provider_error == "Ollama is disabled"


def test_markdown_provider_response_is_coerced_to_safe_payload() -> None:
    payload = OllamaAssistant._parse_markdown_payload(
        """**Headline:** Close pass.\n\n**Explanation:** Elevated from the supplied distance.\n\n**Operator Focus:**\n* Verify TLE freshness.\n* Compare the next screening cycle.\n\n**Caveat:** Public TLE screening is not operational."""
    )

    assert payload is not None
    assert payload.operator_focus == ["Verify TLE freshness.", "Compare the next screening cycle."]


def test_snake_case_provider_response_with_json_focus_is_coerced() -> None:
    payload = OllamaAssistant._parse_markdown_payload(
        """headline: Close pass between A and B.\nexplanation: Ranked critical from the supplied distance.\noperator_focus: ["Validate TLE freshness", "Compare the next cycle"]\ncaveat: Public TLE screening data is not operational."""
    )

    assert payload is not None
    assert payload.headline == "Close pass between A and B."
    assert payload.operator_focus == ["Validate TLE freshness", "Compare the next cycle"]


def test_disabled_agent_features_are_read_only_and_deterministic() -> None:
    features = AgentFeatures(OllamaConfig(enabled=False))
    query = asyncio.run(features.query("What is urgent?", {"events": []}))
    insights = asyncio.run(features.insights({"events": []}))

    assert query.source == "template"
    assert query.referenced_event_ids == []
    assert insights.source == "template"
    assert insights.insights == []


def test_agent_payload_forbids_extra_fields() -> None:
    try:
        AgentQueryPayload(answer="grounded", referenced_event_ids=[], unexpected="blocked")
    except ValidationError:
        pass
    else:
        raise AssertionError("agent schema accepted an unexpected field")


def test_agent_guardrail_rejects_operational_language() -> None:
    try:
        AgentFeatures._validate_text("You should perform an avoidance maneuver now")
    except ValueError:
        pass
    else:
        raise AssertionError("agent guardrail accepted operational advice")


def test_guardrails_allow_advisory_discussion_of_measures() -> None:
    text = (
        "Analysts can monitor the next screening cycle and validate TLE freshness for both objects. "
        "If the miss distance keeps shrinking, a human review could consider whether any operational "
        "response is warranted, but that decision belongs to operators."
    )
    sanitized = AgentFeatures._validate_text(text)
    assert "monitor the next screening cycle" in sanitized
    assert "human review" in sanitized


def test_guardrails_still_block_probability_figures() -> None:
    try:
        AgentFeatures._validate_text("There is roughly a 73% chance of collision based on these numbers.")
    except ValueError:
        pass
    else:
        raise AssertionError("agent guardrail accepted a probability figure")

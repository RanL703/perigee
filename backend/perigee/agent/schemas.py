from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentExplanationPayload(StrictModel):
    headline: str = Field(description="One concise plain-language headline about this close approach")
    explanation: str = Field(description="Explain why the event is ranked as it is using only supplied facts")
    operator_focus: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Non-maneuver review questions an analyst should focus on",
    )
    caveat: str = Field(description="Accuracy limitation of public TLE screening")


class AgentExplanationResponse(AgentExplanationPayload):
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None


class AgentQueryPayload(StrictModel):
    answer: str = Field(min_length=1, max_length=2000)
    referenced_event_ids: list[str] = Field(default_factory=list, max_length=10)


class AgentQueryResponse(AgentQueryPayload):
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None


class RecommendationPayload(StrictModel):
    recommendation: str = Field(min_length=1, max_length=1000)


class RecommendationResponse(RecommendationPayload):
    source: Literal["ollama", "template"]
    model: str
    screened_at: str
    provider_error: str | None = None


class InsightPayload(StrictModel):
    observation: str = Field(min_length=1, max_length=500)
    related_event_ids: list[str] = Field(default_factory=list, max_length=10)


class InsightsPayload(StrictModel):
    insights: list[InsightPayload] = Field(default_factory=list, max_length=4)


class InsightsResponse(InsightsPayload):
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None

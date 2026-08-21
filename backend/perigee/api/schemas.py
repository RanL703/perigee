from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FactorResponse(BaseModel):
    raw_value: float
    contribution: float
    weight: float
    caption: str


class EventObjectResponse(BaseModel):
    norad_id: int
    name: str
    object_type: str
    type_description: str


class EventSummaryResponse(BaseModel):
    id: UUID
    object_a: EventObjectResponse
    object_b: EventObjectResponse
    tca: datetime
    tca_display: str
    miss_distance_km: float
    miss_distance_display: str
    relative_velocity_kmps: float
    relative_velocity_display: str
    risk_score: float = Field(ge=0, le=100)
    risk_tier: str
    summary: str
    factor_breakdown: dict[str, FactorResponse]
    screened_at: datetime


class TrendPoint(BaseModel):
    screened_at: datetime
    risk_score: float
    miss_distance_km: float


class EventDetailResponse(EventSummaryResponse):
    trend_history: list[TrendPoint]
    trend_label: str
    dominant_factor: str


class ObjectResponse(EventObjectResponse):
    epoch: datetime
    last_updated: datetime
    latitude_deg: float | None = None
    longitude_deg: float | None = None
    altitude_km: float | None = None
    altitude_display: str | None = None


class ObjectListItemResponse(BaseModel):
    norad_id: int
    name: str
    object_type: str
    type_description: str
    epoch: datetime | None = None


class ObjectListResponse(BaseModel):
    items: list[ObjectListItemResponse]
    total_returned: int


class ScreeningConfigResponse(BaseModel):
    horizon_hours: int
    conjunction_threshold_km: float
    coorbital_relative_velocity_kmps: float
    object_limit: int
    refresh_interval_hours: int


class RiskConfigResponse(BaseModel):
    weights: dict[str, float]
    critical_threshold: float
    elevated_threshold: float


class AiConfigResponse(BaseModel):
    enabled: bool
    model: str


class ConfigResponse(BaseModel):
    screening: ScreeningConfigResponse
    risk: RiskConfigResponse
    ai: AiConfigResponse


class StatsResponse(BaseModel):
    objects_tracked: int
    events_screened: int
    critical_count: int
    elevated_count: int
    low_count: int
    last_screened_at: datetime | None
    last_refresh_at: datetime | None
    last_refresh_display: str | None
    data_source: str
    refresh_in_progress: bool
    last_refresh_error: str | None = None


class RefreshResponse(BaseModel):
    job_id: UUID
    status: str
    message: str


class ExplainResponse(BaseModel):
    headline: str
    explanation: str
    operator_focus: list[str]
    caveat: str
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class AgentQueryResponse(BaseModel):
    answer: str
    referenced_event_ids: list[str]
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None


class RecommendationResponse(BaseModel):
    recommendation: str
    source: Literal["ollama", "template"]
    model: str
    screened_at: str
    provider_error: str | None = None


class InsightResponse(BaseModel):
    observation: str
    related_event_ids: list[str]


class InsightsResponse(BaseModel):
    insights: list[InsightResponse]
    source: Literal["ollama", "template"]
    model: str
    provider_error: str | None = None


class EventListResponse(BaseModel):
    items: list[EventSummaryResponse]
    page: int
    limit: int
    total_returned: int


class ErrorResponse(BaseModel):
    detail: str


class WebSocketMessage(BaseModel):
    type: str
    payload: dict[str, Any]

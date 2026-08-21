from datetime import datetime
from typing import Any
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

import asyncio
import json
import math
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from perigee.api.schemas import (
    EventDetailResponse,
    EventListResponse,
    EventObjectResponse,
    EventSummaryResponse,
    FactorResponse,
    ObjectResponse,
    RefreshResponse,
    StatsResponse,
    TrendPoint,
)
from perigee.domain import ObjectType, OrbitalObject
from perigee.narrative.templates import (
    event_summary,
    factor_caption,
    format_distance,
    format_velocity,
    object_type_description,
    relative_time,
    time_to_tca,
)
from perigee.propagation.screening import propagate
from perigee.services.refresh import AppState, start_refresh

router = APIRouter(prefix="/api")


def _object_response(norad_id: int, name: str, object_type: str) -> EventObjectResponse:
    return EventObjectResponse(
        norad_id=norad_id,
        name=name,
        object_type=object_type,
        type_description=object_type_description(object_type),
    )


def _factor_responses(raw_factors: dict[str, object]) -> dict[str, FactorResponse]:
    result: dict[str, FactorResponse] = {}
    for name, raw in raw_factors.items():
        factor = raw if isinstance(raw, dict) else {}
        raw_value = float(factor.get("raw_value", 0))
        contribution = float(factor.get("contribution", 0))
        weight = float(factor.get("weight", 0))
        result[name] = FactorResponse(
            raw_value=raw_value,
            contribution=contribution,
            weight=weight,
            caption=factor_caption(name, raw_value, contribution),
        )
    return result


def _event_summary(row: dict[str, object]) -> EventSummaryResponse:
    tca = row["tca"]
    assert isinstance(tca, datetime)
    raw_factors = row["factor_breakdown"]
    if isinstance(raw_factors, str):
        raw_factors = json.loads(raw_factors)
    factors = _factor_responses(raw_factors)
    return EventSummaryResponse(
        id=row["id"],
        object_a=_object_response(row["object_a_id"], row["object_a_name"], row["object_a_type"]),
        object_b=_object_response(row["object_b_id"], row["object_b_name"], row["object_b_type"]),
        tca=tca,
        tca_display=time_to_tca(tca),
        miss_distance_km=float(row["miss_distance_km"]),
        miss_distance_display=format_distance(float(row["miss_distance_km"])),
        relative_velocity_kmps=float(row["relative_velocity_kmps"]),
        relative_velocity_display=format_velocity(float(row["relative_velocity_kmps"])),
        risk_score=float(row["risk_score"]),
        risk_tier=str(row["risk_tier"]),
        summary=event_summary(
            row["object_a_name"], row["object_b_name"], float(row["miss_distance_km"]), tca
        ),
        factor_breakdown=factors,
        screened_at=row["screened_at"],
    )


def _state(request: Request) -> AppState:
    return request.app.state.perigee


@router.get("/events", response_model=EventListResponse)
async def list_events(
    request: Request,
    tier: Annotated[Literal["critical", "elevated", "low"] | None, Query()] = None,
    sort: Annotated[Literal["score_desc", "tca_asc"], Query()] = "score_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> EventListResponse:
    rows = await _state(request).repository.list_events(
        tier=tier, sort=sort, offset=(page - 1) * limit, limit=limit
    )
    items = [_event_summary(dict(row)) for row in rows]
    return EventListResponse(items=items, page=page, limit=limit, total_returned=len(items))


@router.get("/events/{event_id}", response_model=EventDetailResponse)
async def get_event(request: Request, event_id: UUID) -> EventDetailResponse:
    row = await _state(request).repository.get_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conjunction event not found")
    summary = _event_summary(row)
    history = [TrendPoint(**point) for point in row["history"]]
    scores = [point.risk_score for point in history]
    trend_label = "Stable"
    if len(scores) > 1:
        trend_label = "Worsening" if scores[-1] > scores[0] + 1 else "Improving" if scores[-1] < scores[0] - 1 else "Stable"
    dominant_factor = max(summary.factor_breakdown, key=lambda name: summary.factor_breakdown[name].contribution, default="miss_distance")
    return EventDetailResponse(
        **summary.model_dump(), trend_history=history, trend_label=trend_label, dominant_factor=dominant_factor
    )


@router.post("/refresh", response_model=RefreshResponse, status_code=status.HTTP_202_ACCEPTED)
async def refresh(request: Request) -> RefreshResponse:
    job_id = start_refresh(_state(request))
    return RefreshResponse(
        job_id=job_id,
        status="in_progress",
        message="Screening started; listen for refresh_completed on /ws/events.",
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    state = _state(request)
    row = await state.repository.stats()
    last = row["last_screened_at"]
    return StatsResponse(
        objects_tracked=row["objects_tracked"],
        events_screened=row["events_screened"],
        critical_count=row["critical_count"],
        elevated_count=row["elevated_count"],
        low_count=row["low_count"],
        last_screened_at=last,
        last_refresh_at=state.last_refresh_at,
        last_refresh_display=relative_time(state.last_refresh_at) if state.last_refresh_at else None,
        data_source=state.data_source,
        refresh_in_progress=state.refresh_in_progress,
        last_refresh_error=state.last_refresh_error,
    )


@router.get("/objects/{norad_id}", response_model=ObjectResponse)
async def get_object(request: Request, norad_id: Annotated[int, Path(ge=1)]) -> ObjectResponse:
    row = await _state(request).repository.get_object(norad_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tracked object not found")
    object_ = OrbitalObject(
        norad_id=row["norad_id"], name=row["name"], object_type=ObjectType(row["object_type"]),
        tle_line1=row["tle_line1"].strip() if row["tle_line1"] else None,
        tle_line2=row["tle_line2"].strip() if row["tle_line2"] else None,
        epoch=row["epoch"], gp_data=row["gp_data"],
    )
    state_vector = await asyncio.to_thread(propagate, object_, datetime.now(UTC))
    x, y, z = state_vector.position_km
    radius = (x * x + y * y + z * z) ** 0.5
    return ObjectResponse(
        **_object_response(norad_id, row["name"], str(row["object_type"])).model_dump(),
        epoch=row["epoch"], last_updated=row["last_updated"],
        latitude_deg=math.degrees(math.asin(z / radius)), longitude_deg=math.degrees(math.atan2(y, x)),
        altitude_km=radius - 6378.137, altitude_display=f"{radius - 6378.137:.1f} km",
    )

import asyncio
import json
import math
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse

from perigee.agent.schemas import AgentExplanationResponse
from perigee.api.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    AiConfigResponse,
    ConfigResponse,
    EventDetailResponse,
    EventListResponse,
    EventObjectResponse,
    EventSummaryResponse,
    ExplainResponse,
    FactorResponse,
    InsightsResponse,
    ObjectListItemResponse,
    ObjectListResponse,
    ObjectResponse,
    RecommendationResponse,
    RefreshResponse,
    RiskConfigResponse,
    ScreeningConfigResponse,
    StatsResponse,
    TrendPoint,
)
from perigee.config import OllamaConfig, RiskConfig, ScreeningConfig
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


@router.post("/events/{event_id}/explain", response_model=ExplainResponse)
async def explain_event(request: Request, event_id: UUID) -> ExplainResponse:
    state = _state(request)
    row = await state.repository.get_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conjunction event not found")
    if state.assistant is None:
        raise HTTPException(status_code=503, detail="Operator assistant is not configured")
    raw_factors = row["factor_breakdown"]
    if isinstance(raw_factors, str):
        raw_factors = json.loads(raw_factors)
    facts = {
        "object_a_name": row["object_a_name"],
        "object_b_name": row["object_b_name"],
        "risk_score": float(row["risk_score"]),
        "risk_tier": str(row["risk_tier"]),
        "miss_distance_km": float(row["miss_distance_km"]),
        "relative_velocity_kmps": float(row["relative_velocity_kmps"]),
        "tca": row["tca"],
        "factor_breakdown": raw_factors,
    }
    result: AgentExplanationResponse = await state.assistant.explain(facts)
    return ExplainResponse(**result.model_dump())


async def _agent_context(state, payload: AgentQueryRequest) -> dict[str, object]:
    """Shared read-only context for the plain and streaming query endpoints."""
    stats_row = await state.repository.stats()
    events = await state.repository.agent_event_context()
    catalog = await state.repository.list_objects(search=None, limit=500)
    return {
        "stats": dict(stats_row),
        "events": events,
        "model": state.agent_features.config.model,
        "history": [turn.model_dump() for turn in payload.history],
        # Compact catalog snapshot so the agent can look up any tracked
        # object — flagged or not — without extra database round-trips.
        "catalog": [
            {"norad_id": int(row["norad_id"]), "name": str(row["name"]), "object_type": str(row["object_type"])}
            for row in catalog
        ],
    }


@router.post("/agent/query", response_model=AgentQueryResponse)
async def agent_query(request: Request, payload: AgentQueryRequest) -> AgentQueryResponse:
    state = _state(request)
    if state.agent_features is None:
        raise HTTPException(status_code=503, detail="Agent features are not configured")
    context = await _agent_context(state, payload)
    result = await state.agent_features.query(payload.question, context)
    return AgentQueryResponse(**result.model_dump())


@router.post("/agent/query/stream")
async def agent_query_stream(request: Request, payload: AgentQueryRequest) -> StreamingResponse:
    state = _state(request)
    if state.agent_features is None:
        raise HTTPException(status_code=503, detail="Agent features are not configured")
    context = await _agent_context(state, payload)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        result = await state.agent_features.query(payload.question, context)
        # The grounded answer is validated first; it is then released in small
        # paced chunks so the chat box renders progressively like a live model.
        words = result.answer.split(" ")
        chunk = ""
        for index, word in enumerate(words):
            chunk += (" " if chunk else "") + word
            if len(chunk) >= 28 or index == len(words) - 1:
                yield f"data: {json.dumps({'type': 'delta', 'text': chunk})}\n\n"
                chunk = ""
                await asyncio.sleep(0.025)
        yield (
            "data: "
            + json.dumps(
                {
                    "type": "done",
                    "source": result.source,
                    "referenced_event_ids": result.referenced_event_ids,
                }
            )
            + "\n\n"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/events/{event_id}/recommendation", response_model=RecommendationResponse)
async def event_recommendation(request: Request, event_id: UUID) -> RecommendationResponse:
    state = _state(request)
    if state.agent_features is None:
        raise HTTPException(status_code=503, detail="Agent features are not configured")
    row = await state.repository.get_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conjunction event not found")
    screened_at = row["screened_at"]
    cached = await state.repository.get_recommendation(event_id, screened_at)
    if cached is not None:
        return RecommendationResponse(
            recommendation=cached,
            source="ollama",
            model=state.agent_features.config.model,
            screened_at=screened_at.isoformat(),
        )
    raw_factors = row["factor_breakdown"]
    if isinstance(raw_factors, str):
        raw_factors = json.loads(raw_factors)
    facts = {
        "event_id": str(event_id),
        "object_a_name": row["object_a_name"],
        "object_b_name": row["object_b_name"],
        "risk_score": float(row["risk_score"]),
        "risk_tier": str(row["risk_tier"]),
        "miss_distance_km": float(row["miss_distance_km"]),
        "relative_velocity_kmps": float(row["relative_velocity_kmps"]),
        "tca": row["tca"],
        "trend_history": row["history"],
        "factor_breakdown": raw_factors,
    }
    result = await state.agent_features.recommendation(facts, screened_at)
    if result.source == "ollama":
        await state.repository.save_recommendation(event_id, screened_at, result.recommendation)
    return RecommendationResponse(**result.model_dump())


@router.get("/agent/insights", response_model=InsightsResponse)
async def agent_insights(request: Request) -> InsightsResponse:
    state = _state(request)
    if state.agent_features is None:
        raise HTTPException(status_code=503, detail="Agent features are not configured")
    result = await state.agent_features.insights({"events": await state.repository.agent_event_context()})
    return InsightsResponse(**result.model_dump())


@router.get("/objects", response_model=ObjectListResponse)
async def list_objects(
    request: Request,
    search: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ObjectListResponse:
    rows = await _state(request).repository.list_objects(search=search or None, limit=limit)
    items = [
        ObjectListItemResponse(
            norad_id=int(row["norad_id"]),
            name=str(row["name"]),
            object_type=str(row["object_type"]),
            type_description=object_type_description(str(row["object_type"])),
            epoch=row["epoch"],
        )
        for row in rows
    ]
    return ObjectListResponse(items=items, total_returned=len(items))


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    screening = ScreeningConfig()
    risk = RiskConfig()
    ai = OllamaConfig()
    return ConfigResponse(
        screening=ScreeningConfigResponse(
            horizon_hours=screening.horizon_hours,
            conjunction_threshold_km=screening.conjunction_threshold_km,
            coorbital_relative_velocity_kmps=screening.coorbital_relative_velocity_kmps,
            object_limit=screening.object_limit,
            refresh_interval_hours=screening.refresh_interval_hours,
        ),
        risk=RiskConfigResponse(
            weights={
                "miss_distance": risk.distance_weight,
                "relative_velocity": risk.velocity_weight,
                "object_type": risk.object_type_weight,
                "trend": risk.trend_weight,
            },
            critical_threshold=risk.critical_threshold,
            elevated_threshold=risk.elevated_threshold,
        ),
        ai=AiConfigResponse(enabled=ai.enabled, model=ai.model),
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    state = _state(request)
    row = await state.repository.stats()
    last = row["last_screened_at"]
    # `last_refresh_at` lives in memory and resets on restart; fall back to the
    # persisted screening timestamp so the header never claims "Never" while a
    # valid catalog exists.
    refresh_at = state.last_refresh_at or last
    return StatsResponse(
        objects_tracked=row["objects_tracked"],
        events_screened=row["events_screened"],
        critical_count=row["critical_count"],
        elevated_count=row["elevated_count"],
        low_count=row["low_count"],
        last_screened_at=last,
        last_refresh_at=refresh_at,
        last_refresh_display=relative_time(refresh_at) if refresh_at else None,
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

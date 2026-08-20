import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from perigee.api.websocket import ConnectionManager
from perigee.config import ScreeningConfig
from perigee.ingestion.celestrak import fetch_catalog_result
from perigee.persistence.repository import PerigeeRepository
from perigee.propagation.screening import screen
from perigee.scoring.risk import assess


@dataclass
class AppState:
    repository: PerigeeRepository
    websocket_manager: ConnectionManager = field(default_factory=ConnectionManager)
    data_source: str = "unknown"
    last_refresh_at: datetime | None = None
    active_job_id: UUID | None = None
    active_task: asyncio.Task[None] | None = None

    @property
    def refresh_in_progress(self) -> bool:
        return self.active_task is not None and not self.active_task.done()


async def _screen_and_store(state: AppState, job_id: UUID) -> None:
    config = ScreeningConfig()
    started_at = datetime.now(UTC)
    await state.websocket_manager.broadcast(
        {"type": "refresh_started", "payload": {"job_id": str(job_id)}}
    )
    try:
        result = await asyncio.to_thread(
            fetch_catalog_result,
            config.catalog_url,
            config.object_limit,
            cache_path=config.cache_path,
            retries=config.fetch_retries,
            backoff_seconds=config.fetch_backoff_seconds,
        )
        await state.repository.upsert_objects(result.objects)
        events = await asyncio.to_thread(screen, result.objects, started_at, config)
        for event in events:
            pair_key = ":".join(
                map(str, sorted((event.object_a.norad_id, event.object_b.norad_id)))
            )
            event_id = uuid5(NAMESPACE_URL, f"perigee/conjunction/{pair_key}")
            history = await state.repository.previous_miss_distances(event_id)
            assessment = assess(event, history, screening=config)
            await state.repository.save_assessment(event, assessment, started_at)
            await state.websocket_manager.broadcast(
                {
                    "type": "event_updated" if history else "event_created",
                    "payload": {
                        "event_id": str(event_id),
                        "object_a": event.object_a.name,
                        "object_b": event.object_b.name,
                        "risk_tier": assessment.tier.value,
                    },
                }
            )
        state.data_source = result.source
        state.last_refresh_at = started_at
        await state.websocket_manager.broadcast(
            {
                "type": "refresh_completed",
                "payload": {
                    "job_id": str(job_id),
                    "source": result.source,
                    "objects": len(result.objects),
                    "events": len(events),
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 - refresh failures are reported to clients
        await state.websocket_manager.broadcast(
            {
                "type": "refresh_failed",
                "payload": {"job_id": str(job_id), "error": str(exc)},
            }
        )
    finally:
        state.active_job_id = None


def start_refresh(state: AppState) -> UUID:
    if state.refresh_in_progress:
        if state.active_job_id is None:
            raise RuntimeError("Refresh is already running")
        return state.active_job_id
    job_id = uuid4()
    state.active_job_id = job_id
    state.active_task = asyncio.create_task(_screen_and_store(state, job_id))
    return job_id

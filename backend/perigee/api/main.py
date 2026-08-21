from contextlib import asynccontextmanager
from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from perigee.api.routes import router
from perigee.config import DatabaseConfig, ScreeningConfig
from perigee.persistence.repository import PerigeeRepository
from perigee.services.refresh import AppState, start_refresh


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = PerigeeRepository(DatabaseConfig().url)
    await repository.connect()
    state = AppState(repository=repository)
    app.state.perigee = state
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        start_refresh,
        "interval",
        hours=ScreeningConfig().refresh_interval_hours,
        args=[state],
        id="periodic-refresh",
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if state.active_task is not None and not state.active_task.done():
            state.active_task.cancel()
        await repository.close()


app = FastAPI(
    title="Perigee Conjunction Triage API",
    description="Explainable satellite close-approach screening using public CelesTrak GP data.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/events")
async def events_websocket(websocket: WebSocket) -> None:
    state = websocket.app.state.perigee
    await state.websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await state.websocket_manager.disconnect(websocket)

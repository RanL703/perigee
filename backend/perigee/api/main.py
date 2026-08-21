from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from os import getenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from perigee.agent.features import AgentFeatures
from perigee.agent.ollama import OllamaAssistant
from perigee.api.routes import router
from perigee.config import DatabaseConfig, OllamaConfig, ScreeningConfig
from perigee.persistence.repository import PerigeeRepository
from perigee.services.refresh import AppState, start_refresh


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = PerigeeRepository(DatabaseConfig().url)
    await repository.connect()
    ollama_config = OllamaConfig()
    state = AppState(
        repository=repository,
        assistant=OllamaAssistant(ollama_config),
        agent_features=AgentFeatures(ollama_config),
    )
    app.state.perigee = state
    scheduler = AsyncIOScheduler(timezone=UTC)
    # Reinstate live data as soon as the stack boots (skipped gracefully by the
    # cached fallback if CelesTrak is unreachable), then keep re-screening on
    # the configured interval.
    scheduler.add_job(
        start_refresh,
        "date",
        run_date=datetime.now(UTC) + timedelta(seconds=10),
        args=[state],
        id="startup-refresh",
    )
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
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

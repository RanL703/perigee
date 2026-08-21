# Perigee

Perigee is a satellite conjunction triage dashboard. It ingests public CelesTrak GP data, stores normalized orbital objects in PostgreSQL, propagates them with SGP4, scores close approaches deterministically, and exposes the results through a FastAPI REST/WebSocket backend. A local Ollama `qwen3.5:9b` layer adds read-only explanations and analyst assistance; it never changes the physics or risk score.

## Demo architecture

```text
CelesTrak JSON/TLE
        |
        v
 FastAPI ingestion ----> disk cache + PostgreSQL
        |
        v
 SGP4 propagation -> explainable risk score -> REST/WebSocket
                                                |
                         React/Vite dashboard <-+
                                                |
                         local Ollama (optional, read-only)
```

The backend is FastAPI (not Flask). The frontend is a separate Vite development server during local demos.

## Fast demo setup

Requirements: Docker Desktop/WSL2, Node 22+, npm, Python 3.13, and Ollama with `qwen3.5:9b` installed.

```bash
cp .env.example .env
ollama pull qwen3.5:9b       # one-time, if the model is not installed
docker compose up -d postgres redis backend
```

In a second terminal:

```bash
cd frontend
npm ci                       # first run only
npm run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173>. The backend is at <http://127.0.0.1:8000>, Swagger is at <http://127.0.0.1:8000/docs>, and the WebSocket is `ws://127.0.0.1:8000/ws/events`.

For a production-like frontend bundle:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1
```

The current Compose stack runs PostgreSQL, Redis, and backend. Start Vite separately for the demo; the backend CORS configuration allows `localhost:5173` and `127.0.0.1:5173`.

## Demo flow

1. Open the dashboard and confirm the header says `Live telemetry`.
2. Confirm the stats show tracked objects and the current source (`live` or `cache`).
3. Click **Refresh now**. It returns immediately; the WebSocket changes the UI to screening state and then refreshes cards when the cycle completes.
4. If events are present, click a priority event. Show the deterministic score, TCA, miss distance, velocity, trend, and factor captions first.
5. In the detail drawer, click **Explain with local AI**. The AI block is intentionally labeled `AI-assisted`; the deterministic score remains separate.
6. Use **Ask Perigee** with questions such as:
   - `Which alerts need attention?`
   - `What is the largest risk driver?`
   - `What data should I verify before reviewing this screen?`
7. If there are no flagged events, show the honest empty state. Do not seed fabricated conjunctions for the demo.
8. To demonstrate resilience, stop CelesTrak/network access after one successful fetch, click refresh, and show the cached-data indicator/error state.

## Backend smoke checks

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/stats
curl -fsS 'http://127.0.0.1:8000/api/events?limit=25'
curl -fsS http://127.0.0.1:8000/api/objects/25544
curl -i -X POST http://127.0.0.1:8000/api/refresh
curl -fsS http://127.0.0.1:8000/api/agent/insights
curl -fsS -X POST http://127.0.0.1:8000/api/agent/query \
  -H 'content-type: application/json' \
  -d '{"question":"What is the most urgent thing right now?"}'
```

Expected behavior:

- `GET /health` returns `{"status":"ok"}`.
- `POST /api/refresh` returns `202` and a `job_id`; it does not block for the screening cycle.
- `/api/stats` reports counts, refresh state, last refresh, source, and errors.
- AI responses always contain a valid schema. If Ollama is unavailable or violates the structured contract, `source` becomes `template` and `provider_error` explains why.

## API contract

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Process health |
| GET | `/api/stats` | Object/event counts and refresh state |
| GET | `/api/events` | Paginated/filterable conjunction summaries |
| GET | `/api/events/{id}` | Event detail, factors, and trend history |
| POST | `/api/events/{id}/explain` | Guarded local-AI explanation |
| GET | `/api/events/{id}/recommendation` | Cached per-screening-cycle triage suggestion |
| GET | `/api/objects/{norad_id}` | Object metadata and propagated position |
| POST | `/api/refresh` | Asynchronous ingest + screen job |
| POST | `/api/agent/query` | Read-only Ask Perigee query |
| GET | `/api/agent/insights` | Read-only descriptive event insights |
| WS | `/ws/events` | Refresh and event lifecycle messages |

WebSocket message types are `refresh_started`, `event_created`, `event_updated`, `refresh_completed`, and `refresh_failed`.

## Ingesting a larger live catalog

CelesTrak may rate-limit repeated requests, especially large groups. Use a documented group, keep the cache path scoped to that URL, and do not bypass CelesTrak policy:

```bash
CELESTRAK_CATALOG_URL='https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=JSON' \
OBJECT_LIMIT=300 \
CELESTRAK_CACHE_PATH=data/cache/celestrak_visual_demo.json \
.venv/bin/perigee-screen --ingest-only
```

To ingest and screen the same set headlessly:

```bash
SCREENING_HORIZON_HOURS=2 \
CELESTRAK_CATALOG_URL='https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=JSON' \
OBJECT_LIMIT=157 \
CELESTRAK_CACHE_PATH=data/cache/celestrak_visual_demo.json \
.venv/bin/perigee-screen
```

The last successful response is cached. A failed live fetch uses only a URL-matching cache; it never silently mixes catalogs.

## Verification before demo

Backend:

```bash
ruff check backend
.venv/bin/pytest -q
docker compose config --quiet
docker compose ps
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Integration checks:

```bash
curl -i -X OPTIONS http://127.0.0.1:8000/api/stats \
  -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: GET'
```

The response should include `access-control-allow-origin: http://localhost:5173`. Use the browser DevTools Network tab to confirm REST calls go to port 8000 and the WebSocket connects to `/ws/events`.

## Configuration

Copy `.env.example` to `.env` and tune only what the demo needs:

- `DATABASE_URL` / PostgreSQL settings
- `CELESTRAK_CATALOG_URL`, `OBJECT_LIMIT`, `CELESTRAK_CACHE_PATH`
- `SCREENING_HORIZON_HOURS`, propagation steps, and risk thresholds
- `OLLAMA_ENABLED`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`
- `FRONTEND_ORIGINS`

The Docker backend uses `host.docker.internal:11434` to reach Ollama on the host. Host-run Python uses `127.0.0.1:11434` by default.

## Troubleshooting

**Frontend shows “Backend connection issue”**

Check `docker compose ps`, then `curl http://127.0.0.1:8000/health`. Confirm Vite is running on port 5173 and that `FRONTEND_ORIGINS` includes its exact origin.

**Status says “Backend reconnecting”**

The REST API may still work while the WebSocket is reconnecting. Check `/ws/events`, backend logs, and browser console output.

**CelesTrak returns 403 or times out**

Wait for CelesTrak’s update/rate-limit window. Use the last successful URL-matching cache. Do not manually fabricate conjunction data.

**AI shows a template response**

This is safe and expected when Ollama is unavailable or Qwen returns invalid/unsafe structured output. Check `curl http://127.0.0.1:11434/api/tags`, confirm `qwen3.5:9b`, and inspect `provider_error`.

**No events appear**

That is a valid result for the current object set and horizon. The dashboard should show the honest empty state; do not seed fake events for a demo claim.

## Continuation notes

The detailed cross-session implementation record is [`docs/memory/perigee-session.md`](docs/memory/perigee-session.md). It records the architecture, completed work, skills used, tests run, known limitations, and the next recommended work. Read it before continuing in a new session.

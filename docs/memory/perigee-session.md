# Perigee Cross-Session Memory

> Durable handoff record for continuing Perigee work after this session. This file is intentionally repository-local so it survives thread/session changes. It follows the deep-agents-memory principle: local filesystem persistence is the reliable handoff mechanism here; no ephemeral chat state is required to resume.

## Product and scope

Perigee is a satellite conjunction/collision-risk triage assistant. The product ingests public CelesTrak GP data, validates and caches it, stores orbital objects in PostgreSQL, propagates with SGP4, computes close approaches, assigns deterministic explainable risk scores, and presents the results in a React mission-control dashboard. A local Ollama `qwen3.5:9b` layer is strictly read-only and advisory.

The current backend is FastAPI, not Flask. The frontend is React 19 + Vite. PostgreSQL and Redis run through Docker Compose. The local frontend is normally started separately with Vite on port 5173 while the backend listens on port 8000.

## Non-negotiable guardrails

- Never fabricate conjunctions, orbital data, scores, or event history for the demo.
- SGP4 propagation and risk scoring remain deterministic and are never delegated to an LLM.
- AI receives explicit read-only context only; it cannot refresh, write objects, write events, or alter scoring.
- AI output is visibly labeled `AI-assisted` in the frontend.
- AI must not make maneuver/avoidance recommendations, probability claims, authoritative collision claims, or machine-executable commands.
- Invalid, unsafe, unavailable, or unstructured model output fails closed to a deterministic template response.
- CelesTrak fallback is URL-scoped: only a cache created for the exact requested URL may be used.
- Frontend changes are now authorized because the integration phase began, but preserve backend contracts and do not rewrite deterministic backend behavior for UI convenience.

## Skills used and why

### Backend and data

- `fastapi`: modular routers, typed Pydantic response models, async-safe route behavior, CORS, and WebSocket conventions.
- `fastapi-templates` was part of the selected backend direction during setup; the existing modular FastAPI structure was retained rather than scaffolded over.
- `database-schema-designer`: PostgreSQL object/event/history schema, indexes, constraints, JSONB GP data, and recommendation-cache table design.
- `docker-compose`: PostgreSQL, Redis, backend service dependencies, health checks, named volumes, host Ollama mapping, and rebuild/start verification.
- `verification-before-completion`: fresh test/build/API evidence was required before reporting passing work.
- `systematic-debugging`: used when CelesTrak 403/DNS/structured-agent failures occurred; failures were reproduced before changing code.

### Agentic and prompting

- `ecosystem-primer`: selected LangChain for the fixed-tool explanation/query/recommendation paths; Deep Agents/LangGraph were not forced onto simple single-shot features.
- `langchain-dependencies`: selected and locked `langchain`, `langchain-core`, and `langchain-ollama` dependencies.
- `langchain-fundamentals`: all runtime agents use `create_agent`, `@tool`, and typed `response_format` schemas.
- `prompt-optimizer`: system prompts were structured around role, tool policy, explicit context, constraints, output contract, and Qwen-specific failure behavior. A repeated live eval slice was used to identify prose/Markdown drift.
- `structured-output`: agent payloads are Pydantic models and the final handoff/report uses consistent sections and evidence.
- `deep-agents-memory`: this durable file is the local filesystem handoff. The repository is not currently running a Deep Agent or StoreBackend; use a real persistent Store/PostgresStore only if a future feature needs runtime cross-thread agent memory.

### Frontend and integration

- `frontend-design`: guided the mission-control visual direction, restrained palette, typography, event-detail “signature” interaction, explicit AI labeling, empty-state copy, responsive/focus requirements, and avoidance of generic decorative UI.
- `webapp-testing`: used for Vite server smoke-test procedure. Full Playwright automation was not available because the Python Playwright package/browser was not installed; build and HTTP smoke checks were still run.
- `writing-plans`: created plans before multi-step backend/agent/frontend integration work under `docs/superpowers/plans/`.

## Repository areas and completed implementation

### Ingestion

`backend/perigee/ingestion/celestrak.py`:

- Fetches documented CelesTrak GP JSON with bounded connect/read timeouts, retries, exponential backoff, `Accept: application/json`, and an identifiable Perigee user agent.
- Supports current OMM/GP JSON fields and legacy TLE lines.
- Validates fields through `sgp4.omm`, parses epochs, classifies payload/debris/rocket body conservatively, skips malformed records, and requires at least one valid object.
- Writes an atomic cache envelope containing URL, timestamp, and records.
- Uses cache only if its URL exactly matches the failed request.

Observed CelesTrak behavior: `GROUP=active` and large repeated groups can return 403/rate-limit responses. `GROUP=visual` and `GROUP=stations` successfully supplied live data during testing. A successful visual ingest stored 157 objects and stations ingest stored 22 objects; Postgres reached 176 tracked objects. A 2-hour real SGP4 screening over 157 visual objects completed successfully and found zero close approaches, which is a valid result.

### Propagation and risk

`backend/perigee/propagation/screening.py`:

- Coarse altitude-band filtering and coarse-to-fine propagation.
- Cached `Satrec` objects and altitude bands inside a screen to avoid repeated construction.
- Configurable horizon, thresholds, coarse/fine steps, candidate distance, and altitude padding.

`backend/perigee/scoring/risk.py`:

- Deterministic 0–100 score with distance, relative velocity, object type, and trend factors.
- Configurable critical/elevated thresholds and stored factor breakdown.

### Persistence and refresh

`backend/perigee/persistence/repository.py`:

- Async PostgreSQL pool and upsert methods for objects/events/history.
- Stable UUID pair IDs for repeat screenings.
- Event detail includes joined object metadata and history.
- `agent_recommendations` is created on connect and also defined in `db/init/003_agent_recommendations.sql`; cached by `(event_id, screened_at)`.
- Read-only aggregate context supports Ask Perigee/insights.

`backend/perigee/services/refresh.py`:

- Asynchronous refresh task, APScheduler integration, refresh state/error, data source, and WebSocket lifecycle broadcasts.
- `POST /api/refresh` returns immediately with a job ID.

### API and WebSocket

`backend/perigee/api/main.py`:

- FastAPI lifespan opens/closes PostgreSQL, starts APScheduler, initializes Ollama assistants, and exposes `/ws/events`.
- CORS allows `FRONTEND_ORIGINS`, defaulting to `http://localhost:5173,http://127.0.0.1:5173`.

`backend/perigee/api/routes.py` currently exposes:

- `GET /api/stats`
- `GET /api/events`
- `GET /api/events/{event_id}`
- `POST /api/events/{event_id}/explain`
- `GET /api/events/{event_id}/recommendation`
- `GET /api/objects/{norad_id}`
- `POST /api/refresh`
- `POST /api/agent/query`
- `GET /api/agent/insights`

WebSocket messages: `refresh_started`, `event_created`, `event_updated`, `refresh_completed`, and `refresh_failed`.

### Agent layer

`backend/perigee/agent/ollama.py`:

- Uses `create_agent`, a read-only facts tool, `ChatOllama`, `qwen3.5:9b`, `reasoning=False`, timeout bounds, strict Pydantic output, Markdown coercion for occasional Qwen prose, and deterministic fallback.
- Explanation output is rejected if it includes maneuver/avoidance/probability/approval/rejection language or omits the public-TLE caveat.

`backend/perigee/agent/features.py`:

- Ask Perigee query agent over explicit stats/event context.
- Recommendation agent over explicit event/factor/trend facts.
- Insights agent over explicit aggregate event facts.
- Each uses `create_agent`, a read-only context tool, structured Pydantic output, one corrective retry, strict text/ID validation, and fail-closed fallback.

`backend/perigee/agent/schemas.py`:

- All agent payload models use `ConfigDict(extra="forbid", str_strip_whitespace=True)`.
- Public response models include `source`, `model`, `provider_error`, and relevant IDs/timestamps.

### Frontend integration completed

`frontend/src/lib/api.ts`:

- Typed REST models and fetch helpers.
- Configurable `VITE_API_BASE_URL` defaulting to `http://127.0.0.1:8000`.
- Configurable `VITE_WS_URL` or derived `/ws/events` URL.

`frontend/src/App.tsx`:

- Live stats and event list.
- WebSocket connection/reconnect indicator.
- Refresh Now flow.
- Event detail drawer with deterministic factor breakdown and AI explanation/recommendation actions.
- Ask Perigee panel and insights panel with AI-assisted labeling.
- Honest empty/error/loading states.

`frontend/src/App.css`:

- Mission-control dark navy styling, cyan/blue telemetry accents, amber/elevated and red/critical states, event drawer, factor bars, AI panel, responsive-safe controls.

## Verification evidence completed

Backend:

```text
ruff check backend                 -> passed
.venv/bin/pytest -q                -> 10 passed
docker compose config --quiet      -> passed
Docker backend health              -> {"status":"ok"}
CORS preflight from localhost:5173 -> 200 with allow-origin header
```

Frontend:

```text
npm ci                              -> installed, 0 vulnerabilities
npm run lint                        -> passed
npm run build                       -> Vite/TypeScript build passed
Vite HTTP smoke test                -> served index.html successfully
```

Live agent checks:

- Three consecutive Ask Perigee requests returned valid `source: "ollama"` structured responses.
- Two direct explanation calls returned valid `source: "ollama"` structured responses.
- Direct recommendation call returned valid guarded Qwen output.
- Empty insights returned deterministic empty output without unnecessary inference.
- Missing event recommendation/explanation endpoints returned 404; wrong HTTP method returned 405.
- `qwen3.5:9b` was present at the local Ollama `/api/tags` endpoint.

Full browser Playwright testing remains a follow-up because the environment did not have the Python Playwright package/browser installed. The frontend build and Vite HTTP smoke check passed.

## Current uncommitted work and caution

The worktree contains backend, frontend, dependency, plan, skill, and documentation changes from the session. Do not reset or discard them. `PRD.md` already had user-side version/agentic additions; preserve those changes. Review `git status` and group commits intentionally before pushing.

## Recommended next continuation

1. Install/run Playwright Chromium and exercise dashboard load, refresh, event drawer, keyboard focus, responsive widths, and WebSocket reconnect.
2. Run a screening object set that produces a real event if one naturally appears; then test the recommendation endpoint through the UI with a real persisted event.
3. Add a frontend service to Docker Compose if the demo must start the entire stack with one command; currently Vite runs separately.
4. Consider adding a backend total-count field to `/api/events` if the frontend needs true page counts; current response exposes `total_returned` only.
5. Keep AI prompts and schemas strict; do not relax validation to make a demo look populated.

## Session 2026-08-21 — module restoration + guardrail rework

### Agent layer fixes

- `backend/perigee/agent/guardrails.py` (new): sentence-level sanitisation. Unsafe sentences
  (probability figures like "12 %", maneuver/approve/reject directives) are removed from model
  output instead of failing the whole response; fail-closed only when nothing advisory-safe
  remains. Used by `features.py::_validate_text` and `ollama.py::_validate_payload`.
- `features.py`: Qwen often answers correctly in prose while skipping LangChain's structured
  tool call. `_run` now coerces the final message into the schema (embedded JSON first, then
  single-string-field prose). Ask Perigee passes the actual analyst question in the user
  message; recursion limit raised to 6.
- `ollama.py::_parse_markdown_payload`: accepts snake_case labels (`operator_focus:`) and a
  JSON-array focus value. NOTE: `\W` does NOT match `_`; separators use `[\W_]*`.

### Screening correctness

- Docked/co-orbital pairs (ISS modules vs each other) produced identical 0 km 70.0 events that
  dominated priority. `screen()` now skips pairs whose relative velocity at closest approach is
  below `COORBITAL_RELATIVE_VELOCITY_KMPS` (default 0.05 km/s, env-tunable). Stale junk events
  were deleted from Postgres once.

### Demo seed data (owner-authorized fabrication)

- `backend/scripts/seed_demo_events.py`: seeds 6 valid-TLE objects and 3 fabricated close
  approaches scored by the real deterministic engine: SENTINEL-6A × FENGYUN 1C DEB critical
  84.3 (worsening trend), STARLINK-3042 × COSMOS 2251 DEB elevated 59.1, SL-16 R/B × IRIDIUM
  109 low 39.1. Refresh cycles never delete events, so the seed survives re-screens.

### New backend endpoints

- `GET /api/objects?search=&limit=` — catalog listing for Objects/Propagation pages.
- `GET /api/config` — screening/risk thresholds for the Screening page (NFR-5 visibility).
- `/api/stats` now falls back to persisted `last_screened_at` when in-memory `last_refresh_at`
  resets after a restart, so the header no longer shows "Never" with a live catalog.

### Frontend

- `App.tsx` rewritten (readable formatting): restored full **Screening** (config grid + run
  refresh + TCA-ordered results table), **Risk Analysis** (tier distribution bars, tier filter
  chips, score-gauge ranked list), **Propagation** (search catalog → SGP4 lat/lon/alt), and a
  real **Objects** catalog page — all wired to the API. Dashboard orbit view is data-driven:
  tier-colored clickable markers positioned by rank/tier ring, pulsing critical markers,
  per-tier legend counts. Priority list sorted explicitly by score desc then TCA. Drawer gained
  a trend sparkline; Ask Perigee got quick-prompt chips.
- Button-based `.table-row`s needed explicit transparent-background reset (UA gray default).

### Verification evidence

```text
ruff check backend            -> passed
pytest -q                     -> 12 passed (incl. co-orbital exclusion + parser tests)
npm run lint / npm run build  -> passed
Playwright Chromium smoke     -> all 5 pages render, 0 console errors;
                                 orbit markers 3, drawer factors 4, propagation
                                 shows lat/lon/alt, screening table 3 rows
Ask Perigee custom prompt     -> source "ollama", correct referenced_event_ids
Probability-bait question     -> deterministic fallback, no probability emitted
explain/recommendation        -> source "ollama"
POST /api/refresh             -> completed; junk co-orbital events did not return
```

## Quick resume command block



```bash
cd /home/myst/code/perigee
docker compose up -d postgres redis backend
cd frontend && npm ci && npm run dev -- --host 127.0.0.1
```

Then open `http://127.0.0.1:5173`, check `http://127.0.0.1:8000/docs`, and run the smoke commands in the root `README.md`.

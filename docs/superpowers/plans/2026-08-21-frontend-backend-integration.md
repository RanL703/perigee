# Frontend–Backend Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan task-by-task with verification checkpoints.

**Goal:** Connect the existing React dashboard to the FastAPI/WebSocket backend and fill only the frontend capability gaps required by the Perigee PRD.

**Architecture:** Keep deterministic data and AI responses served by FastAPI. Add a typed frontend API client and WebSocket subscription, then replace placeholder dashboard states with live stats, event cards, detail/recommendation views, object data, refresh state, and safe empty/error states. Preserve the existing mission-control visual language while making the event/risk explanation the signature interaction.

**Tech Stack:** React 19, TypeScript, Vite, native `fetch`/WebSocket, FastAPI REST/WebSocket, CSS.

**Spec:** `PRD.md`, backend OpenAPI at `/openapi.json`, frontend-design skill.

## Global Constraints

- Do not modify deterministic scoring/propagation behavior for frontend convenience.
- AI content remains visibly labeled and advisory; frontend must not present it as deterministic risk output.
- No fabricated conjunction events or mock production data.
- Keep frontend/backend integration configurable through `VITE_API_BASE_URL` and `VITE_WS_URL`.
- Respect keyboard focus, responsive layouts, and reduced-motion preferences.

### Task 1: Contract audit and typed client

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/types.ts`
- Modify: `frontend/src/vite-env.d.ts` if environment typing is needed
- Test: `frontend/src/lib/api.test.ts` or browser smoke tests

- [ ] Capture current backend OpenAPI paths and response fields.
- [ ] Define TypeScript types matching stats, events, details, objects, refresh, explanations, recommendations, and agent query/insights.
- [ ] Implement fetch helpers with bounded errors and configurable API base URL.
- [ ] Implement WebSocket URL derivation and reconnect/backoff behavior.
- [ ] Run TypeScript build and lint.

### Task 2: Live dashboard and event detail

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/index.css` only when global tokens/accessibility require it

- [ ] Load stats/events on dashboard mount.
- [ ] Render real risk-tier cards, display-formatted values, empty state, loading state, and backend error state.
- [ ] Add event detail drawer/modal with trend history, factor captions, and deterministic-vs-AI labels.
- [ ] Add “Explain” and recommendation actions wired to backend endpoints.
- [ ] Add refresh action returning immediately from `POST /api/refresh` and reflecting WebSocket lifecycle events.
- [ ] Preserve the mission-control palette and use one signature visual: an orbit-style event detail focus ring rather than generic decorative gradients.

### Task 3: Objects, propagation, agent query, and WebSocket

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Create: `frontend/src/components/AgentPanel.tsx` if the query UI warrants extraction

- [ ] Wire object lookup/list presentation to available backend data without inventing an unsupported list endpoint.
- [ ] Add Ask Perigee panel with strict loading/error/AI-assisted labeling and referenced event links.
- [ ] Subscribe to `/ws/events`; update stats/events and refresh status without full reload.
- [ ] Add reconnect status and clear offline/cached-data copy.

### Task 4: End-to-end verification

- [ ] Run backend Ruff/tests and Docker Compose health checks.
- [ ] Run frontend `npm run lint` and `npm run build`.
- [ ] Start Vite and backend, use Playwright/browser smoke checks for dashboard load, refresh, event empty state, API error state, responsive layout, keyboard focus, and WebSocket status.
- [ ] Recheck changed files to confirm no unrelated frontend or backend behavior was altered.

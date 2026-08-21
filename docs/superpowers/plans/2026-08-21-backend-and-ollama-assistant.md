# Backend and Ollama Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the backend’s PRD-facing reliability and API contracts, then add a bounded local Ollama assistant that explains persisted conjunction events without replacing deterministic orbital calculations.

**Architecture:** Keep ingestion, propagation, scoring, persistence, narrative, and API modules independent. The Ollama assistant is an optional adapter behind a service boundary; it receives persisted event facts and returns a constrained operator explanation, while deterministic templates remain the fallback and source of truth.

**Tech Stack:** FastAPI, asyncpg/PostgreSQL, APScheduler, SGP4/OMM, HTTPX, LangChain `create_agent`, `langchain-ollama`, Ollama, Pydantic.

**Spec:** `PRD.md` Sections 5.1–5.4, 6, 8–10a.

## Global Constraints

- Never fabricate orbital data or risk scores; use live CelesTrak GP JSON or a URL-matched last-success cache.
- Keep screening and risk scoring deterministic; Ollama is advisory narrative only.
- Backend responses include raw numeric values and display strings together.
- Frontend files are explicitly out of scope.
- Preserve Postgres foreign keys, checks, indexes, UTC timestamps, and reversible schema changes.
- Local model defaults to Ollama `qwen3.5:9b` at `http://host.docker.internal:11434` and must fail soft when unavailable.

### Task 1: Backend contract hardening

**Files:** `backend/perigee/api/`, `backend/perigee/services/`, `backend/tests/`, `pyproject.toml`.

- [ ] Add API tests for stats, list/detail not-found behavior, object propagation, refresh `202`, and documented WebSocket message types.
- [ ] Add explicit refresh failure state and relative timestamp formatting.
- [ ] Verify Compose startup, OpenAPI, and endpoint responses against the live Postgres service.

### Task 2: Local Ollama adapter

**Files:** Create `backend/perigee/agent/ollama.py`, `backend/perigee/agent/schemas.py`, `backend/tests/test_ollama.py`; modify config and dependencies.

- [ ] Define a bounded LangChain `create_agent()` adapter using `ChatOllama`, configurable URL/model/timeout.
- [ ] Validate structured JSON output with Pydantic; reject malformed or unsupported responses.
- [ ] Return a deterministic template explanation whenever Ollama is disabled, unreachable, times out, or returns invalid JSON.
- [ ] Never send raw TLE lines or secrets; send only the already-computed event facts and factor contributions.

### Task 3: Assistant API integration

**Files:** `backend/perigee/api/routes.py`, `backend/perigee/api/schemas.py`, `backend/perigee/persistence/repository.py`, tests.

- [ ] Add `POST /api/events/{id}/explain` with `202`/bounded response semantics and a provider/source field.
- [ ] Load event facts from Postgres, call the optional Ollama adapter, and expose fallback status.
- [ ] Add request validation, 404 handling, timeout handling, and tests with mocked Ollama HTTP responses.

### Task 4: Verification and handoff

- [ ] Run Ruff, pytest, Compose config, backend container health, OpenAPI smoke checks, and Ollama-unavailable fallback tests.
- [ ] Confirm no frontend files changed.
- [ ] Report uncommitted backend-only changes separately from any user commits.

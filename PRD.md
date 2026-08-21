# Perigee — Product Requirements Document
### Satellite Conjunction (Collision Risk) Triage Assistant
**Version:** 1.1
**Prepared for:** Codex / AI coding agent implementation
**Context:** SIH 2026 internal hackathon — needs to be functional, demo-ready, and visually strong within a short build window.

---

## 0. AI Coding Agent Skill Instructions

This project is intended to be implemented with Codex using the Agent Skills ecosystem. Skills are reusable procedural instructions for the coding agent; they do **not** replace project dependencies or application code.

### 0.1 Project-local skills

Codex must use the project's local skills when implementing or modifying the relevant parts of Perigee. Project-local skills are expected under:

```text
.agents/
└── skills/
    ├── frontend-design/
    ├── react-dev/
    ├── shadcn-ui/
    ├── tailwind-v4-shadcn/
    ├── fastapi/
    ├── fastapi-templates/
    ├── docker/
    ├── docker-compose/
    ├── database-schema-designer/
    ├── testing-patterns/
    ├── code-review/
    ├── deep-debug/
    ├── project-workflow/
    ├── accessibility/
    ├── motion/
    ├── playwright-local/
    ├── langgraph-fundamentals/
    ├── langgraph-human-in-the-loop/
    ├── langgraph-persistence/
    └── perigee-*/              # project-specific skills when present
```

The canonical installation mechanism is the `skills` CLI. From the repository root, project skills can be installed with:

```bash
npx skills add <owner>/<repo> --skill <skill-name> -a codex
```

Do **not** install project skills globally unless explicitly requested. Project-local skills are preferred because they travel with the repository and keep the implementation workflow reproducible.

Before beginning implementation, Codex should inspect the available skills under `.agents/skills/` and use the most relevant skill(s) for the task at hand. If a required skill is unavailable, continue using the PRD and repository conventions rather than inventing a replacement skill.

### 0.2 Required skill usage by work area

| Work area | Preferred skills | Required behavior |
|---|---|---|
| Overall planning / implementation order | `project-workflow` | Follow the phased build plan and keep changes incremental and verifiable. |
| FastAPI backend | `fastapi`, `fastapi-templates` | Follow modular routing/service/schema patterns; do not collapse the backend into one file. |
| Database/schema | `database-schema-designer` | Validate schema, relationships, indexes, migrations, and query patterns before implementation. |
| React frontend | `react-dev` | Follow established React component/state/data-fetching patterns and keep components maintainable. |
| Visual design | `frontend-design`, `design-system`, `design-review` | Treat the mission-control UI as a product surface, not a generic admin template. |
| shadcn/ui + Tailwind | `shadcn-ui`, `tailwind-v4-shadcn` | Prefer reusable accessible primitives and a coherent design-token system. |
| Accessibility | `accessibility` | Preserve text labels, readable contrast, keyboard usability, and non-color-only risk indicators. |
| Motion | `motion` | Use restrained animation for live alerts, critical states, counters, and globe transitions. |
| Docker / Compose | `docker`, `docker-compose` | Keep services reproducible, health-checked, configurable, and suitable for one-command startup. |
| Testing / verification | `testing-patterns`, `playwright-local` | Verify backend behavior, critical calculations, API contracts, and primary UI flows. |
| Debugging | `deep-debug` | Diagnose root causes instead of patching symptoms, especially in propagation and async workflows. |
| Code review | `code-review` | Perform a review pass before declaring a milestone complete. |
| Orbital mechanics | `perigee-orbital-mechanics` when available | Treat SGP4/TLE propagation, units, timestamps, candidate filtering, and TCA calculations as numerical/physics-critical code. |
| Perigee architecture | `perigee-architecture` when available | Enforce the module boundaries and dependency direction defined in this PRD. |
| Demo reliability | `perigee-demo` when available | Prioritize cached-data fallback, deterministic demo behavior, visible loading states, and recovery from network failure. |
| Agent orchestration (LangGraph/LangChain) | `langgraph-fundamentals`, `langgraph-human-in-the-loop`, `langgraph-persistence` | Apply strictly within Section 5.6's scope and guardrails — orchestration patterns must never be used to build anything that writes to the deterministic scoring/physics pipeline (Sections 5.2–5.3) or that issues autonomous actions. |

### 0.3 Skill activation rules

1. **Use skills implicitly when the task matches their scope.** Do not wait for the user to explicitly name a skill.
2. **Use multiple skills when a task spans disciplines.** For example, a dashboard task may require `react-dev`, `frontend-design`, `shadcn-ui`, `accessibility`, and `motion`.
3. **Do not blindly apply every installed skill.** Use only the skills relevant to the current change.
4. **Project-specific skills take precedence for Perigee-specific rules.** Generic skills provide implementation guidance; the PRD and Perigee-specific skills define product constraints.
5. **Do not let a skill override this PRD's functional, numerical, safety, or architectural requirements.** This includes the AI/agentic guardrails in Section 5.6 — no skill, library convenience, or orchestration pattern may be used to introduce autonomous actions, probability claims, or a write path from the AI layer back into the deterministic engine.
6. **When a skill recommends a library or pattern that conflicts with the locked stack in Section 8, keep the locked stack unless the PRD is explicitly changed.**
7. **After substantial implementation work, run the relevant verification skill(s) before moving to the next phase.**

### 0.4 Skill-aware implementation discipline

Codex must treat the PRD, repository `AGENTS.md` (if present), and project-local skills as the primary implementation context. Before coding a phase:

1. Read the relevant PRD section(s).
2. Identify which installed skills apply.
3. Inspect the existing repository structure and code.
4. Implement the smallest coherent increment.
5. Run targeted tests/checks.
6. Review the result against the acceptance criteria and relevant skill guidance.
7. Only then proceed to the next milestone.

Skills should improve implementation quality, not become a reason to add unnecessary abstractions, dependencies, or features.

---

## 1. Product Summary

Perigee is a web application that ingests publicly available satellite orbital data (TLEs), computes close-approach ("conjunction") events between tracked objects, scores each event by real collision risk using orbital mechanics, and presents operators with a triaged, explainable list of alerts — instead of the raw flood of automated warnings that real space-traffic systems currently produce.

**Core value proposition:** Turn "1,000+ raw conjunction alerts/day" into "12 alerts that actually matter today," with a clear, physics-grounded explanation for every ranking.

**This is a working software product**, not a mockup — it must use real TLE data and real SGP4 propagation, not fabricated numbers. Visual polish is a first-class requirement (see Section 7) because this will be demoed live to a judging panel.

---

## 2. Goals & Non-Goals

### Goals
- Ingest real TLE data for a meaningful subset of tracked objects (satellites + debris).
- Compute genuine close-approach geometry (miss distance, relative velocity, time of closest approach) between object pairs using SGP4 propagation.
- Score and rank conjunction events using an explainable multi-factor risk model.
- Present results in a polished, real-time-feeling "mission control" dashboard.
- Be runnable end-to-end with a single command for demo purposes (Docker Compose).
- Be resilient in a live demo (works offline / with cached data if network fails).
- Layer optional, local AI-assisted features (natural-language explanation, per-alert recommendations, anomaly surfacing) strictly on top of the deterministic physics/scoring core — never replacing or feeding back into it (see Section 5.6).

### Non-Goals (explicitly out of scope for this build)
- No actual maneuver planning / collision avoidance recommendations (risk triage only).
- No integration with classified or restricted conjunction data (CDMs from Space-Track's private feed) — public TLE-derived screening only.
- No user authentication/multi-tenant system — single shared dashboard is fine.
- No mobile app — responsive web is sufficient.
- No production-grade uncertainty/covariance modeling (stretch goal only, not required for MVP).
- No autonomous spacecraft commands or automated maneuver/avoidance actions of any kind — this system is advisory/triage only, always human-in-the-loop (see Section 5.6 guardrails).
- No AI-generated authoritative collision probability figures — qualitative tier language only, always attributed to the deterministic scoring engine.
- No external/cloud LLM API calls — all AI features run on local Ollama inference only (see FR-32).

---

## 3. Users & Use Case

**Primary persona:** A satellite operations analyst who currently reviews a large volume of automated conjunction warnings and needs to know which ones deserve immediate attention.

**Core user flow:**
1. Analyst opens dashboard → sees a ranked list of current conjunction alerts, color-coded by risk tier (Critical / Elevated / Low).
2. Analyst clicks an alert → sees full breakdown: both objects involved, time of closest approach (TCA), miss distance, relative velocity, and a factor-by-factor explanation of why it was scored the way it was.
3. Analyst can view the conjunction geometry visually in a 3D orbit view.
4. Dashboard auto-updates as new TLE data is fetched and re-scored on a schedule.

---

## 4. System Architecture

```
[TLE Data Fetcher] --> [Object Store (Postgres)]
                              |
                              v
                  [Conjunction Screening Job]
                  (SGP4 propagation, pairwise
                   close-approach detection)
                              |
                              v
                    [Risk Scoring Engine]
                              |
                              v
                  [Conjunction Events Store]
                              |
                              v
              [FastAPI Backend (REST + WebSocket)]
                              |
                              v
                [React Dashboard Frontend]
              (list view, detail view, 3D globe,
               trend charts, live updates)
                              ^
                              |
                  [Agentic AI Layer — read-only]
              (LangGraph/LangChain over local Ollama;
               see Section 5.6 — never writes upstream)
```

---

## 5. Functional Requirements

### 5.1 Data Ingestion
- **FR-1:** System must fetch TLE data from CelesTrak (no auth required, use as primary source for demo reliability) — e.g. active satellites, debris catalogs, or a curated subset (recommend: start with a filtered set of ~200–500 objects to keep propagation fast, not the full 30,000+ object catalog).
- **FR-2:** Support optional Space-Track.org integration as a secondary/credibility source (requires free registered API credentials — store via environment variable, never hardcode).
- **FR-3:** Fetched TLEs must be parsed and stored with: NORAD ID, object name, object type (payload/debris/rocket body — CelesTrak provides this), epoch, and raw TLE lines.
- **FR-4:** Ingestion must run on a schedule (configurable, default every 2 hours) and also be manually triggerable via an API endpoint/button in the UI (for live demo purposes — "Refresh Now").
- **FR-5:** System must cache the last successful fetch to disk/DB so the demo still works if network is unavailable at judging time.

### 5.2 Conjunction Screening
- **FR-6:** For the current object set, propagate all objects forward across a configurable time window (default: next 24–48 hours) using SGP4 (`sgp4` or `skyfield` library).
- **FR-7:** For each candidate object pair, compute minimum separation distance within the window and the time at which it occurs (TCA — time of closest approach).
- **FR-8:** Flag a pair as a "conjunction event" if minimum separation falls below a configurable threshold (default: 5 km, tunable in config).
- **FR-9:** For flagged pairs, compute relative velocity at TCA.
- **FR-10:** To keep compute tractable, use a coarse-to-fine approach: coarse orbital-plane/altitude filtering first to eliminate obviously non-intersecting pairs, then fine-grained propagation only on filtered candidates. (This is a performance requirement, not just a nice-to-have — full pairwise propagation across hundreds of objects at fine time resolution will be slow otherwise.)

### 5.3 Risk Scoring
- **FR-11:** Each conjunction event must receive a composite risk score (0–100) computed from a weighted combination of:
  - Miss distance (closer = higher risk; primary factor)
  - Relative velocity at TCA (higher = higher risk)
  - Object type weighting (active payload–payload conjunctions weighted higher than debris–debris)
  - Trend across repeated screenings — if a re-screened event shows decreasing miss distance over successive runs, increase urgency
- **FR-12:** Risk score must map to a tier: **Critical** (score ≥ 75), **Elevated** (40–74), **Low** (< 40). Thresholds must be config-adjustable.
- **FR-13:** Every score must store its contributing factor breakdown (not just the final number) so the UI can render an explanation.
- **FR-14:** Scoring weights must live in a single config file/module, clearly commented, so they can be tuned quickly during the hackathon without touching core logic.

### 5.4 Backend API

**Architecture note:** Structure the backend as clearly separated modules/services (not one monolithic file) so each piece can be built, tested, and debugged independently: `ingestion/`, `propagation/`, `scoring/`, `narrative/` (see FR-21a below), `agentic/` (see Section 5.6), `api/` (routers), `websocket/`. This modularity matters more than usual here because Phase 1 (Section 10) explicitly requires verifying the math pipeline headlessly before the API layer even exists — a tangled structure would block that, and it also keeps the agentic layer physically separated from the code paths that write to `conjunction_events`.

- **FR-15:** REST endpoint: `GET /api/events` — list conjunction events, filterable by tier (`?tier=critical`), sortable by score/TCA (`?sort=score_desc`), paginated (`?page=&limit=`). Response for each event must already include the plain-language summary field (FR-21a) pre-generated — never compute narrative text on the frontend.
- **FR-16:** REST endpoint: `GET /api/events/{id}` — full detail for one event: factor breakdown object (each factor with its raw value, its contribution weight, and a plain-language caption per FR-21a), both objects' full metadata, TCA, miss distance, relative velocity, and the trend history array (for the sparkline/trend chart).
- **FR-17:** REST endpoint: `GET /api/objects/{norad_id}` — object metadata + current propagated lat/lon/altitude (for placing it correctly on the 3D globe) + object type + a short plain-language type description.
- **FR-18:** REST endpoint: `POST /api/refresh` — manually trigger a re-fetch + re-screen cycle. Must return immediately with a `202 Accepted` + job status, not block the request — frontend polls or listens on WebSocket for completion, so the "Refresh Now" button's loading state (FR-23) has something real to key off of.
- **FR-19:** REST endpoint: `GET /api/stats` — summary counts (total objects tracked, total events screened, critical/elevated/low counts, last refresh timestamp, whether currently serving cached vs. live data per NFR-2) — powers the header strip (FR-23) and the before/after screen (FR-28) in one call.
- **FR-20:** WebSocket endpoint (`/ws/events`): pushes a structured message on (a) new event created, (b) existing event's score/tier changed on re-screening, and (c) refresh cycle started/completed — each message type distinct so the frontend can decide whether to animate a new card, update an existing one, or just update the header status, rather than re-fetching everything on every message.
- **FR-21:** Auto-generated OpenAPI/Swagger docs must be enabled (FastAPI default) and left accessible at `/docs` — useful to show judges the API is real and documented.
- **FR-21a — Plain-language narrative generation service:** A dedicated backend module responsible for turning raw event data into the human-readable strings used throughout the frontend (card summary, detail headline, factor captions, trend label, comparison-style captions like the "faster than a rifle bullet" example in FR-24). This must be implemented as **template-based string generation from the actual computed values** (e.g. Python f-string templates keyed off risk tier, dominant factor, and magnitude buckets) — deterministic and fast, not an LLM call, since a demo cannot depend on external API latency or nondeterministic wording. Keep every template in one file (`narrative/templates.py` or similar) so copy can be tuned quickly without touching scoring logic. This module is arguably as important as the risk-scoring engine itself for this product's audience — treat it as a first-class backend component, not an afterthought bolted onto the API layer.
- **FR-21b:** Every API response containing a numeric field intended for direct display (miss distance, velocity, score) should also include its pre-formatted human-readable string alongside the raw number (e.g. `"miss_distance_km": 1.2, "miss_distance_display": "1.2 km"`, `"tca": "2026-08-21T03:14:00Z", "tca_display": "in 6h 12m"`) so the frontend never has to reimplement formatting/unit logic — keeps frontend and backend in sync and avoids inconsistent phrasing across screens.

### 5.5 Frontend Dashboard

**Guiding principle:** A judge or analyst with zero orbital-mechanics background should understand, within 10 seconds of looking at the screen, "how much trouble are we in right now and why." Every technical value (km, km/s, risk score) must be paired with a plain-language equivalent. Nothing on screen should require the viewer to already know what a conjunction, TCA, or miss distance is.

#### Screen 1 — Main Dashboard (landing view)

- **FR-22:** Main dashboard view: card list of current conjunction events sorted by risk score descending. Each card must show, at a glance and without clicking:
  - The two object names in plain form (e.g. "Starlink-4231" vs "COSMOS 1408 Debris") — no raw NORAD IDs as the primary label (ID can be secondary/small text).
  - A large, unmissable color-coded tier badge — not just a colored dot, but a labeled pill: CRITICAL / ELEVATED / LOW — text label always present, never color-only (accessibility + clarity for non-technical viewers).
  - A one-line plain-English summary auto-generated per event, e.g. "These two objects will pass within 1.2 km of each other in 6 hours — closer than usual and worth watching." This single sentence is the most important UI element on the whole card for a non-technical audience — prioritize getting this copy right over any other polish.
  - Miss distance and time-to-TCA shown as human units ("1.2 km apart," "in 6h 12m") not raw decimals/timestamps.
  - Risk score shown as a simple horizontal bar or gauge (0–100), not just a number — visual magnitude reads faster than digits for a non-technical viewer.
- **FR-23:** Header/summary bar, styled like a "mission status" strip, containing:
  - Big animated counters: Objects Tracked, Events Screened, Critical / Elevated / Low counts — each with a short label underneath explaining what it means in plain terms (e.g. under "Events Screened": "Every pair of objects we checked for a close pass").
  - Last refresh timestamp in relative form ("Updated 4 minutes ago") not raw ISO timestamp.
  - A prominent, clearly-labeled "Refresh Now" button with a loading state (spinner + "Screening in progress...") so clicking it visibly does something during a live demo.
  - A small "using cached data" indicator (per NFR-2) that only appears when live fetch has failed — styled as informative, not alarming (e.g. muted gray badge, not red).
- **FR-23a — First-time / empty-state guidance:** On first load (or if there are zero flagged events), show a short explanatory banner instead of a blank screen: what this tool does, in one or two sentences, e.g. "Perigee checks thousands of satellite and debris positions for close passes and shows you which ones actually need attention." This matters specifically because non-technical judges may land on the dashboard with no verbal walkthrough.
- **FR-23b — Persistent "What am I looking at?" help affordance:** A small, always-visible "?" icon in the header that opens a lightweight tooltip/panel explaining the core concept in one paragraph and defining the three tier colors. This is a safety net for a judge who wanders onto the dashboard without a live narrator.

#### Screen 2 — Event Detail View (modal or slide-in side panel, not a full page navigation — must stay contextual)

- **FR-24:** Triggered by clicking any event card. Must include, top to bottom:
  1. Headline plain-English sentence (same style as the card summary, but slightly more detailed) — this stays visible/pinned even as the user scrolls the rest of the panel.
  2. The two objects, each with: name, type (active satellite / debris / rocket body — shown as a simple icon + label), and why that type matters in one short phrase (e.g. "Active satellites can maneuver to avoid a collision — debris cannot."). This single line does a lot of work in making the risk model feel intuitive rather than arbitrary.
  3. Key numbers panel, laid out like a simple stat grid (not a dense table): Miss Distance, Relative Velocity, Time to Closest Approach — each with the raw number AND a one-line "what this means" caption underneath (e.g. under relative velocity: "Faster than a rifle bullet — even a small object at this speed can cause serious damage."). These comparison-style captions are cheap to write and dramatically increase how "graspable" the numbers feel to a non-technical viewer.
  4. "Why was this flagged?" factor breakdown chart — a horizontal bar chart (Recharts) showing each contributing factor (distance, velocity, object type, trend) as a labeled bar, with the highest-contributing factor visually emphasized. Above the chart, one sentence stating the single biggest driver in plain terms, e.g. "This was flagged mainly because of how close the pass is — not the speed or object type." This is the single highest-value piece of UI in the entire product for demonstrating "explainable, not black-box," and should get disproportionate design attention.
  5. Mini 3D view — zoomed-in orbital visualization showing just this pair's trajectories converging, with a marker at the TCA point.
  6. Trend sparkline — small inline chart (not the full trend view) showing whether this event's risk has been rising or falling across recent screenings, with a short label above it ("Trending: Worsening" / "Trending: Stable" / "Trending: Improving") rather than requiring the viewer to read the line direction themselves.
  7. AI triage recommendation (see FR-42) — a short, clearly-tagged AI-assisted suggestion, distinct from the deterministic content above it.

#### Screen 3 — 3D Orbital View (embedded on main dashboard, expandable to full view)

- **FR-25:** A rotating globe (react-globe.gl baseline) showing tracked objects as small points, colored by object type. The currently-selected or highest-risk conjunction pair is visually highlighted — pulsing red markers connected by a line, camera auto-focuses/zooms toward that pair when an event card is clicked.
- **FR-25a:** Include a simple legend overlay (small, corner-positioned, non-intrusive) explaining the dot colors/icons — again, assume zero prior knowledge.
- **FR-25b:** Provide a basic "orbit view" vs "top-down globe view" toggle if time permits — optional polish, not required for MVP, but a strong visual moment if included.

#### Screen 4 — Trend / History View (secondary screen, can be a tab or expandable section rather than a separate route)

- **FR-26:** Line chart of risk score history for a given event across repeated screenings, with plain axis labels (not raw field names) and a short caption stating the takeaway in words above the chart.

#### Cross-cutting frontend requirements

- **FR-27:** Live updates: dashboard must visually reflect new data pushed via WebSocket without requiring a manual page refresh — new/updated alert cards animate in (Framer Motion slide/fade), and a brief, non-intrusive toast/banner announces it in plain language (e.g. "New close pass detected — Starlink-4231 vs debris object"), so a non-technical viewer doesn't need to notice a subtle list re-sort to realize something changed.
- **FR-28:** "Before/After" toggle or split panel: a large, simple visual — left side "1,247 raw alerts" (grayed out, overwhelming-looking list), right side "8 that actually need your attention" (clean, colored). This single screen should be treated as the product's core "elevator pitch," and should require zero explanation to land with a non-technical viewer — this is the highest-leverage screen for judge persuasion and deserves dedicated design/build time, not a quick afterthought.
- **FR-29:** Dark, "mission control" visual theme (see Section 7). Additionally: maintain generous whitespace and large touch/click targets, avoid dense multi-column data tables anywhere in the primary flow (tables read as "technical/intimidating" to non-technical viewers — prefer cards, bars, and plain sentences over grids of numbers), and cap the amount of raw numeric data shown without a plain-language caption next to it.
- **FR-30:** All jargon (TCA, NORAD ID, RCS, SGP4, etc.) must appear only as secondary/small text, never as a primary label, and should have a hover/tap tooltip with a one-line definition wherever it does appear.
- **FR-31:** Responsive down to a reasonably small laptop screen at minimum (judging setups are often a shared external display or a laptop, not a large monitor) — verify the main dashboard and detail panel both remain legible without horizontal scrolling at common presentation resolutions (1366×768 and 1920×1080).

---

### 5.6 Agentic Features (AI Layer)

**Design principle governing this entire section (non-negotiable):** Orbital physics and risk scoring remain fully deterministic (per Section 5.2 and 5.3 — SGP4 propagation and the weighted scoring engine). The AI/agentic layer sits strictly *on top of* that deterministic core as a read-only interpretation and assistance layer. AI is used only where it is genuinely useful — natural-language explanation, learning-to-rank refinement, and anomaly detection — never to compute or alter the core physics or the primary risk score itself.

**Hard guardrails (apply to every agentic feature below, no exceptions):**
- **No autonomous spacecraft commands, ever.** The system never issues, simulates issuing, or drafts machine-executable maneuver/avoidance commands. It may only describe triage priority and suggest that a human review something.
- **No authoritative collision probability claims.** The agent must never state or imply a precise probability of collision (e.g. "73% chance of collision"). It may describe qualitative risk tier and contributing factors only, using the same tier language as the deterministic scoring engine (Critical/Elevated/Low), and must always attribute the tier and score to the deterministic engine, not to itself.
- **Human-in-the-loop by design.** Every agentic output is advisory text for a human to read and act on — never an action the system takes on its own (no auto-escalation, no auto-notification-send without a human clicking confirm, no auto-anything that changes system state beyond generating a suggestion).
- **Every AI-generated statement in the UI must be visually distinguishable** from deterministic system output (e.g. a small "AI-assisted" tag/icon on any agent-generated text block) so a viewer always knows which numbers are hard physics/math and which text is model-generated interpretation. This is both a responsible-design requirement and a good demo talking point ("we're transparent about what's deterministic vs. AI-assisted").
- **Agents only ever read from the API** (`GET` endpoints) for their context — they must never have write access to `objects`, `conjunction_events`, or trigger a re-screening cycle themselves. Only a human clicking "Refresh Now" (FR-18) can trigger re-computation.

#### 5.6.1 Local Inference Setup

- **FR-32:** All agentic/LLM features run **fully locally** via **Ollama**, using the **`qwen3.5:9b`** model for fast local inference — no external LLM API calls, no data leaving the local machine. This must be true both for reliability (no network dependency during a live demo) and for a clean "your orbital data never leaves your machine" story.
- **FR-33:** The backend must expose a thin internal Ollama client wrapper (`agentic/llm_client.py` or similar) so the model name/endpoint is configured in one place (`OLLAMA_BASE_URL`, `OLLAMA_MODEL` env vars) — never hardcoded inline in agent logic, so swapping models later is a one-line config change.
- **FR-34:** Include a startup health check that pings the local Ollama instance; if unreachable, the agentic features should degrade gracefully — UI shows an "AI features unavailable" state on the relevant components, while the deterministic dashboard (Sections 5.2–5.5) continues to work fully unaffected. This is the same fallback philosophy as NFR-2's cached-data behavior, applied to the AI layer.

#### 5.6.2 Orchestration Framework

- **FR-35:** Use **LangGraph** as the primary orchestration layer for any agentic feature involving multi-step reasoning or tool use (e.g. the query agent needing to decide which API endpoint to call before answering). Use plain **LangChain** primitives (prompt templates, output parsers) for simpler single-shot features (e.g. the per-alert recommendation, which doesn't need graph-based branching). Don't force LangGraph onto features that are genuinely single-call — keep the simplest tool that does the job, since build speed matters here.
- **FR-36:** All agent prompts must be stored as versioned template files in one directory (`agentic/prompts/`), not inlined as strings scattered through the codebase — mirrors the FR-21a requirement for the deterministic narrative templates, and keeps prompt iteration fast during the hackathon.
- **FR-37:** Every agent must be given its readable context **explicitly** (the relevant event JSON, factor breakdown, trend history — pulled via the existing REST endpoints) rather than free-roaming tool access to the whole database. Scope each agent's context tightly to what it needs to answer the specific question, both for speed (smaller context = faster local inference) and for safety (agent can't reference or hallucinate about data it wasn't given).

#### 5.6.3 Feature 1 — "Ask Perigee" Natural-Language Query Bar

- **FR-38:** A query input on the main dashboard where a user can ask plain-English questions about current screening results (e.g. "Which alerts involve debris?", "What's the most urgent thing right now?", "Explain this alert simply").
- **FR-39:** Implementation: LangGraph agent with a small toolset limited to read-only wrappers around `GET /api/events`, `GET /api/events/{id}`, and `GET /api/stats` — the agent decides which tool(s) to call based on the question, retrieves real data, then generates a grounded natural-language answer. The agent must be prompted explicitly to answer only from retrieved data and to say "I don't have enough information to answer that" rather than guessing, if the data doesn't support an answer.
- **FR-40:** Backend endpoint: `POST /api/agent/query` — accepts `{ "question": string }`, returns `{ "answer": string, "referenced_event_ids": [...] }` so the frontend can optionally deep-link the answer to the specific event cards it referenced (nice touch: clicking a referenced event ID in the AI's answer scrolls to/opens that card).
- **FR-41:** Response time target: under ~5 seconds on local `qwen3.5:9b` inference for a typical query — validate this early in the build (Phase 1 or 2, not left until the end) since local model speed on the actual demo hardware needs to be confirmed, not assumed.

#### 5.6.4 Feature 2 — Per-Alert Triage Recommendation

- **FR-42:** On the event detail view (Screen 2, Section 5.5, item 7), an AI-generated one-to-two-sentence triage suggestion — e.g. "This pairing has stayed at Elevated risk for two consecutive screenings without worsening — recommend routine monitoring, no immediate escalation needed." Must be phrased as a *recommendation for human judgment*, never a directive or automated action, and must explicitly avoid numeric probability claims per the guardrails above.
- **FR-43:** Implementation: simple LangChain prompt template (no LangGraph needed — single-shot, given the event's factor breakdown + tier + trend as context) run through the local Ollama model.
- **FR-44:** Backend endpoint: `GET /api/events/{id}/recommendation` — generated on-demand when the detail panel opens (not precomputed for every event on every screening cycle, to keep the deterministic pipeline in Section 10/Phase 1 fully independent of AI availability) — cache the result per event per screening cycle so re-opening the same event doesn't re-run inference unnecessarily.

#### 5.6.5 Feature 3 — Anomaly / Pattern Detection (stretch, build if time allows after 5.6.3–5.6.4 are solid)

- **FR-45:** A periodic (or on-demand) agent pass over recent `event_history` data that surfaces plain-language observations a human might miss — e.g. "Object COSMOS-1408 debris has appeared in 3 separate conjunction events this week, more than any other object" or "Risk scores in this batch have trended upward over the last 3 screenings." This must be framed strictly as descriptive pattern-surfacing, not predictive/probabilistic claims.
- **FR-46:** Implementation: LangGraph agent that queries `event_history` aggregates (via a small set of read-only summary tool calls, e.g. "get objects appearing in multiple events this week," "get events with worsening trend") and synthesizes findings into 2–4 short bullet observations.
- **FR-47:** Backend endpoint: `GET /api/agent/insights` — returns a small list of `{ observation: string, related_event_ids: [...] }`. Surfaced on the dashboard as a small "Noticed something" panel, visually tagged as AI-assisted per the guardrails above.

#### 5.6.6 Optional/Future — Learning-to-Rank Refinement (explicitly optional, not required for MVP)

- **FR-48 (optional):** If time allows, an optional learning-to-rank layer may re-order events *within* their deterministically-assigned tier (never across tiers — a Low event must never be reranked into Critical by this layer) based on historical patterns of which factor combinations tend to matter most. This must be clearly labeled in the UI as an optional refinement (e.g. a toggle: "Use AI-assisted ranking within tiers") that a user can switch off to see the pure deterministic order — never silently replacing the deterministic ranking.
- **FR-49 (optional):** If built, keep this simple (e.g. a lightweight scikit-learn model, not deep learning) and train it only on data generated within this project (screening history), never external/unrelated datasets — and clearly document that it's a ranking *refinement* layer, not a replacement for FR-11's scoring engine.

#### 5.6.7 Explicit Non-Goals for the Agentic Layer

To keep this section aligned with the stated design principles and prevent scope creep during the build:
- No agent output is ever used as an input to the deterministic risk scoring engine (Section 5.3) — the data flow is one-directional: deterministic engine → AI layer, never the reverse. This keeps FR-11 through FR-14's scoring pipeline fully explainable and auditable independent of any LLM behavior.
- No fine-tuning or training of the local model — use `qwen3.5:9b` as-is via prompting only; model training/fine-tuning is out of scope for the hackathon timeframe.
- No agent is given the ability to call `POST /api/refresh` or any other state-changing endpoint.
- No multi-agent "autonomous negotiation" or agent-to-agent action chains that result in system state changes without a human click in between.

---

## 6. Non-Functional Requirements

- **NFR-1 (Performance):** Full screening cycle for the default object set (~200–500 objects) must complete in under 60 seconds so the "Refresh Now" demo moment doesn't stall.
- **NFR-2 (Reliability/demo safety):** App must degrade gracefully — if live TLE fetch fails, fall back to last cached dataset and show a subtle "using cached data" indicator rather than breaking.
- **NFR-3 (Deployability):** Entire stack (backend, frontend, DB, redis) must run via a single `docker-compose up`.
- **NFR-4 (Explainability):** No risk score may be shown without an accompanying factor breakdown — black-box numbers are not acceptable per product philosophy.
- **NFR-5 (Config-driven):** Screening threshold, risk weights, tier cutoffs, refresh interval, and object set filters must all be adjustable via a single config file/env vars, not hardcoded in logic.
- **NFR-6 (Accuracy honesty):** UI copy must not overstate precision — this is a *screening/triage* tool using public TLE data (which has known accuracy limitations vs. precision tracking), not an operational collision-avoidance system. Include a small disclaimer in the UI footer.
- **NFR-7 (AI availability independence):** The deterministic dashboard (Sections 5.2–5.5) must be fully functional with the agentic layer (Section 5.6) completely disabled or unreachable — the AI layer is additive, never a dependency of the core product.

---

## 7. Design & Visual Requirements (High Priority for Demo)

This will be judged partly on visual impact by a panel that may not be deeply technical, so invest real effort here.

- **Theme:** Dark background, high-contrast "mission control" aesthetic — think satellite operations center, not a generic admin dashboard.
- **Typography:** Technical/monospace accents for data (IDs, coordinates, timestamps); clean sans-serif for body text.
- **Color coding:** Consistent risk-tier colors throughout — red (Critical), amber (Elevated), green (Low) — used in badges, chart lines, and 3D highlight markers.
- **Motion:** Subtle animations for incoming alerts (slide/fade in), pulsing effect on critical risk badges, smooth camera movement in the 3D globe view when focusing on a selected event. Use Framer Motion for UI animation.
- **3D globe centerpiece:** This is the single most important visual element for judge impact. Use `react-globe.gl` (fast to implement, good visual payoff) as the baseline; upgrade to CesiumJS only if time permits, as it has a steeper integration cost.
- **Charts:** Use Recharts for the factor-breakdown and trend charts — clean, readable, no need for custom D3 unless time allows.
- **Component library:** Use shadcn/ui + TailwindCSS for fast, polished, accessible UI primitives (cards, modals, badges, tooltips).
- **Header stat strip:** Large animated counters for "Objects Tracked," "Events Screened Today," "Critical Alerts" — this kind of dashboard summary reads as "serious infrastructure" at a glance, which matters for non-technical judges.
- **AI-assisted content styling:** Any AI-generated text block (query answers, per-alert recommendations, insights) uses a visually distinct treatment (e.g. a subtle accent border/icon + "AI-assisted" microlabel) so it never gets mistaken for deterministic system output — see Section 5.6 guardrails.

---

## 8. Tech Stack (Final)

| Layer | Technology |
|---|---|
| Data source | CelesTrak (primary), Space-Track.org (optional secondary) |
| Orbital mechanics | Python `sgp4`, `skyfield` |
| Backend | FastAPI (Python), async |
| Database | PostgreSQL — run locally as a Docker container from the start (see Phase 0), not a bare local install |
| Cache / pub-sub | Redis |
| Scheduling | APScheduler (simpler than Celery for hackathon timeframe) |
| Real-time push | WebSockets (native FastAPI support) |
| Frontend framework | React + Vite |
| Styling | TailwindCSS + shadcn/ui |
| 3D visualization | react-globe.gl (baseline), CesiumJS (stretch) |
| Charts | Recharts |
| Animation | Framer Motion |
| Local LLM inference | Ollama, running `qwen3.5:9b` — fully local, no external API calls |
| Agent orchestration | LangGraph (multi-step/tool-using agents) + LangChain (simple single-shot prompt features) |
| Containerization | Docker + docker-compose |
| Agent container tooling | Docker MCP plugin/server (installed locally so the coding agent can manage containers directly during development) |
| Deployment (demo) | Render / Railway (backend), Vercel (frontend) |

> **Agent skills note:** Skills listed in Section 0 are development-time procedural context for Codex. They are not runtime dependencies and must not be added to the application's Python or Node dependency manifests merely because they are installed in `.agents/skills/`.

---

## 9. Data Model (initial schema sketch)

**`objects`**
- `norad_id` (PK)
- `name`
- `object_type` (payload / debris / rocket_body)
- `tle_line1`, `tle_line2`
- `epoch`
- `last_updated`

**`conjunction_events`**
- `id` (PK)
- `object_a_id` (FK → objects.norad_id)
- `object_b_id` (FK → objects.norad_id)
- `tca` (timestamp — time of closest approach)
- `miss_distance_km`
- `relative_velocity_kmps`
- `risk_score` (0–100)
- `risk_tier` (critical / elevated / low)
- `factor_breakdown` (JSON — stores individual factor contributions)
- `screened_at` (timestamp of this screening run)

**`event_history`** (for trend charting)
- `event_id` (FK → conjunction_events.id, or a stable pair-hash key so repeated screenings of the same pair link together)
- `screened_at`
- `risk_score`
- `miss_distance_km`

**`agent_recommendations`** (cache for FR-44, avoids re-running inference on every panel open)
- `event_id` (FK → conjunction_events.id)
- `screened_at` (the screening cycle this recommendation was generated for)
- `recommendation_text`
- `generated_at`

> Note: this table is populated only by the agentic layer's own on-demand generation path (FR-44) — nothing in Sections 5.1–5.3's deterministic pipeline reads from or writes to it, preserving the one-directional data flow required in Section 5.6.7.

---

## 10. Build Plan / Milestones (suggested for hackathon timeframe)

**Phase 0 — Environment setup (do this before any application code)**
**Skills:** `project-workflow`, `docker`, `docker-compose`, `database-schema-designer`
0a. Install and configure the Docker MCP plugin/server locally so the coding agent can create, inspect, and manage containers directly (start/stop services, check logs, rebuild images) instead of requiring manual shell intervention for every Docker action. This should be set up first since every later phase depends on containerized services.
0b. Stand up a local PostgreSQL instance as a Docker container (not a bare local install) — this becomes the persistent dev database for the `objects`, `conjunction_events`, and `event_history` tables defined in Section 9, and later folds directly into the full `docker-compose.yml` stack from NFR-3 rather than being a throwaway setup.
   - Define the Postgres service in a `docker-compose.yml` from the start (even before other services exist), with a named volume for data persistence across container restarts, and environment variables for `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` (kept in a local `.env` file, not hardcoded/committed).
   - Verify connectivity (e.g. via `psql` or the Postgres MCP server, if installed) before writing any application code against it — confirm the container starts cleanly, is reachable on the expected port, and persists data across a container restart.
   - This same Postgres service definition should be reused as-is when Redis, backend, and frontend services are added to the compose file later in Phase 5, so there's no rework — get the schema and container config right once here.

**Phase 1 — Core data + math pipeline (get this working first, headless, no UI)**
**Skills:** `project-workflow`, `deep-debug`, `testing-patterns`, `perigee-orbital-mechanics` (if installed)
1. TLE fetcher from CelesTrak → store in the Dockerized Postgres instance from Phase 0.
2. SGP4 propagation for object set + pairwise coarse filtering.
3. Fine-grained close-approach detection → populate `conjunction_events`.
4. Risk scoring engine with factor breakdown.
5. Verify with a script/CLI output before touching the API — confirm the math produces sane, explainable results.

**Phase 2 — API layer**
**Skills:** `fastapi`, `fastapi-templates`, `testing-patterns`, `deep-debug`
6. FastAPI endpoints per Section 5.4.
7. WebSocket push on new event creation.
8. APScheduler wiring for periodic refresh + manual refresh endpoint.

**Phase 3 — Frontend core**
**Skills:** `react-dev`, `frontend-design`, `shadcn-ui`, `tailwind-v4-shadcn`, `accessibility`, `testing-patterns`
9. Dashboard list view + stat header, wired to REST API.
10. Event detail view with factor breakdown chart.
11. WebSocket client integration for live updates.

**Phase 4 — Visual centerpiece**
**Skills:** `frontend-design`, `react-dev`, `motion`, `design-system`, `design-review`, `accessibility`
12. 3D globe integration (react-globe.gl) with object markers + orbit paths.
13. Highlight/focus behavior for selected conjunction event.
14. Dark theme + animation pass (Framer Motion) across all views.

**Phase 5 — Demo hardening**
**Skills:** `docker`, `docker-compose`, `playwright-local`, `testing-patterns`, `code-review`, `deep-debug`, `perigee-demo` (if installed)
15. Cached-data fallback if live fetch fails.
16. Docker Compose for one-command spin-up.
17. Seed/demo dataset locked in ahead of time as a safety net in case live data or network is unreliable during judging.
18. Final UI polish pass — stat counters, before/after toggle, disclaimer copy.

**Phase 6 — Agentic AI layer (build last, only once Phases 1–5 are solid — see Section 5.6)**
**Skills:** `langgraph-fundamentals`, `langgraph-human-in-the-loop`, `langgraph-persistence`, `fastapi`, `testing-patterns`, `deep-debug`, `code-review`
19. Set up local Ollama with `qwen3.5:9b`, wire up the `llm_client.py` wrapper and health check (FR-32–FR-34).
20. Build Feature 2 first (per-alert triage recommendation, FR-42–FR-44) — it's the simpler single-shot LangChain implementation, good for validating local inference speed and prompt quality before investing in LangGraph.
21. Build Feature 1 ("Ask Perigee" query bar, FR-38–FR-41) — LangGraph agent with read-only tool access.
22. Add the "AI-assisted" visual tagging across the UI wherever agent output appears (guardrail requirement, Section 5.6).
23. If time remains: Feature 3 (anomaly/pattern detection, FR-45–FR-47), then the optional learning-to-rank refinement (FR-48–FR-49) last, since both are explicitly stretch scope.

---

## 10a. Skill-Aware Quality Gates

Each phase must have a verification pass before the next phase begins.

### Gate A — Environment

- Confirm project-local skills are present under `.agents/skills/`.
- Confirm Docker Compose starts PostgreSQL successfully.
- Confirm database persistence across a container restart.
- Use the infrastructure/database skills where applicable.

### Gate B — Orbital math

- Run the propagation/screening pipeline headlessly before relying on the API or UI.
- Validate TLE parsing, UTC timestamps, units, SGP4 propagation, coarse filtering, fine screening, TCA, miss distance, relative velocity, and risk-factor calculations.
- Test edge cases and inspect numerical outputs for obvious physical/numerical errors.
- Use `perigee-orbital-mechanics`, `deep-debug`, and `testing-patterns` when installed.

### Gate C — API

- Verify every required endpoint and response shape from Section 5.4.
- Verify asynchronous refresh behavior and WebSocket messages.
- Verify OpenAPI documentation at `/docs`.
- Use `fastapi`, `fastapi-templates`, and testing skills.

### Gate D — Frontend

- Verify the main dashboard, event detail panel, live updates, factor chart, trend chart, and 3D globe.
- Verify that technical values always have plain-language context.
- Verify accessibility requirements, including labeled risk tiers and non-color-only meaning.
- Use `react-dev`, `frontend-design`, `shadcn-ui`, `tailwind-v4-shadcn`, `accessibility`, and `motion` as applicable.

### Gate E — Demo readiness

- Run the complete stack through Docker Compose.
- Test live refresh and cached-data fallback.
- Run the primary user flow from dashboard → event detail → 3D focus → refresh.
- Verify the application remains usable at 1366×768 and 1920×1080.
- Perform a final code-review and browser verification pass.
- Use `playwright-local`, `testing-patterns`, `code-review`, `deep-debug`, `docker`, and `docker-compose` as applicable.

### Gate F — Agentic layer

- Confirm the Ollama health check works and the AI layer degrades gracefully when Ollama is stopped (dashboard remains fully functional per NFR-7).
- Confirm no agent has write access to `objects`, `conjunction_events`, or `POST /api/refresh` — inspect the agent tool definitions directly, don't just test happy-path behavior.
- Confirm every AI-generated text block is visually tagged as AI-assisted and is visually distinct from deterministic content.
- Spot-check agent outputs across several events for guardrail violations: no probability figures, no directive/command language, no claims not grounded in the retrieved data.
- Confirm `POST /api/agent/query` and `GET /api/events/{id}/recommendation` respond within the target latency (FR-41) on the actual demo hardware.
- Use `langgraph-fundamentals`, `langgraph-human-in-the-loop`, `deep-debug`, `testing-patterns`, and `code-review`.

---

## 11. Acceptance Criteria (MVP "done" definition)

- [ ] App boots fully via `docker-compose up` with no manual steps.
- [ ] Real TLE data is fetched and visible in the dashboard (not mock data).
- [ ] At least one genuine conjunction event is detected and scored from real propagated orbits.
- [ ] Every displayed risk score has a visible factor breakdown.
- [ ] Dashboard updates live (via WebSocket) when a manual refresh is triggered.
- [ ] 3D globe renders tracked objects and highlights the selected conjunction event.
- [ ] App still functions (using cached data) if network access is cut mid-demo.
- [ ] Swagger/OpenAPI docs are accessible at `/docs`.
- [ ] A person with no orbital-mechanics background can look at the main dashboard, unprompted, and correctly state which alert is most urgent and roughly why — validate this with at least one genuine non-technical reviewer (a teammate outside the core dev team, a friend, etc.) before the demo, not just the build team.
- [ ] Every risk score, miss distance, velocity, and TCA visible anywhere in the UI has an accompanying plain-language caption or display string — no raw unexplained numbers.
- [ ] All AI-generated text is visually tagged as AI-assisted and distinguishable from deterministic system output.
- [ ] The deterministic dashboard (screening, scoring, event list, 3D globe) functions fully and correctly even with Ollama/the AI layer completely stopped or unreachable.
- [ ] No agent-generated text anywhere in the app states or implies a numeric collision probability, and no UI element allows issuing or simulating a spacecraft command.
- [ ] All LLM inference runs against the local Ollama endpoint only — confirm no outbound calls to external LLM APIs occur (e.g. by checking network activity with the AI features in use).

---

## 12. Open Questions / Assumptions to Confirm Before/During Build

- **Object set size for demo:** recommend starting with a curated ~200–300 object subset (mix of active payloads + debris in similar altitude bands) rather than the full catalog, to guarantee real conjunctions show up without needing to screen tens of thousands of objects. Codex should pick a sensible filtered CelesTrak group (e.g. "active satellites" + a debris group) and make this configurable.
- **Screening threshold tuning:** 5 km default miss-distance threshold may need adjusting based on how many events it surfaces in practice — should be trivially configurable, not hardcoded.
- **Space-Track credentials:** optional — if not provided, system should run entirely on CelesTrak with no degraded functionality (this must not be a hard dependency).
- **Local Ollama/`qwen3.5:9b` performance on demo hardware:** validate actual response latency early (Phase 6, step 19–20) rather than assuming the FR-41 target holds — if the demo machine is underpowered, consider a smaller/quantized model as a fallback, but keep it local per FR-32's non-goal on external calls.

---

**End of PRD.** This document is intended to be handed directly to an AI coding agent (Codex) as the primary build spec. Section 10 (Build Plan) should be treated as the implementation order, and Section 10a's gates should be treated as mandatory checkpoints between phases.
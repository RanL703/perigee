import { useCallback, useEffect, useState } from "react";
import {
  api,
  type Config,
  type EventDetail,
  type EventSummary,
  type Insights,
  type ObjectListItem,
  type PropagatedObject,
  type QueryResult,
  type Stats,
  websocketUrl,
} from "./lib/api";
import "./App.css";
import { settingsStore, useSettings } from "./lib/settings";

type Page = "Dashboard" | "Objects" | "Screening" | "Risk Analysis" | "Propagation" | "Settings";
const navItems: Page[] = ["Dashboard", "Objects", "Screening", "Risk Analysis", "Propagation"];

function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [socketState, setSocketState] = useState("connecting");
  const [toast, setToast] = useState<string | null>(null);
  const [settings, updateSettings] = useSettings();

  const loadDashboard = useCallback(async () => {
    try {
      const [nextStats, nextEvents] = await Promise.all([api.stats(), api.events(100)]);
      setStats(nextStats);
      setEvents(nextEvents.items);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Backend unavailable");
    }
  }, []);

  // The initial fetch synchronizes React state with the external FastAPI store.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    let socket: WebSocket | undefined;
    let retry: number | undefined;
    let stopped = false;
    const connect = () => {
      socket = new WebSocket(websocketUrl());
      socket.onopen = () => setSocketState("live");
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as { type: string; payload?: Record<string, unknown> };
        if (event.type === "refresh_started") setRefreshing(true);
        if (event.type === "refresh_failed") {
          setRefreshing(false);
          const detail = typeof event.payload?.error === "string" ? ` — ${event.payload.error}` : "";
          setToast(`Screening failed${detail}`);
        }
        if (["refresh_completed", "refresh_failed", "event_created", "event_updated"].includes(event.type)) {
          if (event.type === "refresh_completed") setRefreshing(false);
          void loadDashboard();
        }
        if (
          settingsStore.get().liveToasts &&
          ["event_created", "event_updated"].includes(event.type) &&
          typeof event.payload?.object_a === "string"
        ) {
          setToast(
            `${event.type === "event_created" ? "New close pass detected" : "Event re-scored"} — ${event.payload.object_a} × ${String(event.payload.object_b)} (${String(event.payload.risk_tier)})`,
          );
        }
      };
      socket.onclose = () => {
        setSocketState("offline");
        if (!stopped) retry = window.setTimeout(connect, 3000);
      };
      socket.onerror = () => setSocketState("offline");
    };
    connect();
    return () => {
      stopped = true;
      if (retry) window.clearTimeout(retry);
      socket?.close();
    };
  }, [loadDashboard]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await api.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Refresh failed");
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (settings.autoRefreshMinutes <= 0) return;
    const interval = window.setInterval(() => void refresh(), settings.autoRefreshMinutes * 60_000);
    return () => window.clearInterval(interval);
     
  }, [settings.autoRefreshMinutes]);

  const navigate = (item: Page) => {
    setPage(item);
    setSidebarOpen(false);
  };

  return (
    <div className={`app ${sidebarOpen ? "sidebar-open" : ""} ${settings.compactTables ? "compact-tables" : ""}`}>
      <button
        className="mobile-menu-button"
        onClick={() => setSidebarOpen((open) => !open)}
        aria-label="Toggle navigation"
        aria-expanded={sidebarOpen}
      >
        ☰
      </button>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">P</div>
          <span>PERIGEE</span>
        </div>
        <nav>
          {navItems.map((item) => (
            <button key={item} className={`nav-item ${page === item ? "active" : ""}`} onClick={() => navigate(item)}>
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className={`nav-item ${page === "Settings" ? "active" : ""}`} onClick={() => navigate("Settings")}>
            Settings
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">ORBITAL SAFETY SYSTEM</p>
            <h1>Perigee {page}</h1>
          </div>
          <div className={`status ${socketState !== "live" ? "status-muted" : ""}`}>
            <span className="status-dot" />
            {refreshing ? "Screening in progress…" : socketState === "live" ? "Live telemetry" : "Backend reconnecting"}
          </div>
        </header>
        {error && (
          <div className="backend-alert" role="alert">
            Backend connection issue: {error}
          </div>
        )}
        {toast && (
          <div className="toast" role="status">
            ◈ {toast}
          </div>
        )}
        {page === "Dashboard" && <Dashboard stats={stats} events={events} refreshing={refreshing} onRefresh={refresh} onSelect={setSelectedId} aiEnabled={settings.aiAssistance} />}
        {page === "Objects" && <ObjectsPage stats={stats} />}
        {page === "Screening" && <ScreeningPage stats={stats} events={events} refreshing={refreshing} onRefresh={refresh} onSelect={setSelectedId} />}
        {page === "Risk Analysis" && <RiskAnalysisPage stats={stats} events={events} onSelect={setSelectedId} />}
        {page === "Propagation" && <PropagationPage />}
        {page === "Settings" && <SettingsPage settings={settings} onUpdate={updateSettings} />}
      </main>
      {selectedId && (
        <EventDrawer key={selectedId} eventId={selectedId} onClose={() => setSelectedId(null)} aiEnabled={settings.aiAssistance} />
      )}
    </div>
  );
}

const byScoreDesc = (a: EventSummary, b: EventSummary) =>
  b.risk_score - a.risk_score || a.tca.localeCompare(b.tca);

function Dashboard({ stats, events, refreshing, onRefresh, onSelect, aiEnabled }: {
  stats: Stats | null;
  events: EventSummary[];
  refreshing: boolean;
  onRefresh: () => void;
  onSelect: (id: string) => void;
  aiEnabled: boolean;
}) {
  const ranked = [...events].sort(byScoreDesc);
  const criticalCount = ranked.filter((event) => event.risk_tier === "critical").length;
  return (
    <>
      <section className="stats">
        <StatCard label="Tracked Objects" value={stats?.objects_tracked} hint={stats?.data_source === "cache" ? "Serving cached catalog" : "Live catalog"} />
        <StatCard label="Active Conjunctions" value={stats?.events_screened} hint="Deterministic screening results" />
        <StatCard label="Critical Alerts" value={criticalCount || stats?.critical_count} hint="Requires analyst attention" accent="critical" />
        <StatCard label="Last Refresh" value={stats?.last_refresh_display ?? "Never"} hint={refreshing ? "Screening in progress" : "Refresh Now is available"} />
      </section>

      <section className="content-grid">
        <div className="panel large">
          <div className="panel-header">
            <div>
              <p className="eyebrow">ORBITAL OVERVIEW</p>
              <h2>Live screening picture</h2>
            </div>
            <button className="outline-btn" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? "Screening…" : "Refresh now"}
            </button>
          </div>
          <OrbitView events={ranked} onSelect={onSelect} />
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">RISK MONITOR</p>
              <h2>Priority events</h2>
            </div>
          </div>
          {ranked.length ? (
            <div className="event-list">
              {ranked.slice(0, 6).map((event) => (
                <EventRow key={event.id} event={event} onClick={() => onSelect(event.id)} />
              ))}
            </div>
          ) : (
            <EmptyState message="No conjunctions in the current screen" />
          )}
        </div>
      </section>

      {aiEnabled && <AgentPanel events={ranked} onSelect={onSelect} />}

      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Latest screenings</h2>
          </div>
        </div>
        {ranked.length ? <EventTable events={ranked} onSelect={onSelect} /> : <EmptyTable message="The backend has not recorded a flagged close approach yet." />}
      </section>
    </>
  );
}

function OrbitView({ events, onSelect }: { events: EventSummary[]; onSelect: (id: string) => void }) {
  const counts = {
    critical: events.filter((event) => event.risk_tier === "critical").length,
    elevated: events.filter((event) => event.risk_tier === "elevated").length,
    low: events.filter((event) => event.risk_tier === "low").length,
  };
  const ringScale = (tier: string) => (tier === "critical" ? 0.55 : tier === "elevated" ? 0.8 : 1);

  return (
    <div className="orbit-placeholder orbit-live">
      <div className="orbit orbit-1" />
      <div className="orbit orbit-2" />
      <div className="orbit orbit-3" />
      <div className="earth">
        <div className="earth-glow" />
        <span>⊕</span>
      </div>

      {events.map((event, index) => {
        const angle = (-90 + (360 * index) / Math.max(events.length, 1)) * (Math.PI / 180);
        const scale = ringScale(event.risk_tier);
        return (
          <button
            key={event.id}
            className={`orbit-marker marker-${event.risk_tier}`}
            style={{
              left: `${50 + 40 * scale * Math.cos(angle)}%`,
              top: `${50 + 36 * scale * Math.sin(angle)}%`,
            }}
            title={`${event.object_a.name} × ${event.object_b.name} — score ${event.risk_score.toFixed(0)} (${event.risk_tier})`}
            aria-label={`Open conjunction: ${event.object_a.name} and ${event.object_b.name}`}
            onClick={() => onSelect(event.id)}
          >
            <i />
            <span>{event.risk_score.toFixed(0)}</span>
          </button>
        );
      })}

      <div className="orbit-empty orbit-center-label">
        {events.length
          ? `${counts.critical} critical · ${counts.elevated} elevated · ${counts.low} low`
          : "No flagged close approaches"}
      </div>
      <div className="orbit-legend">
        <span><i className="legend-dot dot-critical" /> critical ({counts.critical})</span>
        <span><i className="legend-dot dot-elevated" /> elevated ({counts.elevated})</span>
        <span><i className="legend-dot dot-low" /> low ({counts.low})</span>
        <span>SGP4 propagation · public TLE data · click a marker</span>
      </div>
    </div>
  );
}

function StatCard({ label, value = "—", hint, accent }: { label: string; value?: number | string; hint: string; accent?: string }) {
  return (
    <div className={`card ${accent ? `card-${accent}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

function EventRow({ event, onClick }: { event: EventSummary; onClick: () => void }) {
  return (
    <button className="event-row" onClick={onClick}>
      <span className={`tier-dot tier-${event.risk_tier}`} />
      <span className="event-copy">
        <strong>{event.object_a.name} × {event.object_b.name}</strong>
        <small>{event.summary}</small>
      </span>
      <span className={`tier-label tier-${event.risk_tier}`}>{event.risk_tier}</span>
      <span className="event-score">{event.risk_score.toFixed(0)}</span>
    </button>
  );
}

function EventTable({ events, onSelect }: { events: EventSummary[]; onSelect: (id: string) => void }) {
  return (
    <div className="table-body">
      {events.map((event) => (
        <button className="table-row" key={event.id} onClick={() => onSelect(event.id)}>
          <span>{event.object_a.name} × {event.object_b.name}</span>
          <span>{event.object_a.object_type.replace("_", " ")} / {event.object_b.object_type.replace("_", " ")}</span>
          <span><i className={`tier-dot tier-${event.risk_tier}`} /> {event.risk_score.toFixed(0)} · {event.risk_tier}</span>
          <span>{event.miss_distance_display}</span>
          <span>{event.tca_display}</span>
        </button>
      ))}
    </div>
  );
}

function ObjectsPage({ stats }: { stats: Stats | null }) {
  const [search, setSearch] = useState("");
  const [objects, setObjects] = useState<ObjectListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void api.objects(search.trim(), 500)
      .then((result) => {
        if (!cancelled) {
          setObjects(result.items);
          setLoading(false);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [search]);

  return (
    <section className="panel objects-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">SPACE OBJECT CATALOG</p>
          <h2>Tracked objects</h2>
        </div>
        <input
          className="catalog-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name…"
          aria-label="Search tracked objects"
        />
        <span className="data-badge">{stats?.data_source ?? "waiting"}</span>
      </div>

      <div className="object-summary">
        <StatCard label="Total Objects" value={objects.length || stats?.objects_tracked} hint="Stored in Postgres" />
        <StatCard label="Payloads" value={objects.filter((object_) => object_.object_type === "payload").length} hint="Active satellites can maneuver" />
        <StatCard label="Debris" value={objects.filter((object_) => object_.object_type === "debris").length} hint="Cannot maneuver — passive risk" />
        <StatCard label="Rocket Bodies" value={objects.filter((object_) => object_.object_type === "rocket_body").length} hint="Spent upper stages" />
      </div>

      <div className="table-row table-head">
        <span>OBJECT</span>
        <span>NORAD ID</span>
        <span>TYPE</span>
        <span>EPOCH</span>
      </div>
      {loading ? (
        <EmptyState message="Loading catalog from the backend…" />
      ) : objects.length ? (
        <div className="table-body">
          {objects.map((object_) => (
            <div className="table-row" key={object_.norad_id}>
              <span>{object_.name}</span>
              <span className="mono">{object_.norad_id}</span>
              <span>{object_.object_type.replace("_", " ")}</span>
              <span>{object_.epoch ? new Date(object_.epoch).toLocaleString() : "—"}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No catalog objects match that search." />
      )}
    </section>
  );
}

function ScreeningPage({ stats, events, refreshing, onRefresh, onSelect }: {
  stats: Stats | null;
  events: EventSummary[];
  refreshing: boolean;
  onRefresh: () => void;
  onSelect: (id: string) => void;
}) {
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    void api.config().then(setConfig).catch(() => undefined);
  }, []);

  const byTca = [...events].sort((a, b) => a.tca.localeCompare(b.tca));

  return (
    <div className="screening-page">
      <section className="panel screening-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">CONJUNCTION SCREENING</p>
            <h2>Deterministic screen</h2>
          </div>
          <span className="data-badge">{stats?.data_source === "cache" ? "cached data" : "live data"}</span>
        </div>
        <p className="screening-copy">
          Perigee fetches current public orbital elements, propagates the tracked set with SGP4, and stores only
          explainable close approaches. The request returns immediately while WebSocket status updates arrive here.
        </p>
        {config ? (
          <div className="config-grid">
            <div><small>Screening window</small><strong>{config.screening.horizon_hours} h ahead</strong></div>
            <div><small>Flag below</small><strong>{config.screening.conjunction_threshold_km} km separation</strong></div>
            <div><small>Object limit</small><strong>{config.screening.object_limit} tracked objects</strong></div>
            <div><small>Scheduled refresh</small><strong>every {config.screening.refresh_interval_hours} h</strong></div>
            <div><small>Risk weights</small><strong>{Object.entries(config.risk.weights).map(([name, weight]) => `${name.replace("_", " ")} ${weight}`).join(" · ")}</strong></div>
            <div><small>Tier cutoffs</small><strong>Critical ≥ {config.risk.critical_threshold} · Elevated ≥ {config.risk.elevated_threshold}</strong></div>
          </div>
        ) : (
          <small className="muted-copy">Loading screening configuration from the backend…</small>
        )}
        <button className="screening-btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "Screening in progress…" : "Run refresh now"}
        </button>
        {refreshing && <small className="muted-copy">Propagating orbits — results appear automatically when the cycle completes.</small>}
      </section>

      <section className="panel screening-results">
        <div className="panel-header">
          <div>
            <p className="eyebrow">SCREENING OUTPUT</p>
            <h2>Results · ordered by closest approach</h2>
          </div>
          <span className="data-badge">{byTca.length} flagged pairs</span>
        </div>
        {byTca.length ? (
          <>
            <div className="table-row table-head">
              <span>OBJECTS</span>
              <span>MISS DISTANCE</span>
              <span>REL. VELOCITY</span>
              <span>TCA</span>
              <span>RISK</span>
            </div>
            <div className="table-body">
              {byTca.map((event) => (
                <button className="table-row" key={event.id} onClick={() => onSelect(event.id)}>
                  <span>{event.object_a.name} × {event.object_b.name}</span>
                  <span>{event.miss_distance_display}</span>
                  <span>{event.relative_velocity_display}</span>
                  <span>{event.tca_display}</span>
                  <span><i className={`tier-dot tier-${event.risk_tier}`} /> {event.risk_tier} · {event.risk_score.toFixed(0)}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <EmptyState message={refreshing ? "Screening is running — no flagged pairs yet." : "No flagged close approaches in the current screen."} />
        )}
      </section>
    </div>
  );
}

function RiskAnalysisPage({ stats, events, onSelect }: { stats: Stats | null; events: EventSummary[]; onSelect: (id: string) => void }) {
  const tiers = ["all", "critical", "elevated", "low"] as const;
  const [tierFilter, setTierFilter] = useState<(typeof tiers)[number]>("all");
  const ranked = [...events].sort(byScoreDesc).filter((event) => tierFilter === "all" || event.risk_tier === tierFilter);
  const total = stats?.events_screened ?? events.length;
  const distribution = [
    { tier: "critical", count: stats?.critical_count ?? 0 },
    { tier: "elevated", count: stats?.elevated_count ?? 0 },
    { tier: "low", count: stats?.low_count ?? 0 },
  ];

  return (
    <div className="risk-analysis-page">
      <section className="panel risk-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RISK ASSESSMENT SYSTEM</p>
            <h2>Tier distribution</h2>
          </div>
        </div>
        <div className="distribution">
          {distribution.map((entry) => (
            <div className="distribution-row" key={entry.tier}>
              <span className={`tier-label tier-${entry.tier}`}>{entry.tier}</span>
              <div className="distribution-bar">
                <i className={`tier-${entry.tier}`} style={{ width: `${total ? (entry.count / total) * 100 : 0}%` }} />
              </div>
              <b>{entry.count}</b>
            </div>
          ))}
        </div>
        <p className="screening-copy">
          Scores come from the deterministic engine: miss distance, relative velocity at closest approach, object type,
          and trend across repeated screenings. Higher score means higher review priority.
        </p>
        <div className="tier-filter" role="group" aria-label="Filter by risk tier">
          {tiers.map((tier) => (
            <button
              key={tier}
              className={`chip ${tierFilter === tier ? "chip-active" : ""}`}
              onClick={() => setTierFilter(tier)}
            >
              {tier}
            </button>
          ))}
        </div>
      </section>

      <section className="panel risk-results">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RISK ASSESSMENT OUTPUT</p>
            <h2>Ranked by priority</h2>
          </div>
        </div>
        {ranked.length ? (
          <div className="event-list">
            {ranked.map((event) => (
              <div className="analysis-row" key={event.id}>
                <EventRow event={event} onClick={() => onSelect(event.id)} />
                <div className="score-gauge" role="img" aria-label={`Risk score ${event.risk_score.toFixed(0)} of 100`}>
                  <i className={`tier-${event.risk_tier}`} style={{ width: `${Math.min(100, event.risk_score)}%` }} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No events match this filter." />
        )}
      </section>
    </div>
  );
}

function PropagationPage() {
  const [search, setSearch] = useState("");
  const [objects, setObjects] = useState<ObjectListItem[]>([]);
  const [selected, setSelected] = useState<ObjectListItem | null>(null);
  const [stateVector, setStateVector] = useState<PropagatedObject | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [propagating, setPropagating] = useState(false);
  const [propagationError, setPropagationError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api.objects(search.trim(), 200)
      .then((result) => {
        if (!cancelled) {
          setObjects(result.items);
          setLoadingCatalog(false);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [search]);

  const select = async (object_: ObjectListItem) => {
    setSelected(object_);
    setStateVector(null);
    setPropagationError(null);
    setPropagating(true);
    try {
      setStateVector(await api.object(object_.norad_id));
    } catch (cause) {
      setPropagationError(cause instanceof Error ? cause.message : "Propagation failed");
    } finally {
      setPropagating(false);
    }
  };

  return (
    <div className="propagation-page">
      <section className="panel propagation-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">ORBITAL PROPAGATION SYSTEM</p>
            <h2>Pick an object</h2>
          </div>
        </div>
        <input
          className="catalog-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search the live catalog…"
          aria-label="Search objects to propagate"
        />
        {loadingCatalog ? (
          <EmptyState message="Loading object catalog…" />
        ) : objects.length ? (
          <div className="catalog-list">
            {objects.map((object_) => (
              <button
                key={object_.norad_id}
                className={`catalog-item ${selected?.norad_id === object_.norad_id ? "catalog-item-active" : ""}`}
                onClick={() => void select(object_)}
              >
                <strong>{object_.name}</strong>
                <small>{object_.object_type.replace("_", " ")} · NORAD {object_.norad_id}</small>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState message="No objects match that search." />
        )}
      </section>

      <section className="panel propagation-output">
        <div className="panel-header">
          <div>
            <p className="eyebrow">PROPAGATION OUTPUT</p>
            <h2>{selected ? selected.name : "Orbital state"}</h2>
          </div>
        </div>
        {propagating && <EmptyState message="Running SGP4 propagation for the current epoch…" />}
        {!propagating && propagationError && <EmptyState message={`Propagation failed: ${propagationError}`} />}
        {!propagating && stateVector && (
          <div className="propagation-result">
            <div className="detail-grid">
              <div><small>Type</small><strong>{stateVector.object_type.replace("_", " ")}</strong></div>
              <div><small>Latitude</small><strong>{stateVector.latitude_deg != null ? `${stateVector.latitude_deg.toFixed(2)}°` : "—"}</strong></div>
              <div><small>Longitude</small><strong>{stateVector.longitude_deg != null ? `${stateVector.longitude_deg.toFixed(2)}°` : "—"}</strong></div>
              <div><small>Altitude</small><strong>{stateVector.altitude_display ?? "—"}</strong></div>
              <div><small>Element epoch</small><strong>{new Date(stateVector.epoch).toLocaleString()}</strong></div>
              <div><small>NORAD ID</small><strong className="mono">{stateVector.norad_id}</strong></div>
            </div>
            <small className="muted-copy">{stateVector.type_description}</small>
          </div>
        )}
        {!propagating && !stateVector && !propagationError && (
          <EmptyState message="Select an object from the live catalog to propagate its current state." />
        )}
      </section>
    </div>
  );
}

const QUICK_PROMPTS = [
  "Which alerts need attention right now?",
  "What is the most urgent thing on the board?",
  "Summarize the current screening picture",
];

function AgentPanel({ events, onSelect }: { events: EventSummary[]; onSelect: (id: string) => void }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async (prompt: string) => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      setResult(await api.query(prompt));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void api.insights().then(setInsights).catch(() => undefined);
  }, []);

  return (
    <section className="panel agent-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">AI-ASSISTED · READ ONLY</p>
          <h2>Ask Perigee</h2>
        </div>
        <span className="data-badge">{result?.source ?? "local qwen3.5:9b"}</span>
      </div>
      <div className="agent-query">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void ask(question);
          }}
          placeholder="Ask anything about the current screening results…"
          aria-label="Ask Perigee a question"
        />
        <button className="outline-btn" onClick={() => void ask(question)} disabled={loading}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </div>
      <div className="agent-chips">
        {QUICK_PROMPTS.map((prompt) => (
          <button key={prompt} className="chip" disabled={loading} onClick={() => {
            setQuestion(prompt);
            void ask(prompt);
          }}>
            {prompt}
          </button>
        ))}
      </div>
      {result && (
        <div className="agent-answer">
          <small>AI-assisted answer{result.source === "template" ? " · deterministic fallback" : ` · ${result.model}`}</small>
          <strong>{result.answer}</strong>
          {result.provider_error && <small>Fallback used: {result.provider_error}</small>}
          {result.referenced_event_ids.length > 0 && result.referenced_event_ids.map((id) => (
            <button key={id} className="link-btn" onClick={() => onSelect(id)}>
              Open referenced event
            </button>
          ))}
        </div>
      )}
      {insights?.insights.length ? (
        <div className="insight-list">
          <small>AI-assisted observations</small>
          {insights.insights.map((insight) => (
            <p key={insight.observation}>◈ {insight.observation}</p>
          ))}
        </div>
      ) : (
        events.length === 0 && <small className="muted-copy">AI observations will appear when the deterministic screen records events.</small>
      )}
    </section>
  );
}

function TrendSparkline({ points }: { points: EventDetail["trend_history"] }) {
  if (points.length < 2) return null;
  const scores = points.map((point) => point.risk_score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const span = max - min || 1;
  const coords = scores
    .map((score, index) => `${(index / (scores.length - 1)) * 100},${28 - ((score - min) / span) * 24}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="sparkline" role="img" aria-label="Risk score trend across screenings">
      <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function EventDrawer({ eventId, onClose, aiEnabled }: { eventId: string; onClose: () => void; aiEnabled: boolean }) {
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [explanation, setExplanation] = useState<Awaited<ReturnType<typeof api.explain>> | null>(null);
  const [recommendation, setRecommendation] = useState<Awaited<ReturnType<typeof api.recommendation>> | null>(null);
  const [explaining, setExplaining] = useState(false);

  useEffect(() => {
    void api.event(eventId).then(setDetail);
  }, [eventId]);

  const explain = async () => {
    setExplaining(true);
    try {
      setExplanation(await api.explain(eventId));
      setRecommendation(await api.recommendation(eventId).catch(() => null));
    } finally {
      setExplaining(false);
    }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="event-drawer" onClick={(event) => event.stopPropagation()}>
        <button className="drawer-close" onClick={onClose} aria-label="Close event detail">×</button>
        {detail ? (
          <>
            <p className="eyebrow">DETERMINISTIC EVENT DETAIL</p>
            <h2>{detail.object_a.name} × {detail.object_b.name}</h2>
            <div className={`risk-banner tier-${detail.risk_tier}`}>
              {detail.risk_tier.toUpperCase()} · score {detail.risk_score.toFixed(1)}
            </div>
            <p>{detail.summary}</p>
            <div className="detail-grid">
              <div><small>Miss distance</small><strong>{detail.miss_distance_display}</strong></div>
              <div><small>Relative velocity</small><strong>{detail.relative_velocity_display}</strong></div>
              <div><small>Closest approach</small><strong>{detail.tca_display}</strong></div>
              <div><small>Trend</small><strong>{detail.trend_label}</strong></div>
            </div>
            {detail.trend_history.length > 1 && (
              <div className="trend-block">
                <small>Trending: {detail.trend_label} across {detail.trend_history.length} screenings</small>
                <TrendSparkline points={detail.trend_history} />
              </div>
            )}
            <h3>Why it was flagged</h3>
            {Object.entries(detail.factor_breakdown).map(([name, factor]) => (
              <div className="factor" key={name}>
                <div>
                  <span>{name.replaceAll("_", " ")}</span>
                  <b>{factor.contribution.toFixed(1)}</b>
                </div>
                <div className="factor-bar"><i style={{ width: `${Math.min(100, factor.contribution)}%` }} /></div>
                <small>{factor.caption}</small>
              </div>
            ))}
            {aiEnabled && (
              <button className="screening-btn" onClick={() => void explain()} disabled={explaining}>
                {explaining ? "Thinking with local AI…" : explanation ? "Refresh AI explanation" : "Explain with local AI"}
              </button>
            )}
            {aiEnabled && explanation && (
              <div className="ai-box">
                <small>AI-assisted · {explanation.source}</small>
                <strong>{explanation.headline}</strong>
                <p>{explanation.explanation}</p>
                <ul>{explanation.operator_focus.map((focus) => <li key={focus}>{focus}</li>)}</ul>
                <small>{explanation.caveat}</small>
              </div>
            )}
            {aiEnabled && recommendation && (
              <div className="ai-box">
                <small>AI-assisted triage suggestion</small>
                <p>{recommendation.recommendation}</p>
              </div>
            )}
          </>
        ) : (
          <p>Loading event detail…</p>
        )}
      </aside>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <span>—</span>
      <p>{message}</p>
      <small>Live API data will appear after the next successful screen.</small>
    </div>
  );
}

function EmptyTable({ message }: { message: string }) {
  return (
    <div className="empty-table">
      <div className="table-row table-head">
        <span>OBJECT</span>
        <span>TYPE</span>
        <span>RISK</span>
        <span>STATUS</span>
        <span>UPDATED</span>
      </div>
      <EmptyState message={message} />
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (next: boolean) => void; label: string }) {
  return (
    <button
      className={`toggle ${checked ? "toggle-on" : ""}`}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}

function SettingsPage({ settings, onUpdate }: {
  settings: ReturnType<typeof useSettings>[0];
  onUpdate: (patch: Partial<ReturnType<typeof useSettings>[0]>) => void;
}) {
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    void api.config().then(setConfig).catch(() => undefined);
  }, []);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">APPLICATION PREFERENCES</p>
          <h2>Preferences</h2>
        </div>
        <span className="data-badge">saved locally</span>
      </div>

      <div className="settings-list">
        <div className="setting-row">
          <div>
            <strong>AI assistance</strong>
            <small>Show the Ask Perigee panel and per-event AI explanations. The deterministic dashboard is unaffected when off.</small>
          </div>
          <Toggle checked={settings.aiAssistance} onChange={(next) => onUpdate({ aiAssistance: next })} label="AI assistance" />
        </div>
        <div className="setting-row">
          <div>
            <strong>Live update announcements</strong>
            <small>Briefly announce new or re-scored close approaches as they arrive over WebSocket.</small>
          </div>
          <Toggle checked={settings.liveToasts} onChange={(next) => onUpdate({ liveToasts: next })} label="Live update announcements" />
        </div>
        <div className="setting-row">
          <div>
            <strong>Client auto-refresh</strong>
            <small>Trigger a full deterministic re-screen from this browser while the dashboard stays open. The backend scheduler runs regardless.</small>
          </div>
          <select
            className="setting-select"
            value={String(settings.autoRefreshMinutes)}
            aria-label="Client auto-refresh interval"
            onChange={(event) => onUpdate({ autoRefreshMinutes: Number(event.target.value) })}
          >
            <option value="0">Off (backend schedule only)</option>
            <option value="10">Every 10 minutes</option>
            <option value="30">Every 30 minutes</option>
          </select>
        </div>
        <div className="setting-row">
          <div>
            <strong>Compact tables</strong>
            <small>Denser rows for screening and activity tables — fits more events on screen.</small>
          </div>
          <Toggle checked={settings.compactTables} onChange={(next) => onUpdate({ compactTables: next })} label="Compact tables" />
        </div>
      </div>

      <div className="panel-header backend-panel-header">
        <div>
          <p className="eyebrow">BACKEND CONTROLLED · READ ONLY</p>
          <h2>Deterministic engine settings</h2>
        </div>
        <span className="data-badge">{config ? "live" : "loading…"}</span>
      </div>
      <small className="muted-copy config-note">
        These values are environment-driven on the backend and cannot be changed from the UI, keeping the scoring pipeline auditable.
      </small>
      {config && (
        <div className="config-grid settings-config-grid">
          <div><small>Screening window</small><strong>{config.screening.horizon_hours} h ahead</strong></div>
          <div><small>Flag below</small><strong>{config.screening.conjunction_threshold_km} km separation</strong></div>
          <div><small>Scheduled refresh</small><strong>every {config.screening.refresh_interval_hours} h</strong></div>
          <div><small>Risk weights</small><strong>{Object.entries(config.risk.weights).map(([name, weight]) => `${name.replace("_", " ")} ${weight}`).join(" · ")}</strong></div>
          <div><small>Tier cutoffs</small><strong>Critical ≥ {config.risk.critical_threshold} · Elevated ≥ {config.risk.elevated_threshold}</strong></div>
          <div><small>AI layer</small><strong>{config.ai.enabled ? `${config.ai.model} (local)` : "disabled"}</strong></div>
        </div>
      )}
    </section>
  );
}

export default App;

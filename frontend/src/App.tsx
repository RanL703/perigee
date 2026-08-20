import { useState } from "react";
import "./index.css";

type Risk = "LOW" | "MEDIUM" | "HIGH";

const satellites = [
  {
    id: "SAT-1042",
    name: "ORION-7",
    altitude: "547 km",
    velocity: "7.61 km/s",
    inclination: "51.6°",
    risk: "LOW" as Risk,
    distance: "12.8 km",
  },
  {
    id: "SAT-2087",
    name: "COSMOS-21",
    altitude: "682 km",
    velocity: "7.48 km/s",
    inclination: "74.1°",
    risk: "HIGH" as Risk,
    distance: "0.84 km",
  },
  {
    id: "SAT-3319",
    name: "NOVA-3",
    altitude: "421 km",
    velocity: "7.66 km/s",
    inclination: "97.3°",
    risk: "MEDIUM" as Risk,
    distance: "4.21 km",
  },
  {
    id: "SAT-4176",
    name: "AURORA-9",
    altitude: "791 km",
    velocity: "7.31 km/s",
    inclination: "98.7°",
    risk: "LOW" as Risk,
    distance: "18.4 km",
  },
];

const alerts = [
  {
    time: "14:32:08",
    title: "Close approach detected",
    description: "COSMOS-21 · 0.84 km predicted separation",
    risk: "HIGH" as Risk,
  },
  {
    time: "13:47:21",
    title: "Risk threshold exceeded",
    description: "NOVA-3 · Probability increased to 2.7%",
    risk: "MEDIUM" as Risk,
  },
  {
    time: "12:18:44",
    title: "Orbit update received",
    description: "ORION-7 · Propagation successfully updated",
    risk: "LOW" as Risk,
  },
];

function RiskBadge({ risk }: { risk: Risk }) {
  return <span className={`risk-badge ${risk.toLowerCase()}`}>{risk}</span>;
}

function App() {
  const [active, setActive] = useState("Overview");
  const [selectedSatellite, setSelectedSatellite] = useState(satellites[1]);

  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <span>◉</span>
          </div>

          <div>
            <h1>PERIGEE</h1>
            <p>ORBITAL INTELLIGENCE</p>
          </div>
        </div>

        <nav className="navigation">
          <p className="nav-label">MONITORING</p>

          {["Overview", "Satellites", "Risk Analysis", "Close Approaches"].map(
            (item, index) => (
              <button
                key={item}
                className={`nav-item ${active === item ? "active" : ""}`}
                onClick={() => setActive(item)}
              >
                <span className="nav-icon">
                  {["⌂", "◈", "◌", "⚠"][index]}
                </span>
                {item}
              </button>
            )
          )}

          <p className="nav-label second">SYSTEM</p>

          {["Alerts", "Data Sources", "Settings"].map((item, index) => (
            <button
              key={item}
              className={`nav-item ${active === item ? "active" : ""}`}
              onClick={() => setActive(item)}
            >
              <span className="nav-icon">
                {["!", "◎", "⚙"][index]}
              </span>
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot"></span>

            <div>
              <strong>System Operational</strong>
              <span>All services running</span>
            </div>
          </div>

          <div className="version">PERIGEE v1.0.0</div>
        </div>
      </aside>

      {/* MAIN */}
      <main className="main">
        {/* TOPBAR */}
        <header className="topbar">
          <div>
            <p className="breadcrumb">MISSION CONTROL / {active.toUpperCase()}</p>
            <h2>{active}</h2>
          </div>

          <div className="top-actions">
            <div className="live-status">
              <span></span>
              LIVE MONITORING
            </div>

            <button className="icon-button">⌕</button>
            <button className="profile">SK</button>
          </div>
        </header>

        <div className="content">
          {/* HERO */}
          <section className="hero">
            <div className="hero-copy">
              <span className="eyebrow">ORBITAL SITUATIONAL AWARENESS</span>

              <h1>
                Understand the
                <br />
                <span>space around you.</span>
              </h1>

              <p>
                Real-time orbital intelligence for tracking satellites,
                detecting close approaches, and evaluating collision risk.
              </p>

              <div className="hero-buttons">
                <button className="primary-button">
                  <span>▶</span>
                  Start Monitoring
                </button>

                <button className="secondary-button">
                  View Analytics
                  <span>→</span>
                </button>
              </div>
            </div>

            {/* ORBIT VISUAL */}
            <div className="orbit-system">
              <div className="orbit-glow"></div>
              <div className="earth">
                <div className="earth-light"></div>
                <div className="continent c1"></div>
                <div className="continent c2"></div>
              </div>

              <div className="orbit-line orbit-a"></div>
              <div className="orbit-line orbit-b"></div>
              <div className="orbit-line orbit-c"></div>

              <div className="sat-dot sat-one"></div>
              <div className="sat-dot sat-two"></div>
              <div className="sat-dot sat-three"></div>

              <div className="orbit-label label-one">SAT-2087</div>
              <div className="orbit-label label-two">ORION-7</div>
            </div>
          </section>

          {/* STAT CARDS */}
          <section className="stats-grid">
            <div className="stat-card">
              <div className="stat-top">
                <span>TRACKED OBJECTS</span>
                <span className="stat-icon">◈</span>
              </div>

              <strong>12,847</strong>
              <small>
                <span className="positive">+128</span> in last 24 hours
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-top">
                <span>ACTIVE THREATS</span>
                <span className="stat-icon warning">⚠</span>
              </div>

              <strong className="danger-number">03</strong>
              <small>
                <span className="negative">+1</span> since last update
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-top">
                <span>CLOSE APPROACHES</span>
                <span className="stat-icon">⌁</span>
              </div>

              <strong>17</strong>
              <small>
                <span className="positive">−4</span> from previous cycle
              </small>
            </div>

            <div className="stat-card">
              <div className="stat-top">
                <span>DATA FRESHNESS</span>
                <span className="stat-icon">◷</span>
              </div>

              <strong>99.8%</strong>
              <small>
                Last update <span className="positive">12 sec ago</span>
              </small>
            </div>
          </section>

          {/* GRID */}
          <section className="dashboard-grid">
            {/* RISK */}
            <div className="panel risk-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-label">RISK ASSESSMENT</span>
                  <h3>Orbital Risk Overview</h3>
                </div>

                <button className="more-button">•••</button>
              </div>

              <div className="risk-content">
                <div className="risk-score">
                  <div className="score-ring">
                    <div>
                      <strong>72</strong>
                      <span>/100</span>
                    </div>
                  </div>

                  <div>
                    <RiskBadge risk="MEDIUM" />
                    <p>Overall orbital risk</p>
                  </div>
                </div>

                <div className="risk-bars">
                  <div className="bar-row">
                    <div>
                      <span>Collision Probability</span>
                      <b>24%</b>
                    </div>
                    <div className="bar">
                      <i style={{ width: "24%" }}></i>
                    </div>
                  </div>

                  <div className="bar-row">
                    <div>
                      <span>Close Approach</span>
                      <b>61%</b>
                    </div>
                    <div className="bar">
                      <i style={{ width: "61%" }}></i>
                    </div>
                  </div>

                  <div className="bar-row">
                    <div>
                      <span>Tracking Confidence</span>
                      <b>94%</b>
                    </div>
                    <div className="bar">
                      <i className="safe-bar" style={{ width: "94%" }}></i>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ALERTS */}
            <div className="panel alerts-panel">
              <div className="panel-header">
                <div>
                  <span className="panel-label">LIVE FEED</span>
                  <h3>Recent Alerts</h3>
                </div>

                <button className="view-all">View all →</button>
              </div>

              <div className="alerts">
                {alerts.map((alert) => (
                  <div className="alert" key={alert.time}>
                    <div className={`alert-marker ${alert.risk.toLowerCase()}`}>
                      !
                    </div>

                    <div className="alert-info">
                      <div>
                        <strong>{alert.title}</strong>
                        <time>{alert.time}</time>
                      </div>

                      <p>{alert.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* SATELLITES */}
          <section className="panel satellite-panel">
            <div className="panel-header">
              <div>
                <span className="panel-label">OBJECT CATALOG</span>
                <h3>Tracked Satellites</h3>
              </div>

              <button className="secondary-button small">
                Export Data ↓
              </button>
            </div>

            <div className="table">
              <div className="table-head">
                <span>OBJECT</span>
                <span>ALTITUDE</span>
                <span>VELOCITY</span>
                <span>INCLINATION</span>
                <span>SEPARATION</span>
                <span>RISK</span>
              </div>

              {satellites.map((satellite) => (
                <button
                  className={`table-row ${
                    selectedSatellite.id === satellite.id ? "selected" : ""
                  }`}
                  key={satellite.id}
                  onClick={() => setSelectedSatellite(satellite)}
                >
                  <span className="object-name">
                    <i></i>
                    <div>
                      <strong>{satellite.name}</strong>
                      <small>{satellite.id}</small>
                    </div>
                  </span>

                  <span>{satellite.altitude}</span>
                  <span>{satellite.velocity}</span>
                  <span>{satellite.inclination}</span>
                  <span>{satellite.distance}</span>
                  <span>
                    <RiskBadge risk={satellite.risk} />
                  </span>
                </button>
              ))}
            </div>
          </section>

          {/* SELECTED SATELLITE */}
          <section className="selected-object">
            <div>
              <span className="panel-label">SELECTED OBJECT</span>
              <h3>{selectedSatellite.name}</h3>
              <p>
                {selectedSatellite.id} · Orbital telemetry available
              </p>
            </div>

            <div className="selected-data">
              <div>
                <span>ALTITUDE</span>
                <strong>{selectedSatellite.altitude}</strong>
              </div>

              <div>
                <span>VELOCITY</span>
                <strong>{selectedSatellite.velocity}</strong>
              </div>

              <div>
                <span>INCLINATION</span>
                <strong>{selectedSatellite.inclination}</strong>
              </div>

              <div>
                <span>RISK</span>
                <RiskBadge risk={selectedSatellite.risk} />
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;
import { useState } from "react";
import "./App.css";

type Page =
  | "Dashboard"
  | "Objects"
  | "Screening"
  | "Risk Analysis"
  | "Propagation"
  | "Settings";

const navItems: Page[] = [
  "Dashboard",
  "Objects",
  "Screening",
  "Risk Analysis",
  "Propagation",
];

function App() {
  const [page, setPage] = useState<Page>("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleNavigation = (item: Page) => {
    setPage(item);
    setSidebarOpen(false);
  };

  return (
    <div className={`app ${sidebarOpen ? "sidebar-open" : ""}`}>
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
            <button
              key={item}
              className={`nav-item ${page === item ? "active" : ""}`}
              onClick={() => handleNavigation(item)}
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className={`nav-item ${page === "Settings" ? "active" : ""}`}
            onClick={() => handleNavigation("Settings")}
          >
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

          <div className="status">
            <span className="status-dot" />
            System Operational
          </div>
        </header>

        {page === "Dashboard" && <Dashboard />}
        {page === "Objects" && <ObjectsPage />}
        {page === "Screening" && <ScreeningPage />}
        {page === "Risk Analysis" && <RiskAnalysisPage />}
        {page === "Propagation" && <PropagationPage />}
        {page === "Settings" && <SettingsPage />}
      </main>
    </div>
  );
}

function Dashboard() {
  return (
    <>
      <section className="stats">
        <StatCard label="Tracked Objects" />
        <StatCard label="Active Conjunctions" />
        <StatCard label="High Risk Objects" />
        <StatCard label="Last Update" />
      </section>

      <section className="content-grid">
        <div className="panel large">
          <div className="panel-header">
            <div>
              <p className="eyebrow">ORBITAL OVERVIEW</p>
              <h2>Object Tracking</h2>
            </div>

            <button className="outline-btn">View all</button>
          </div>

          <div className="orbit-placeholder">
            <div className="orbit orbit-1" />
            <div className="orbit orbit-2" />
            <div className="orbit orbit-3" />

            <div className="earth">
              <div className="earth-glow" />
              <span>⊕</span>
            </div>

            <div className="orbit-empty">
              No orbital data available
            </div>

            <div className="orbit-legend">
              <span>Waiting for propagation data</span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">RISK MONITOR</p>
              <h2>Priority Events</h2>
            </div>
          </div>

          <EmptyState message="No event data available" />
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Latest Screenings</h2>
          </div>

          <button className="outline-btn">Export</button>
        </div>

        <EmptyTable message="No screening data available" />
      </section>
    </>
  );
}

function ObjectsPage() {
  return (
    <section className="panel objects-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">SPACE OBJECT CATALOG</p>
          <h2>Tracked Objects</h2>
        </div>

        <button className="outline-btn">Export</button>
      </div>

      <div className="object-summary">
        <StatCard label="Total Objects" />
        <StatCard label="LEO Objects" />
        <StatCard label="MEO Objects" />
        <StatCard label="High Risk Objects" />
      </div>

      <EmptyTable message="No object data available" />
    </section>
  );
}

function StatCard({ label }: { label: string }) {
  return (
    <div className="card">
      <span>{label}</span>
      <strong>—</strong>
      <small>Data unavailable</small>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <span>—</span>
      <p>{message}</p>
      <small>Connect the Perigee backend to load data.</small>
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

function ScreeningPage() {
  return (
    <div className="screening-page">
      <section className="panel screening-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">CONJUNCTION SCREENING</p>
            <h2>Screening Configuration</h2>
          </div>
        </div>

        <div className="screening-form">
          <label>
            <span>SCREENING WINDOW</span>
            <input type="text" placeholder="Enter time window" />
          </label>

          <label>
            <span>MINIMUM SEPARATION</span>
            <input type="text" placeholder="Enter threshold" />
          </label>

          <label>
            <span>OBJECT SOURCE</span>
            <select defaultValue="">
              <option value="" disabled>
                Select object source
              </option>
              <option value="catalog">Object Catalog</option>
              <option value="external">External Source</option>
            </select>
          </label>

          <button className="screening-btn">Run Screening</button>
        </div>
      </section>

      <section className="panel screening-results">
        <div className="panel-header">
          <div>
            <p className="eyebrow">SCREENING OUTPUT</p>
            <h2>Results</h2>
          </div>
        </div>

        <EmptyState message="No screening results available" />
      </section>
    </div>
  );
}

function RiskAnalysisPage() {
  return (
    <div className="risk-analysis-page">
      <section className="panel risk-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RISK ASSESSMENT SYSTEM</p>
            <h2>Risk Analysis</h2>
          </div>
        </div>

        <div className="risk-form">
          <label>
            <span>OBJECT SOURCE</span>
            <select defaultValue="">
              <option value="" disabled>
                Select object source
              </option>
              <option value="catalog">Object Catalog</option>
              <option value="screening">Screening Results</option>
            </select>
          </label>

          <label>
            <span>RISK MODEL</span>
            <select defaultValue="">
              <option value="" disabled>
                Select risk model
              </option>
              <option value="conjunction">Conjunction Risk</option>
              <option value="collision">Collision Risk</option>
            </select>
          </label>

          <label>
            <span>ANALYSIS WINDOW</span>
            <input type="text" placeholder="Enter analysis window" />
          </label>

          <button className="analysis-btn">Run Analysis</button>
        </div>
      </section>

      <section className="panel risk-results">
        <div className="panel-header">
          <div>
            <p className="eyebrow">RISK ASSESSMENT OUTPUT</p>
            <h2>Analysis Results</h2>
          </div>
        </div>

        <EmptyState message="No risk analysis available" />
      </section>
    </div>
  );
}

function PropagationPage() {
  return (
    <div className="propagation-page">
      <section className="panel propagation-config">
        <div className="panel-header">
          <div>
            <p className="eyebrow">ORBITAL PROPAGATION SYSTEM</p>
            <h2>Propagation</h2>
          </div>
        </div>

        <div className="propagation-form">
          <label>
            <span>OBJECT SOURCE</span>
            <select defaultValue="">
              <option value="" disabled>
                Select object source
              </option>
              <option value="catalog">Object Catalog</option>
              <option value="screening">Screening Results</option>
            </select>
          </label>

          <label>
            <span>PROPAGATION MODEL</span>
            <select defaultValue="">
              <option value="" disabled>
                Select propagation model
              </option>
              <option value="sgp4">SGP4</option>
              <option value="custom">Custom Model</option>
            </select>
          </label>

          <label>
            <span>TIME RANGE</span>
            <input type="text" placeholder="Enter propagation window" />
          </label>

          <button className="propagation-btn">Run Propagation</button>
        </div>
      </section>

      <section className="panel propagation-output">
        <div className="panel-header">
          <div>
            <p className="eyebrow">PROPAGATION OUTPUT</p>
            <h2>Orbital State</h2>
          </div>
        </div>

        <EmptyState message="No propagation data available" />
      </section>
    </div>
  );
}

function SettingsPage() {
  return (
    <div className="settings-page">
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">APPLICATION PREFERENCES</p>
            <h2>Preferences</h2>
          </div>
        </div>

        <div className="settings-list">
          <div className="setting-row">
            <div>
              <strong>Automatic Refresh</strong>
              <small>
                Automatically refresh data when connected to the backend.
              </small>
            </div>

            <button className="toggle" aria-label="Automatic refresh">
              <span />
            </button>
          </div>

          <div className="setting-row">
            <div>
              <strong>Notifications</strong>
              <small>
                Receive notifications for important system events.
              </small>
            </div>

            <button className="toggle" aria-label="Notifications">
              <span />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function EmptyModule({ title }: { title: string }) {
  return (
    <section className="panel placeholder">
      <p className="eyebrow">PERIGEE MODULE</p>
      <h2>{title}</h2>
      <EmptyState message="No data available" />
    </section>
  );
}

export default App;
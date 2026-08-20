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

  return (
    <div className="app">
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
              onClick={() => setPage(item)}
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            className={`nav-item ${page === "Settings" ? "active" : ""}`}
            onClick={() => setPage("Settings")}
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
        {page === "Risk Analysis" && <EmptyModule title="Risk Analysis" />}
        {page === "Propagation" && <EmptyModule title="Propagation" />}
        {page === "Settings" && <EmptyModule title="Settings" />}
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

          <button className="screening-btn">
            Run Screening
          </button>
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
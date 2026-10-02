import { RefreshCw } from "lucide-react";

export function TopBar({ connected, lastUpdated, onRefresh, refreshing }) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="topbar-eyebrow">Civic Priority AI</span>
        <span className="topbar-sub">Admin Command Center</span>
      </div>

      <div className="topbar-status">
        <span className={`live-pill ${connected ? "up" : "down"}`}>
          <span className="live-dot" />
          {connected ? "System online" : "Connection lost"}
        </span>
        <span className="topbar-place">Vellore &middot; Tamil Nadu</span>
      </div>

      <div className="topbar-sync">
        <div className="sync-text">
          <span>Last synchronized</span>
          <strong>
            {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
          </strong>
        </div>
        <button
          className="sync-btn"
          onClick={onRefresh}
          aria-label="Refresh dashboard data"
        >
          <RefreshCw size={15} className={refreshing ? "spin" : ""} />
        </button>
      </div>
    </header>
  );
}

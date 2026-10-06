import {
  Activity,
  Gauge,
  ListOrdered,
  Radio,
  Wrench,
  BarChart3,
  MapPinned,
  WalletCards,
  Repeat2,
  CheckCircle2,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "road-issues", label: "Road Issues", icon: Activity },
  { id: "priority-queue", label: "Priority Queue", icon: ListOrdered },
  { id: "technicians", label: "Technicians", icon: Wrench },
  { id: "repairs", label: "Repair Status", icon: Radio },
  { id: "completed-repairs", label: "Completed Repairs", icon: CheckCircle2 },
  { id: "budget", label: "Budget Optimizer", icon: WalletCards },
  { id: "map", label: "Complaint Map", icon: MapPinned },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
];

export function Sidebar({ activeSection, onNavigate, connected, onSwitchRole }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">CP</div>
        <div className="brand-text">
          <strong>CivicPriorityAI</strong>
          <span>Admin workspace</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`sidebar-link ${activeSection === id ? "active" : ""
              }`}
            onClick={() => onNavigate(id)}
          >
            <Icon size={16} strokeWidth={1.75} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="sidebar-link role-switch-link" onClick={onSwitchRole}>
          <Repeat2 size={16} strokeWidth={1.75} />
          <span>Switch role</span>
        </button>
        <div className="sidebar-status">
          <span
            className={`status-dot ${connected ? "up" : "down"}`}
          ></span>
          <span>{connected ? "System online" : "Connection lost"}</span>
        </div>
        <div className="sidebar-status muted">
          <span
            className={`status-dot ${connected ? "up" : "down"}`}
          ></span>
          <span>{connected ? "API connected" : "API unreachable"}</span>
        </div>
        <div className="sidebar-location">Vellore, Tamil Nadu</div>
      </div>
    </aside>
  );
}

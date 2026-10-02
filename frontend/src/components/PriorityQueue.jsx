import { memo } from "react";
import { Eye, Users } from "lucide-react";
import { PriorityBadge, StatusBadge } from "./StatusBadge.jsx";
import { damageSeverityLabel, detectionStateLabel, roadDamageLabel } from "../utils/complaintLabels.js";

function QueueView({ complaints, selectedId, onSelect, technicians = [], onAssign, title = "Priority Repair Queue" }) {
  const sorted = [...complaints].sort((a, b) => (b.priority?.score ?? 0) - (a.priority?.score ?? 0));
  return (
    <div className="panel admin-queue-panel">
      <div className="panel-header"><div><h2>{title}</h2><p>Ranked by the rule-based baseline; AI prediction is shown separately.</p></div><span className="count-badge">{sorted.length}</span></div>
      <div className="table-wrapper">
        <table className="admin-queue-table">
          <thead><tr><th>Complaint</th><th>Road damage / damage severity</th><th>Overall priority</th><th>Road / location</th><th>Status</th><th>Technician</th><th>Action</th></tr></thead>
          <tbody>
            {sorted.map((complaint) => <tr key={complaint.id} className={complaint.id === selectedId ? "row-active" : ""}>
              <td className="mono">#{String(complaint.id).padStart(3, "0")}</td>
              <td><div className="queue-damage-cell"><span>Road damage</span><strong>{roadDamageLabel(complaint.damage)}</strong><span>AI detection</span><strong>{detectionStateLabel(complaint.damage)}</strong><span>Damage severity</span><strong>{damageSeverityLabel(complaint.damage)}</strong></div></td>
              <td><div className="queue-priority-cell"><span className="queue-signal-label">Rule-based priority level</span><PriorityBadge level={complaint.priority?.level} /><strong>Overall priority score: {complaint.priority?.score ?? "—"}</strong><span className="queue-signal-label">AI predicted overall priority</span>{complaint.ai_prediction?.model_status === "available" ? <><strong>{complaint.ai_prediction.predicted_priority_score} · {complaint.ai_prediction.predicted_priority_level}</strong><small>Difference {complaint.ai_prediction.difference > 0 ? "+" : ""}{complaint.ai_prediction.difference}</small></> : <small>Unavailable</small>}</div></td>
              <td><div className="queue-road-cell"><strong>{complaint.road?.name || "Unknown road"}</strong><span>{complaint.location?.latitude?.toFixed?.(4)}, {complaint.location?.longitude?.toFixed?.(4)}</span></div></td>
              <td><StatusBadge status={complaint.status} /></td>
              <td>{complaint.assigned_technician_id ? <span className="assigned-tag"><Users size={13} />Tech #{complaint.assigned_technician_id}</span> : <select aria-label={`Assign complaint ${complaint.id}`} defaultValue="" onChange={(e) => e.target.value && onAssign?.(complaint.id, e.target.value)}><option value="">Assign…</option>{technicians.map((tech) => <option key={tech.id} value={tech.id}>{tech.name}</option>)}</select>}</td>
              <td><button type="button" className="admin-view-btn" onClick={() => onSelect(complaint.id)}><Eye size={14} />View</button></td>
            </tr>)}
            {sorted.length === 0 && <tr><td colSpan="7"><div className="empty-state">No complaints in this queue.</div></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export const PriorityQueue = memo(QueueView);

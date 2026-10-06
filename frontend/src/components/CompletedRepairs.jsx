import { CheckCircle2 } from "lucide-react";
import { damageSeverityLabel, roadDamageLabel } from "../utils/complaintLabels.js";

function completedDate(value) {
  return value ? new Date(`${value}Z`).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "Date unavailable";
}

export function CompletedRepairs({ repairs = [], onSelect }) {
  return (
    <div className="panel completed-repairs-panel">
      <div className="panel-header">
        <div>
          <h2><CheckCircle2 size={16} /> Completed Repairs</h2>
          <p>Historical repair records retained after leaving the active priority workload.</p>
        </div>
        <span className="count-badge">{repairs.length}</span>
      </div>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Complaint</th>
              <th>Road / issue</th>
              <th>Priority</th>
              <th>Technician</th>
              <th>Completed</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {repairs.map((repair) => (
              <tr
                key={repair.complaint_id}
                onClick={() => onSelect?.(repair.complaint_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect?.(repair.complaint_id);
                  }
                }}
                tabIndex={onSelect ? 0 : undefined}
                aria-label={`View details for completed complaint ${repair.complaint_id}`}
              >
                <td className="mono">#{String(repair.complaint_id).padStart(3, "0")}</td>
                <td>
                  <strong>{repair.road_name || repair.road_type || "Unknown road"}</strong>
                  <span className="completed-repair-issue">
                    {roadDamageLabel(repair.damage)} · {damageSeverityLabel(repair.damage)}
                  </span>
                </td>
                <td>{repair.priority || "Unknown"} · {repair.priority_score ?? "—"}</td>
                <td>{repair.technician_name || "Unavailable"}</td>
                <td>{completedDate(repair.completed_at)}</td>
                <td>{repair.status}</td>
              </tr>
            ))}
            {!repairs.length && (
              <tr><td colSpan="6"><div className="empty-state">No completed repairs recorded.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

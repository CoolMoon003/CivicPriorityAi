import { UserRound } from "lucide-react";

const COMPLETED_STATUSES = new Set(["REPAIRED", "VERIFIED"]);

export function TechnicianPanel({ technicians, complaints }) {
  return (
    <div className="tech-panel">
      <div className="panel-header">
        <h2>Technician Operations</h2>
        <span className="count-badge">{technicians.length}</span>
      </div>

      <div className="tech-grid">
        {technicians.length === 0 && (
          <div className="empty-state">No technicians registered.</div>
        )}

        {technicians.map((tech) => {
          const assigned = complaints.filter(
            (c) => c.assigned_technician_id === tech.id
          );
          const completed = assigned.filter((c) =>
            COMPLETED_STATUSES.has((c.status || "").toUpperCase())
          );
          const active = assigned.length - completed.length;

          return (
            <div key={tech.id} className="tech-card">
              <div className="tech-card-top">
                <div className="tech-avatar">
                  <UserRound size={16} strokeWidth={1.75} />
                </div>
                <div>
                  <strong>{tech.name}</strong>
                  {tech.email && <span>{tech.email}</span>}
                </div>
              </div>

              <div className="tech-stats">
                <div>
                  <span>Assigned</span>
                  <strong>{assigned.length}</strong>
                </div>
                <div>
                  <span>Active</span>
                  <strong>{active}</strong>
                </div>
                <div>
                  <span>Completed</span>
                  <strong>{completed.length}</strong>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

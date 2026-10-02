function timeLabel(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleString();
}

export function ActivityFeed({ complaints }) {
  const entries = [...complaints]
    .sort(
      (a, b) =>
        new Date(b.created_at || 0).getTime() -
        new Date(a.created_at || 0).getTime()
    )
    .slice(0, 8);

  return (
    <div className="activity-panel">
      <div className="panel-header">
        <h2>Live Activity</h2>
      </div>

      <div className="activity-list">
        {entries.length === 0 && (
          <div className="empty-state">No activity recorded yet.</div>
        )}

        {entries.map((c) => (
          <div key={c.id} className="activity-item">
            <span
              className={`activity-dot status-${(
                c.status || "unknown"
              ).toLowerCase()}`}
            />
            <div>
              <div className="activity-text">
                Issue #{c.id} &middot;{" "}
                {c.assigned_technician_id
                  ? "assigned, "
                  : "awaiting assignment, "}
                status {c.status}
              </div>
              <div className="activity-time">{timeLabel(c.created_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

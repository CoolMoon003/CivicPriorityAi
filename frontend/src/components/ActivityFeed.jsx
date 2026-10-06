const IST_TIMEZONE = "Asia/Kolkata";

function parseBackendTimestamp(value) {
  if (!value) return null;
  const text = String(value);
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)
    ? new Date(text)
    : new Date(`${text}Z`);
}

function timeLabel(iso) {
  const date = parseBackendTimestamp(iso);
  if (!date || Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone: IST_TIMEZONE,
  }).format(date);
}

export function ActivityFeed({ complaints }) {
  const entries = complaints
    .flatMap((complaint) =>
      (complaint.activity || []).map((event, index) => ({
        ...event,
        complaint,
        key: `${complaint.id}-${event.type}-${event.timestamp}-${index}`,
      }))
    )
    .sort((a, b) => {
      const aTime = parseBackendTimestamp(a.timestamp)?.getTime() || 0;
      const bTime = parseBackendTimestamp(b.timestamp)?.getTime() || 0;
      return bTime - aTime;
    })
    .slice(0, 8);

  return (
    <div className="activity-panel">
      <div className="panel-header">
        <h2>Latest complaint activity</h2>
        <p>Stored complaint, repair, and outcome events; not a full audit history.</p>
      </div>

      <div className="activity-list">
        {entries.length === 0 && (
          <div className="empty-state">No activity recorded yet.</div>
        )}

        {entries.map((entry) => (
          <div key={entry.key} className="activity-item">
            <span
              className={`activity-dot status-${(
                entry.complaint.status || "unknown"
              ).toLowerCase()}`}
            />
            <div>
              <div className="activity-text">
                Issue #{entry.complaint.id} &middot; {entry.label}
              </div>
              <div className="activity-time">{timeLabel(entry.timestamp)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

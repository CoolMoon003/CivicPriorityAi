import { roadDamageLabel } from "../utils/complaintLabels.js";

function Bar({ label, value, total, colorVar }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="bar-row">
      <div className="bar-row-label">
        <span>{label}</span>
        <strong>
          {value} &middot; {pct}%
        </strong>
      </div>
      <div className="bar-track">
        <div
          className="bar-fill"
          style={{ width: `${pct}%`, background: `var(${colorVar})` }}
        />
      </div>
    </div>
  );
}

const PRIORITY_COLORS = {
  CRITICAL: "--level-high",
  HIGH: "--level-high",
  MEDIUM: "--level-medium",
  LOW: "--level-low",
};

const STATUS_COLORS = {
  OPEN: "--level-medium",
  ASSIGNED: "--accent-signal",
  IN_PROGRESS: "--accent-signal",
  REPAIRED: "--level-success",
  VERIFIED: "--level-success",
  REJECTED: "--level-high",
};

export function AnalyticsPanel({ dashboard, complaints = [] }) {
  const summary = dashboard?.summary || {};
  const byPriority = dashboard?.by_priority || {};
  const byStatus = dashboard?.by_status || {};
  const total = summary.total_complaints || 0;
  const damageCounts = complaints.reduce((counts, complaint) => {
    const type = roadDamageLabel(complaint.damage);
    counts[type] = (counts[type] || 0) + 1;
    return counts;
  }, {});
  const modelPredictions = complaints.map((complaint) => complaint.ai_prediction)
    .filter((prediction) => prediction?.model_status === "available"
      && prediction.predicted_priority_score != null
      && prediction.baseline_priority_score != null);
  const average = (values) => values.length
    ? values.reduce((sum, value) => sum + Number(value || 0), 0) / values.length
    : null;
  const aiMean = average(modelPredictions.map((item) => item.predicted_priority_score));
  const baselineMean = average(modelPredictions.map((item) => item.baseline_priority_score));
  const differenceMean = average(modelPredictions.map((item) => item.difference));

  return (
    <div className="analytics-grid">
      <div className="panel">
        <div className="panel-header">
          <h2>Priority Distribution</h2>
        </div>
        <div className="bar-list">
          {Object.keys(byPriority).length === 0 && (
            <div className="empty-state">No data yet.</div>
          )}
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            .filter((k) => byPriority[k] !== undefined)
            .map((level) => (
              <Bar
                key={level}
                label={level}
                value={byPriority[level] || 0}
                total={total}
                colorVar={PRIORITY_COLORS[level]}
              />
            ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><h2>Complaints by Damage Type</h2></div>
        <div className="bar-list">
          {Object.keys(damageCounts).length === 0 ? <div className="empty-state">No complaint data yet.</div> : Object.entries(damageCounts).map(([type, count]) => <Bar key={type} label={type.replaceAll("_", " ")} value={count} total={total} colorVar="--accent-signal" />)}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><h2>AI and Baseline Signals</h2></div>
        {modelPredictions.length ? <div className="overview-grid">
          <div><span>Available AI predictions</span><strong>{modelPredictions.length}</strong></div>
          <div><span>Mean rule-based baseline</span><strong className="mono">{baselineMean.toFixed(1)}</strong></div>
          <div><span>Mean AI predicted priority</span><strong className="mono">{aiMean.toFixed(1)}</strong></div>
          <div><span>Mean difference (AI − baseline)</span><strong className="mono">{differenceMean > 0 ? "+" : ""}{differenceMean.toFixed(1)}</strong></div>
          <small>Separate signals from the baseline-derived prototype model; not a model accuracy metric.</small>
        </div> : <div className="empty-state">No available AI predictions.</div>}
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Status Distribution</h2>
        </div>
        <div className="bar-list">
          {Object.keys(byStatus).length === 0 && (
            <div className="empty-state">No data yet.</div>
          )}
          {Object.entries(byStatus).map(([status, count]) => (
            <Bar
              key={status}
              label={status.replace("_", " ")}
              value={count}
              total={total}
              colorVar={STATUS_COLORS[status] || "--level-low"}
            />
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>System Overview</h2>
        </div>
        <div className="overview-grid">
          <div>
            <span>Average priority</span>
            <strong className="mono">
              {total > 0 ? (summary.average_priority_score ?? "Unavailable") : "Unavailable"}
            </strong>
          </div>
          <div>
            <span>Recorded repair cost</span>
            <strong className="mono">
              {summary.repair_record_count ? `₹${Number(summary.total_repair_cost || 0).toLocaleString("en-IN")}` : "Unavailable"}
            </strong>
          </div>
          <div><span>Completed repair records</span><strong className="mono">{summary.completed_repair_count ?? 0}</strong></div>
          <div><span>Average recorded cost</span><strong className="mono">{summary.average_recorded_repair_cost == null ? "Unavailable" : `₹${Number(summary.average_recorded_repair_cost).toLocaleString("en-IN")}`}</strong></div>
          <div>
            <span>Total complaints</span>
            <strong className="mono">{total}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}

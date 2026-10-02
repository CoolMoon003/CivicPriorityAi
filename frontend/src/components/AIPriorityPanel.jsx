import { Cpu } from "lucide-react";
import { damageSeverityLabel, yoloConfidenceLabel } from "../utils/complaintLabels.js";

export function AIPriorityPanel({ selectedComplaint }) {
  return (
    <div className="ai-panel">
      <div className="ai-panel-header">
        <div className="ai-icon">
          <Cpu size={16} strokeWidth={1.75} />
        </div>
        <div>
          <h2>AI Priority Engine</h2>
          <span className="ai-status">
            <span className="status-dot up" />
            Active
          </span>
        </div>
      </div>

      <p className="ai-copy">
        The detector reports visible road damage. Overall priority is calculated
        separately from the road network, facility exposure, recurrence, and other available context.
      </p>

      {selectedComplaint ? (
        <div className="ai-factors">
          <div className="ai-factor">
            <span>Damage severity</span>
            <strong>{damageSeverityLabel(selectedComplaint.damage)}</strong>
          </div>
          <div className="ai-factor">
            <span>YOLO confidence</span>
            <strong>{yoloConfidenceLabel(selectedComplaint.damage, 0)}</strong>
          </div>
          <div className="ai-factor">
            <span>Overall priority score</span>
            <strong className="mono">
              {selectedComplaint.priority?.score ?? "—"}
            </strong>
          </div>
          <div className="ai-factor"><span>Overall priority level</span><strong>{selectedComplaint.priority?.level ?? "Unavailable"}</strong></div>
          <div className="ai-note">
            Detailed factor telemetry (road importance, facility exposure,
            recurrence, district safety context) is not currently exposed by
            the admin API and is not shown here to avoid fabricated metrics.
          </div>
        </div>
      ) : (
        <div className="ai-note standalone">
          Select a road issue to view its overall priority score. Extended factor
          telemetry is available during complaint analysis where the backend
          exposes it.
        </div>
      )}
    </div>
  );
}

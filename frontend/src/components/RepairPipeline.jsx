const STAGES = [
  { key: "OPEN", label: "Open" },
  { key: "ASSIGNED", label: "Assigned" },
  { key: "IN_PROGRESS", label: "In progress" },
  { key: "REPAIRED", label: "Repaired" },
  { key: "VERIFIED", label: "Verified" },
];

export function RepairPipeline({ byStatus }) {
  return (
    <div className="pipeline-panel">
      <div className="panel-header">
        <h2>Repair Pipeline</h2>
      </div>

      <div className="pipeline-track">
        {STAGES.map((stage, i) => (
          <div className="pipeline-stage" key={stage.key}>
            <div className="pipeline-node">
              <span className="pipeline-count">
                {byStatus?.[stage.key] ?? 0}
              </span>
              <span className="pipeline-label">{stage.label}</span>
            </div>
            {i < STAGES.length - 1 && <div className="pipeline-arrow" />}
          </div>
        ))}
      </div>
    </div>
  );
}

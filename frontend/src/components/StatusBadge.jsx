const STATUS_LABEL = {
  OPEN: "Open",
  ASSIGNED: "Assigned",
  IN_PROGRESS: "In progress",
  REPAIRED: "Repaired",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
};

const STATUS_CLASS = {
  OPEN: "status-open",
  ASSIGNED: "status-assigned",
  IN_PROGRESS: "status-progress",
  REPAIRED: "status-repaired",
  VERIFIED: "status-verified",
  REJECTED: "status-rejected",
};

export function StatusBadge({ status }) {
  const key = (status || "").toUpperCase();
  return (
    <span className={`status-badge ${STATUS_CLASS[key] || "status-unknown"}`}>
      {STATUS_LABEL[key] || status || "Unknown"}
    </span>
  );
}

const LEVEL_CLASS = {
  CRITICAL: "level-high",
  HIGH: "level-high",
  MEDIUM: "level-medium",
  LOW: "level-low",
};

export function PriorityBadge({ level }) {
  const key = (level || "").toUpperCase();
  return (
    <span className={`priority-badge ${LEVEL_CLASS[key] || "level-low"}`}>
      {key || "UNKNOWN"}
    </span>
  );
}

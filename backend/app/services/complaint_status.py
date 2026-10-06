ACTIVE_COMPLAINT_STATUSES = frozenset({"PENDING", "OPEN", "ASSIGNED", "IN_PROGRESS"})
COMPLETED_COMPLAINT_STATUSES = frozenset({"REPAIRED", "VERIFIED"})


def is_active_complaint_status(status: str | None) -> bool:
    return (status or "").upper() in ACTIVE_COMPLAINT_STATUSES

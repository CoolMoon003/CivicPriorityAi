"""Safe API representation for historical complaint damage fields."""

from backend.ai.detection_policy import DEFAULT_POLICY, NO_RELIABLE_DETECTION

VALID_DAMAGE_TYPES = {
    "pothole", "longitudinal_crack", "transverse_crack", "alligator_crack"
}
SEVERITY_BY_DAMAGE = {
    "pothole": "high", "alligator_crack": "high",
    "longitudinal_crack": "medium", "transverse_crack": "medium",
}


def complaint_damage_fields(complaint) -> dict:
    damage_type = str(complaint.damage_type or "unknown").strip().lower()
    severity = str(complaint.damage_severity or "unknown").strip().lower()
    try:
        confidence = float(complaint.damage_confidence) if complaint.damage_confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    state = DEFAULT_POLICY.state_for(confidence)
    if damage_type not in VALID_DAMAGE_TYPES or state == NO_RELIABLE_DETECTION:
        # Older rows can contain severity values from pre-detector demo logic.
        # A stale class/severity below the possible threshold is not evidence.
        damage_type = "unknown"
        severity = "unknown"
        confidence = 0.0
        state = NO_RELIABLE_DETECTION
    else:
        severity = SEVERITY_BY_DAMAGE[damage_type]
    return {
        "type": damage_type,
        "severity": severity,
        "confidence": confidence or 0.0,
        "detection_state": state,
    }

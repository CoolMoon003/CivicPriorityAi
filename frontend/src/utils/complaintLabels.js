const UNKNOWN_DAMAGE = new Set(["", "unknown", "none", "null"]);
const DAMAGE_TYPES = new Set(["pothole", "longitudinal_crack", "transverse_crack", "alligator_crack"]);
const POSSIBLE = "possible";

export function detectionState(damage) {
  if (damage?.detection_state) return damage.detection_state;
  if (DAMAGE_TYPES.has(String(damage?.type ?? "").trim().toLowerCase())) {
    const confidence = Number(damage?.confidence);
    if (Number.isFinite(confidence) && confidence >= 0.25) return "confirmed";
    if (Number.isFinite(confidence) && confidence >= 0.1) return POSSIBLE;
  }
  return "no_reliable_detection";
}

export function hasDetectedDamage(damage) {
  return DAMAGE_TYPES.has(String(damage?.type ?? "").trim().toLowerCase())
    && detectionState(damage) !== "no_reliable_detection";
}

export function detectionStateLabel(damage) {
  const state = detectionState(damage);
  if (state === "confirmed") return "Confirmed";
  if (state === POSSIBLE) return "Possible · AI uncertain";
  return "No reliable AI detection";
}

export function roadDamageLabel(damage) {
  if (!hasDetectedDamage(damage)) return "Not reliably detected";
  const label = String(damage.type).replaceAll("_", " ");
  return detectionState(damage) === POSSIBLE ? `Possible ${label}` : label;
}

export function damageSeverityLabel(damage) {
  if (!hasDetectedDamage(damage)) return "Not determined";
  const severity = String(damage?.severity ?? "").trim();
  if (UNKNOWN_DAMAGE.has(severity.toLowerCase())) return "Not determined";
  return detectionState(damage) === POSSIBLE ? `Potentially ${severity} · AI uncertain` : severity;
}

export function yoloConfidenceLabel(damage, digits = 1) {
  if (!hasDetectedDamage(damage)) return "0%";
  if (damage?.confidence == null) return "Not available";
  const confidence = Number(damage?.confidence);
  return Number.isFinite(confidence)
    ? `${(confidence * 100).toFixed(digits)}%`
    : "Not available";
}

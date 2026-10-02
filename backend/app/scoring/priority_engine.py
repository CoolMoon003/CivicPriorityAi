"""Transparent, configurable road complaint priority policy (0–100)."""
from dataclasses import dataclass
from typing import Any

from backend.ai.detection_policy import DEFAULT_POLICY, NO_RELIABLE_DETECTION, POSSIBLE

# Initial policy weights; tune with municipal stakeholders, not presented as optimal.
DAMAGE_WEIGHT = 30.0
CONFIDENCE_WEIGHT = 8.0
ROAD_IMPORTANCE_WEIGHT = 18.0
FACILITY_WEIGHT = 14.0
RECURRENCE_WEIGHT = 15.0
POPULATION_WEIGHT = 10.0
SAFETY_WEIGHT = 5.0
WEIGHTS = {
    "damage": DAMAGE_WEIGHT, "confidence": CONFIDENCE_WEIGHT,
    "road_importance": ROAD_IMPORTANCE_WEIGHT, "facilities": FACILITY_WEIGHT,
    "recurrence": RECURRENCE_WEIGHT, "population": POPULATION_WEIGHT,
    "district_safety": SAFETY_WEIGHT,
}

SEVERITY = {"low": 35.0, "medium": 65.0, "high": 100.0}
DAMAGE_SEVERITY = {
    "pothole": "high", "alligator_crack": "high",
    "longitudinal_crack": "medium", "transverse_crack": "medium",
}
ROAD_CLASS = {"motorway": 100, "trunk": 95, "primary": 85, "secondary": 70,
              "tertiary": 55, "unclassified": 35, "residential": 30,
              "service": 20, "living_street": 20}
FACILITIES = ("near_hospital", "near_clinic", "near_school", "near_college",
              "near_university", "near_police", "near_fire_station", "near_doctors")


@dataclass
class PriorityResult:
    score: float
    priority: str
    recommended_action: str
    factors: dict[str, Any]
    components: dict[str, Any]
    explanations: list[str]


class PriorityEngine:
    """Evaluate only evidence supplied by the existing detector/data pipeline."""

    # Backward-compatible name used by budget_optimizer for repair-cost estimates.
    # Alias the existing source of truth so scoring and optimization stay aligned.
    ROAD_IMPORTANCE = ROAD_CLASS

    @staticmethod
    def level_for_score(score: float) -> str:
        """Return the existing policy's score band for any 0–100 score."""
        return "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM" if score >= 35 else "LOW"

    @staticmethod
    def calculate(damage_type: str | None, severity: str | None,
                  confidence: float | None, road: dict | None,
                  repeat_reports: int = 0, recent_reports: int | None = None,
                  population: float | None = None,
                  detection_state: str | None = None) -> PriorityResult:
        road = road or {}
        class_key = str(damage_type or "unknown").strip().lower()
        severity_key = str(severity or "unknown").strip().lower()
        confidence_number = _number(confidence)
        valid_damage_types = {
            "pothole", "longitudinal_crack", "transverse_crack", "alligator_crack"
        }
        # Re-derive state from the central policy rather than trusting legacy
        # labels or callers. A class with no possible-level confidence is not
        # damage evidence and cannot inherit a stale severity.
        state = DEFAULT_POLICY.state_for(confidence_number)
        if class_key not in valid_damage_types or state == NO_RELIABLE_DETECTION:
            class_key = "unknown"
            severity_key = "unknown"
            confidence_number = None
            state = NO_RELIABLE_DETECTION
        else:
            # Damage severity is application policy derived from the class;
            # never trust a stale persisted severity for known classes.
            severity_key = DAMAGE_SEVERITY[class_key]

        raw_damage_value = SEVERITY.get(severity_key)
        damage_discount = 1.0
        if state == POSSIBLE:
            damage_discount = max(0.0, min(1.0, confidence_number or 0.0))
        damage_value = raw_damage_value * damage_discount if raw_damage_value is not None else None
        conf_value = (min(100.0, max(0.0, confidence_number * 100))
                      if confidence_number is not None else None)
        highway = road.get("highway") or road.get("road_type")
        if isinstance(highway, list): highway = highway[0] if highway else None
        road_value = float(ROAD_CLASS[str(highway).lower()]) if str(highway).lower() in ROAD_CLASS else None
        facility_count = sum(1 for field in FACILITIES if _positive(road.get(field)))
        facility_value = min(100.0, facility_count * 25.0) if any(field in road for field in FACILITIES) else None
        recurrence = max(0, int(repeat_reports or 0))
        recurrence_value = min(100.0, recurrence * 20.0)
        # Generated road feature rows repeat district totals. Keep this explicitly district context.
        accidents = _number(road.get("accidents_2023"))
        deaths = _number(road.get("deaths_2023"))
        if accidents is not None or deaths is not None:
            # Only district totals are available: use a simple indicator, not road-level normalization.
            safety_value = 50.0 if (accidents or 0) > 0 or (deaths or 0) > 0 else 0.0
        else:
            history = _number(road.get("accident_history_3yr"))
            safety_value = (50.0 if history > 0 else 0.0) if history is not None else None
        population_value = min(100.0, float(population) / 20000 * 100) if population is not None else None

        values = {"damage": damage_value, "confidence": conf_value,
                  "road_importance": road_value, "facilities": facility_value,
                  "recurrence": recurrence_value, "population": population_value,
                  "district_safety": safety_value}
        available = {k: v for k, v in values.items() if v is not None}
        denom = sum(WEIGHTS[k] for k in available)
        score = sum(v * WEIGHTS[k] for k, v in available.items()) / denom if denom else 0.0
        level = PriorityEngine.level_for_score(score)
        explanations = []
        if damage_value is not None and state == POSSIBLE:
            explanations.append(
                f"Possible {class_key.replace('_', ' ')} evidence; damage contribution "
                f"discounted by its {conf_value:.2f}% confidence ({damage_discount:.3f} factor)."
            )
        elif damage_value is not None:
            explanations.append(f"{severity_key.capitalize()} road damage confirmed by YOLO ({class_key.replace('_', ' ')}).")
        else:
            explanations.append("No reliable damage classification; no damage severity contribution was used.")
        if conf_value is not None: explanations.append(f"Detection confidence is {conf_value:.0f}%.")
        if road_value is not None: explanations.append(f"Road importance uses its mapped OSM {highway} classification.")
        if recurrence: explanations.append(f"{recurrence} other unresolved complaint(s) match this road segment or are within 50 m.")
        if facility_count: explanations.append(f"Nearby facility evidence includes {facility_count} mapped facility type(s).")
        if safety_value is not None: explanations.append("Safety component uses Vellore district accident/death context, not road-level accident records.")
        if population_value is None: explanations.append("Ward population unavailable: no complaint-to-ward mapping is present.")
        if facility_value is None: explanations.append("Nearby facility data unavailable for this road.")
        if road_value is None: explanations.append("Road importance unavailable for this road classification.")
        factors = {k: v for k, v in values.items() if v is not None}
        components = {k: {"value": v, "weight": WEIGHTS[k],
                          "weighted_points": round(v * WEIGHTS[k] / denom, 2) if denom and v is not None else 0}
                      for k, v in values.items()}
        if raw_damage_value is not None and state == POSSIBLE:
            components["damage"].update({
                "undiscounted_value": raw_damage_value,
                "discount_factor": round(damage_discount, 4),
                "detection_state": state,
            })
        return PriorityResult(round(score, 1), level,
            "Urgent inspection and repair planning" if level in {"CRITICAL", "HIGH"} else "Review and schedule based on field assessment",
            factors, components, explanations)


def _number(value):
    try:
        if value in (None, "", "nan"): return None
        return float(value)
    except (TypeError, ValueError): return None


def _positive(value):
    number = _number(value)
    return number > 0 if number is not None else value is True

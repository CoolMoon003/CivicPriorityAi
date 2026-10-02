"""One versioned, deterministic feature builder for priority ML.

Only persisted complaint evidence and existing Vellore road feature data are
used. Population remains missing until a defensible road-to-ward join exists.
"""
import csv
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timedelta, timezone

from backend.app.models.complaint import Complaint
from backend.app.scoring.priority_engine import DAMAGE_SEVERITY, FACILITIES, PriorityEngine
from backend.app.services.duplicate_service import DuplicateService
from backend.ai.detection_policy import DEFAULT_POLICY, NO_RELIABLE_DETECTION

BASE_DIR = Path(__file__).resolve().parents[3]
ROAD_FEATURES_CSV = BASE_DIR / "data" / "processed" / "vellore_road_features.csv"
FEATURE_VERSION = "priority_features_v1"
DAMAGE_TYPES = ("pothole", "longitudinal_crack", "transverse_crack", "alligator_crack", "unknown")
SEVERITIES = ("low", "medium", "high", "unknown")

# Stable ordering is stored with every model artifact.
FEATURE_NAMES = tuple(
    [f"damage_type_{name}" for name in DAMAGE_TYPES]
    + [f"severity_{name}" for name in SEVERITIES]
    + ["damage_confidence", "road_importance", "road_length_m", "road_lanes", "road_maxspeed"]
    + list(FACILITIES)
    + ["unresolved_complaints_older_30d", "recent_complaints_30d", "district_accidents_2023",
       "district_deaths_2023", "district_accident_history_3yr", "district_death_history_3yr",
       "ward_population", "ward_population_available"]
    + ["baseline_priority_score"]
)


@lru_cache(maxsize=1)
def _road_rows():
    if not ROAD_FEATURES_CSV.exists():
        return {}
    try:
        with ROAD_FEATURES_CSV.open(newline="", encoding="utf-8") as stream:
            return {(str(row.get("u")), str(row.get("v")), str(row.get("key"))): row
                    for row in csv.DictReader(stream)}
    except (OSError, csv.Error):
        return {}


def _number(value):
    try:
        if value in (None, "", "nan", "NaN"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def road_features_for(complaint):
    road = {"highway": complaint.road_type}
    if complaint.road_u is not None:
        row = _road_rows().get((str(complaint.road_u), str(complaint.road_v), str(complaint.road_key)))
        if row:
            road.update(row)
    return road


def recurrence_for(complaint, db):
    others = (db.query(Complaint).filter(Complaint.id != complaint.id,
               Complaint.status != "RESOLVED").all())
    matches = [other for other in others if
        (complaint.road_u is not None and other.road_u == complaint.road_u
         and other.road_v == complaint.road_v and other.road_key == complaint.road_key)
        or DuplicateService.distance_m(complaint.latitude, complaint.longitude,
                                       other.latitude, other.longitude) <= DuplicateService.MAX_DISTANCE_METERS]
    now = complaint.created_at
    recent = sum(1 for other in matches if now and other.created_at and
                 0 <= (now - other.created_at).total_seconds() <= 30 * 86400)
    return len(matches), recent


def recent_match_count(matches, now=None):
    """Count duplicate-service matches in the same 30-day bucket as inference."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(days=DuplicateService.RECENT_DAYS)
    recent = 0
    for match in matches or []:
        created_at = match.get("created_at")
        if not created_at:
            continue
        try:
            created_at = datetime.fromisoformat(created_at)
        except (TypeError, ValueError):
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if cutoff <= created_at.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            recent += 1
    return recent


def build_feature_values(damage_type, severity, confidence, road, recurrence=0,
                         recent_recurrence=0, baseline_score=None):
    values = {name: 0.0 for name in FEATURE_NAMES}
    damage = str(damage_type or "unknown").lower()
    severity_key = str(severity or "unknown").lower()
    if damage not in DAMAGE_TYPES:
        damage = "unknown"
    confidence_number = _number(confidence)
    if damage == "unknown" or damage not in DAMAGE_TYPES or DEFAULT_POLICY.state_for(confidence_number) == NO_RELIABLE_DETECTION:
        # Legacy rows can carry a stale severity despite having no qualifying
        # detector class/confidence. Do not feature the stale class or severity.
        damage = "unknown"
        severity_key = "unknown"
        confidence = 0.0
    else:
        severity_key = DAMAGE_SEVERITY[damage]
        confidence = confidence_number
    if severity_key not in SEVERITIES:
        severity_key = "unknown"
    values[f"damage_type_{damage}"] = 1.0
    values[f"severity_{severity_key}"] = 1.0
    values["damage_confidence"] = _number(confidence)
    highway = road.get("highway") or road.get("road_type")
    if isinstance(highway, list):
        highway = highway[0] if highway else None
    values["road_importance"] = _number(PriorityEngine.ROAD_IMPORTANCE.get(str(highway).lower()))
    # OSMnx graph edge `length` is stored in meters in the existing network export.
    values["road_length_m"] = _number(road.get("length"))
    values["road_lanes"] = _number(road.get("lanes"))
    values["road_maxspeed"] = _number(road.get("maxspeed"))
    for field in FACILITIES:
        values[field] = _number(road.get(field))
    # Disjoint age buckets prevent the same recurrence record being counted twice.
    recent = min(max(0, recent_recurrence), max(0, recurrence))
    values["recent_complaints_30d"] = float(recent)
    values["unresolved_complaints_older_30d"] = float(max(0, recurrence) - recent)
    # These values are duplicated district context, not road-level observations.
    for feature, source in (("district_accidents_2023", "accidents_2023"),
                            ("district_deaths_2023", "deaths_2023"),
                            ("district_accident_history_3yr", "accident_history_3yr"),
                            ("district_death_history_3yr", "death_history_3yr")):
        values[feature] = _number(road.get(source))
    values["ward_population"] = None  # no complaint/road -> ward mapping exists
    values["ward_population_available"] = 0.0
    values["baseline_priority_score"] = _number(baseline_score)
    return values


def build_feature_vector(**kwargs):
    values = build_feature_values(**kwargs)
    return [values[name] for name in FEATURE_NAMES]


def build_for_complaint(complaint, db, baseline_score=None):
    road = road_features_for(complaint)
    recurrence, recent = recurrence_for(complaint, db)
    damage_type = str(complaint.damage_type or "unknown").lower()
    severity = complaint.damage_severity if damage_type != "unknown" else "unknown"
    confidence = complaint.damage_confidence if damage_type != "unknown" else 0.0
    baseline = PriorityEngine.calculate(damage_type, severity,
        confidence, road, repeat_reports=recurrence)
    if baseline_score is not None:
        baseline_score = baseline_score
    else:
        baseline_score = baseline.score
    values = build_feature_values(damage_type, severity,
        confidence, road, recurrence, recent, baseline_score)
    return values, {"road": road, "recurrence_count": recurrence,
                    "recent_recurrence_count": recent, "baseline": baseline}

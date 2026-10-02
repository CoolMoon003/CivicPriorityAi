from pathlib import Path
import csv
import json
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database.database import get_db
from backend.app.models.complaint import Complaint
from backend.app.models.repair import Repair
from backend.app.models.outcome import Outcome
from backend.app.optimization.budget_optimizer import (
    RepairCandidate,
    estimate_repair_cost,
    knapsack_01,
)
from backend.app.services.impact_score_service import get_impact_score
from backend.app.services.priority_features import build_for_complaint
from backend.app.services.priority_predictor import predict_values
from backend.app.services.damage_presentation import complaint_damage_fields
from backend.app.services.annotated_image_service import existing_annotated_path
from backend.app.services.complaint_deletion import (
    safe_complaint_uploads_to_remove,
    valid_admin_delete_token,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_PUBLIC_DIR = BASE_DIR / "data" / "public"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"

ROAD_FEATURES_CSV = DATA_PROCESSED_DIR / "vellore_road_features.csv"
FACILITIES_GEOJSON = DATA_PUBLIC_DIR / "vellore_public_facilities.geojson"
ACCIDENTS_CSV = DATA_PUBLIC_DIR / "tamil_nadu_road_accidents_2021_2023.csv"
WARD_POPULATION_CSV = DATA_PUBLIC_DIR / "vellore_ward_population.csv"


def _priority_evidence(complaint: Complaint, db: Session) -> dict:
    """Build score evidence from the matched OSM feature row and live recurrence."""
    features, context = build_for_complaint(complaint, db)
    result = context["baseline"]
    recurrence = context["recurrence_count"]
    ai_prediction = predict_values(features, result.score)
    return {"priority_score": result.score, "priority_level": result.priority,
            "components": result.components, "explanations": result.explanations,
            "recurrence_count": recurrence, "evidence": result.factors,
            "ai_prediction": ai_prediction}


def _priority_item(complaint: Complaint, db: Session) -> dict:
    priority = _priority_evidence(complaint, db)
    return {"complaint_id": complaint.id, "road_id": (f"{complaint.road_u}-{complaint.road_v}-{complaint.road_key}" if complaint.road_u is not None else None),
        **priority, "damage": complaint_damage_fields(complaint),
        "road": {"name": complaint.road_name, "type": complaint.road_type},
        "location": {"latitude": complaint.latitude, "longitude": complaint.longitude},
        "status": complaint.status, "image_path": complaint.image_path,
        "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
        "assigned_technician_id": complaint.assigned_technician_id,
        "ai_prediction": priority["ai_prediction"]}


@router.get("/priorities")
def priority_queue(limit: int = Query(100, ge=1, le=500), level: str | None = None,
                   status: str | None = None, db: Session = Depends(get_db)):
    complaints = db.query(Complaint).all()
    items = [_priority_item(c, db) for c in complaints]
    if level: items = [i for i in items if i["priority_level"] == level.upper()]
    if status: items = [i for i in items if i["status"] == status.upper()]
    items.sort(key=lambda i: i["priority_score"], reverse=True)
    return {"count": len(items), "items": items[:limit]}


@router.get("/priorities/{complaint_id}")
def priority_detail(complaint_id: int, db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return _priority_item(complaint, db)


# --------------------------------------------------
# 1. List complaints
# --------------------------------------------------

@router.get("/complaints")
def list_complaints(
    status: str | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Complaint)

    if status:
        query = query.filter(
            Complaint.status == status.upper()
        )

    if priority:
        query = query.filter(
            Complaint.priority == priority.upper()
        )

    complaints = (
        query
        .order_by(
            Complaint.priority_score.desc(),
            Complaint.created_at.desc(),
        )
        .all()
    )

    return {
        "count": len(complaints),
        "complaints": [
            {
                "id": complaint.id,
                "location": {
                    "latitude": complaint.latitude,
                    "longitude": complaint.longitude,
                },
                "road": {
                    "name": complaint.road_name,
                    "type": complaint.road_type,
                },
                "damage": complaint_damage_fields(complaint),
                "priority": {
                    "score": complaint.priority_score,
                    "level": complaint.priority,
                },
                "status": complaint.status,
                "duplicate_of_id": complaint.duplicate_of_id,
                "description": complaint.description,
                "image_path": complaint.image_path,
                "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
                "assigned_technician_id": (
                    complaint.assigned_technician_id
                ),
                "created_at": (
                    complaint.created_at.isoformat()
                    if complaint.created_at
                    else None
                ),
            }
            for complaint in complaints
        ],
    }


# --------------------------------------------------
# 2. Get single complaint
# --------------------------------------------------

@router.get("/complaints/{complaint_id}")
def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    priority_evidence = _priority_evidence(complaint, db)

    return {
        "id": complaint.id,
        "location": {
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
        },
        "road": {
            "name": complaint.road_name,
            "type": complaint.road_type,
            "u": complaint.road_u,
            "v": complaint.road_v,
            "key": complaint.road_key,
        },
        "damage": complaint_damage_fields(complaint),
        "priority": {
            "score": priority_evidence["priority_score"],
            "level": priority_evidence["priority_level"],
            "components": priority_evidence["components"],
            "explanations": priority_evidence["explanations"],
            "recurrence_count": priority_evidence["recurrence_count"],
            "recommended_action": (
                complaint.recommended_action
            ),
        },
        "ai_prediction": priority_evidence["ai_prediction"],
        "status": complaint.status,
        "duplicate_of_id": complaint.duplicate_of_id,
        "description": complaint.description,
        "image_path": complaint.image_path,
        "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
        "assigned_technician_id": (
            complaint.assigned_technician_id
        ),
        "created_at": (
            complaint.created_at.isoformat()
            if complaint.created_at
            else None
        ),
        "updated_at": (
            complaint.updated_at.isoformat()
            if complaint.updated_at
            else None
        ),
    }


# --------------------------------------------------
# 3. Update complaint status
# --------------------------------------------------

@router.patch("/complaints/{complaint_id}/status")
def update_status(
    complaint_id: int,
    status: str,
    db: Session = Depends(get_db),
):
    allowed_statuses = {
        "OPEN",
        "ASSIGNED",
        "IN_PROGRESS",
        "REPAIRED",
        "VERIFIED",
        "REJECTED",
    }

    status = status.upper()

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid status",
                "allowed": sorted(allowed_statuses),
            },
        )

    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    complaint.status = status

    db.commit()
    db.refresh(complaint)

    return {
        "message": "Complaint status updated",
        "complaint_id": complaint.id,
        "status": complaint.status,
    }


@router.patch("/complaints/{complaint_id}/duplicate-of/{existing_id}")
def link_duplicate(complaint_id: int, existing_id: int, db: Session = Depends(get_db)):
    """Admin review action: retain both records and explicitly link the duplicate."""
    if complaint_id == existing_id:
        raise HTTPException(status_code=400, detail="A complaint cannot be linked to itself")
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    existing = db.query(Complaint).filter(Complaint.id == existing_id).first()
    if complaint is None or existing is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    # Keep the link graph acyclic even though upgraded SQLite schemas do not
    # have a database-level self-FK constraint.
    cursor = existing
    visited = set()
    while cursor is not None:
        if cursor.id == complaint.id:
            raise HTTPException(status_code=400, detail="Duplicate links cannot form a cycle")
        if cursor.id in visited:
            raise HTTPException(status_code=409, detail="The existing duplicate link chain is already cyclic")
        visited.add(cursor.id)
        cursor = db.query(Complaint).filter(Complaint.id == cursor.duplicate_of_id).first() if cursor.duplicate_of_id else None
    complaint.duplicate_of_id = existing.id
    db.commit()
    return {"message": "Duplicate link recorded; both complaint records are preserved", "complaint_id": complaint.id, "duplicate_of_id": existing.id}


@router.delete("/complaints/{complaint_id}")
def delete_complaint(
    complaint_id: int,
    x_civic_admin_token: str | None = Header(default=None, alias="X-Civic-Admin-Token"),
    db: Session = Depends(get_db),
):
    configured_token = os.getenv("CIVIC_ADMIN_DELETE_TOKEN")
    if not configured_token:
        raise HTTPException(
            status_code=503,
            detail="Complaint deletion is disabled until CIVIC_ADMIN_DELETE_TOKEN is configured.",
        )
    if len(configured_token) < 32:
        raise HTTPException(
            status_code=503,
            detail="CIVIC_ADMIN_DELETE_TOKEN must be at least 32 characters.",
        )
    if not valid_admin_delete_token(configured_token, x_civic_admin_token):
        raise HTTPException(status_code=403, detail="Admin deletion token is missing or invalid")

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    linked_duplicates = db.query(Complaint.id).filter(Complaint.duplicate_of_id == complaint.id).all()
    if linked_duplicates:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This complaint is the target of duplicate links. Relink those complaints before deletion.",
                "linked_duplicate_ids": [row[0] for row in linked_duplicates],
            },
        )

    shared_image = (
        db.query(Complaint.id)
        .filter(Complaint.image_path == complaint.image_path, Complaint.id != complaint.id)
        .first()
        is not None
    ) if complaint.image_path else False
    cleanup_candidates = safe_complaint_uploads_to_remove(
        complaint.image_path, BASE_DIR, shared_reference=shared_image
    )

    try:
        db.query(Outcome).filter(Outcome.complaint_id == complaint.id).delete(synchronize_session=False)
        db.query(Repair).filter(Repair.complaint_id == complaint.id).delete(synchronize_session=False)
        db.delete(complaint)
        db.commit()
    except Exception:
        db.rollback()
        raise

    removed_files = []
    cleanup_errors = []
    for path in cleanup_candidates:
        try:
            if not path.is_file():
                continue
            path.unlink(missing_ok=True)
            removed_files.append(path.name)
        except OSError as exc:
            cleanup_errors.append(f"{path.name}: {exc}")
    return {
        "message": "Complaint deleted",
        "complaint_id": complaint_id,
        "removed_upload_files": removed_files,
        "image_cleanup_scope": "owned_unshared_upload" if cleanup_candidates else "preserved_shared_or_non_user_asset",
        "file_cleanup_errors": cleanup_errors,
    }


# --------------------------------------------------
# 4. Assign technician
# --------------------------------------------------

@router.patch("/complaints/{complaint_id}/assign")
def assign_technician(
    complaint_id: int,
    technician_id: int,
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .filter(Complaint.id == complaint_id)
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    complaint.assigned_technician_id = technician_id

    if complaint.status == "OPEN":
        complaint.status = "ASSIGNED"

    db.commit()
    db.refresh(complaint)

    return {
        "message": "Technician assigned",
        "complaint_id": complaint.id,
        "technician_id": technician_id,
        "status": complaint.status,
    }


# --------------------------------------------------
# 5. Dashboard statistics
# --------------------------------------------------

@router.get("/statistics")
def statistics(
    db: Session = Depends(get_db),
):
    complaints = db.query(Complaint).all()

    total = len(complaints)

    by_status = {}
    by_priority = {}

    for complaint in complaints:
        status = complaint.status or "UNKNOWN"
        priority = complaint.priority or "UNKNOWN"

        by_status[status] = (
            by_status.get(status, 0) + 1
        )

        by_priority[priority] = (
            by_priority.get(priority, 0) + 1
        )

    scores = [
        complaint.priority_score
        for complaint in complaints
        if complaint.priority_score is not None
    ]

    average_priority = (
        round(sum(scores) / len(scores), 2)
        if scores
        else 0
    )

    return {
        "total_complaints": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "average_priority_score": average_priority,
    }


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
):
    complaints = db.query(Complaint).all()

    by_status = {}
    by_priority = {}

    for complaint in complaints:
        status = complaint.status or "UNKNOWN"
        priority = complaint.priority or "UNKNOWN"

        by_status[status] = by_status.get(status, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1

    # Import locally to avoid unnecessary model-loading issues.
    from backend.app.models.repair import Repair

    repairs = db.query(Repair).all()
    recorded_costs = [float(repair.repair_cost) for repair in repairs
                      if repair.repair_cost is not None]
    repair_cost = sum(recorded_costs)
    completed_repairs = sum(1 for repair in repairs if repair.completed_at is not None)

    scores = [
        c.priority_score
        for c in complaints
        if c.priority_score is not None
    ]

    top_complaints = sorted(
        complaints,
        key=lambda c: c.priority_score or 0,
        reverse=True,
    )[:10]

    return {
        "project": "CivicPriorityAI",
        "location": "Vellore, Tamil Nadu",
        "data_note": (
            "This workspace includes pre-existing development/demo records and records explicitly marked SYNTHETIC DEMO; it is not an official government complaint feed."
        ),
        "summary": {
            "total_complaints": len(complaints),
            "average_priority_score": (
                round(sum(scores) / len(scores), 2)
                if scores else 0
            ),
            "total_repair_cost": round(repair_cost, 2),
            "repair_record_count": len(repairs),
            "completed_repair_count": completed_repairs,
            "average_recorded_repair_cost": (round(repair_cost / len(recorded_costs), 2)
                                              if recorded_costs else None),
        },
        "by_status": by_status,
        "by_priority": by_priority,
        "top_complaints": [
            {
                "id": c.id,
                "road_name": c.road_name,
                "road_type": c.road_type,
                "priority_score": c.priority_score,
                "priority": c.priority,
                "status": c.status,
                "latitude": c.latitude,
                "longitude": c.longitude,
            }
            for c in top_complaints
        ],
    }


# --------------------------------------------------
# 4. Vellore local data summary
# --------------------------------------------------

def _count_csv_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = sum(1 for _ in reader)
        # Subtract header row if the file has any rows.
        return max(rows - 1, 0)
    except Exception:
        return None


def _facility_summary() -> dict:
    if not FACILITIES_GEOJSON.exists():
        return {"total_facilities": None, "by_type": None}

    try:
        with open(FACILITIES_GEOJSON, encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        by_type: dict[str, int] = {}

        for feature in features:
            props = feature.get("properties", {}) or {}
            amenity = props.get("amenity") or "unknown"
            by_type[amenity] = by_type.get(amenity, 0) + 1

        return {
            "total_facilities": len(features),
            "by_type": by_type,
        }
    except Exception:
        return {"total_facilities": None, "by_type": None}


def _accident_summary() -> dict:
    if not ACCIDENTS_CSV.exists():
        return {"accidents_by_year": None, "deaths_by_year": None}

    try:
        with open(ACCIDENTS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            vellore_row = None
            for row in reader:
                if (row.get("District") or "").strip().upper() == "VELLORE":
                    vellore_row = row
                    break

        if vellore_row is None:
            return {"accidents_by_year": None, "deaths_by_year": None}

        years = ["2021", "2022", "2023"]

        accidents_by_year = {}
        deaths_by_year = {}

        for year in years:
            acc_val = vellore_row.get(f"Total Accidents {year}")
            death_val = vellore_row.get(f"Total Deaths {year}")

            accidents_by_year[year] = (
                int(float(acc_val)) if acc_val not in (None, "") else None
            )
            deaths_by_year[year] = (
                int(float(death_val)) if death_val not in (None, "") else None
            )

        return {
            "accidents_by_year": accidents_by_year,
            "deaths_by_year": deaths_by_year,
        }
    except Exception:
        return {"accidents_by_year": None, "deaths_by_year": None}


def _ward_population_summary() -> dict:
    if not WARD_POPULATION_CSV.exists():
        return {"ward_count": None, "total_population": None}

    try:
        with open(WARD_POPULATION_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_population = 0
        for row in rows:
            total_val = row.get("total")
            if total_val not in (None, ""):
                total_population += float(total_val)

        return {
            "ward_count": len(rows),
            "total_population": (
                int(total_population) if rows else None
            ),
        }
    except Exception:
        return {"ward_count": None, "total_population": None}


def _find_civic_issues_file() -> Path | None:
    # No fixed filename is established in this project yet, so
    # look for a plausibly-named file under the existing public/
    # and processed/ data directories rather than guessing a path.
    candidates = []

    for directory in (DATA_PUBLIC_DIR, DATA_PROCESSED_DIR):
        if not directory.exists():
            continue
        for pattern in ("*namma*", "*civic*"):
            candidates.extend(directory.glob(pattern))

    return candidates[0] if candidates else None


def _civic_issues_summary() -> dict:
    civic_file = _find_civic_issues_file()

    if civic_file is None:
        return {"total_civic_issues": None, "source_file": None,
                "availability": "unavailable"}

    try:
        if civic_file.suffix.lower() == ".csv":
            count = _count_csv_rows(civic_file)
        elif civic_file.suffix.lower() in (".geojson", ".json"):
            with open(civic_file, encoding="utf-8") as f:
                data = json.load(f)
            count = len(data.get("features", data if isinstance(data, list) else []))
        else:
            count = None

        if count is not None and civic_file.suffix.lower() in (".geojson", ".json"):
            features = data.get("features", data if isinstance(data, list) else [])
            # The local NammaTN/Vellore files have no source URL or provenance
            # metadata. Do not surface their unverified records as public counts.
            if any(not (feature.get("properties") or {}).get("source")
                   or not (feature.get("properties") or {}).get("url")
                   for feature in features):
                return {"total_civic_issues": None, "source_file": None,
                        "availability": "source provenance unverified"}

        return {
            "total_civic_issues": count,
            "source_file": str(civic_file.relative_to(BASE_DIR)),
            "availability": "available",
        }
    except Exception:
        return {"total_civic_issues": None, "source_file": None,
                "availability": "unavailable"}


# --------------------------------------------------
# 6. Budget-constrained repair portfolio optimizer (0/1 knapsack)
# --------------------------------------------------

# Complaints in these statuses have not yet been repaired, so they
# are the pool eligible for a *future* repair-budget allocation.
# REPAIRED / VERIFIED / REJECTED complaints are excluded — there is
# nothing left to allocate budget toward.
_ELIGIBLE_FOR_OPTIMIZATION_STATUSES = {"OPEN", "ASSIGNED", "IN_PROGRESS"}


def _existing_repair_cost(db: Session, complaint_id: int) -> float | None:
    """
    Return a verified repair_cost already recorded for this complaint,
    if one exists — never fabricated. If more than one Repair row
    exists for the complaint (e.g. a redo), the most recent one with
    a recorded cost wins.
    """

    repair = (
        db.query(Repair)
        .filter(
            Repair.complaint_id == complaint_id,
            Repair.repair_cost.isnot(None),
        )
        .order_by(Repair.created_at.desc())
        .first()
    )

    return repair.repair_cost if repair else None


@router.get("/optimization")
def optimize_repair_budget(
    budget: float = Query(
        ...,
        gt=0,
        description="Total repair budget available, in INR.",
    ),
    db: Session = Depends(get_db),
):
    """
    Select the repair portfolio (subset of not-yet-repaired
    complaints) that maximizes total impact without exceeding
    `budget`, using a real 0/1 knapsack solved by dynamic
    programming — i.e. it evaluates combinations of complaints, not
    just a sorted/greedy list.

    Impact comes from the existing priority engine's output
    (`Complaint.priority_score`, via `impact_score_service`) — it is
    never recomputed or replaced here.

    Cost comes from an existing verified `Repair.repair_cost` when
    one exists; otherwise from a clearly-labeled deterministic
    ESTIMATE (`estimate_repair_cost`), since most eligible complaints
    are, by definition, not repaired yet and so have no verified cost.
    """

    complaints = (
        db.query(Complaint)
        .filter(Complaint.status.in_(_ELIGIBLE_FOR_OPTIMIZATION_STATUSES))
        .all()
    )

    candidates: list[RepairCandidate] = []
    excluded: list[dict] = []
    image_paths = {complaint.id: complaint.image_path for complaint in complaints}
    annotated_image_paths = {
        complaint.id: existing_annotated_path(complaint.image_path, BASE_DIR)
        for complaint in complaints
    }

    for complaint in complaints:
        damage_evidence = complaint_damage_fields(complaint)
        impact_score = get_impact_score(complaint)

        if impact_score is None:
            # Explicitly reported, never silently dropped or
            # fabricated as zero.
            excluded.append(
                {
                    "complaint_id": complaint.id,
                    "reason": (
                        "no priority_score recorded yet — impact "
                        "unknown, cannot be optimized over"
                    ),
                }
            )
            continue

        verified_cost = _existing_repair_cost(db, complaint.id)

        if verified_cost is not None:
            cost = float(verified_cost)
            cost_is_estimated = False
            cost_note = "verified repair_cost from repairs table"
        else:
            cost = estimate_repair_cost(
                damage_type=damage_evidence["type"],
                severity=damage_evidence["severity"],
                road_type=complaint.road_type,
            )
            cost_is_estimated = True
            cost_note = (
                "ESTIMATE — no verified repair record exists yet for "
                "this complaint; cost derived from damage type, "
                "severity and road importance only"
            )

        candidates.append(
            RepairCandidate(
                complaint_id=complaint.id,
                impact_score=impact_score,
                estimated_cost=cost,
                cost_is_estimated=cost_is_estimated,
                priority_level=complaint.priority,
                damage_type=damage_evidence["type"],
                severity=damage_evidence["severity"],
                cost_note=cost_note,
                confidence=damage_evidence["confidence"],
                detection_state=damage_evidence["detection_state"],
            )
        )

    result = knapsack_01(candidates, budget)

    selected = result["selected"]
    unselected = result["unselected"]

    return {
        "budget": budget,
        "selected_repairs": [
            {
                "complaint_id": c.complaint_id,
                "image_path": image_paths.get(c.complaint_id),
                "annotated_image_path": annotated_image_paths.get(c.complaint_id),
                "impact_score": c.impact_score,
                "estimated_cost": c.estimated_cost,
                "cost_is_estimated": c.cost_is_estimated,
                "cost_note": c.cost_note,
                "priority_level": c.priority_level,
                "damage_type": c.damage_type or "unknown",
                "severity": "unknown" if (c.damage_type or "unknown").lower() == "unknown" else c.severity,
                "confidence": c.confidence or 0.0,
                "detection_state": c.detection_state or "no_reliable_detection",
            }
            for c in selected
        ],
        "selected_count": len(selected),
        "total_cost": result["total_cost"],
        "total_impact": result["total_impact"],
        "remaining_budget": round(budget - result["total_cost"], 2),
        "unselected_count": len(unselected),
        "optimization_method": result["optimization_method"],
        "cost_quantization_unit": result["cost_quantization_unit"],
        "excluded_missing_impact_score": excluded,
    }


@router.get("/vellore-summary")
def vellore_summary():
    facility_data = _facility_summary()
    accident_data = _accident_summary()
    ward_data = _ward_population_summary()
    civic_data = _civic_issues_summary()

    return {
        "road_segments": {
            "total": _count_csv_rows(ROAD_FEATURES_CSV),
        },
        "public_facilities": facility_data,
        "accidents": accident_data,
        "ward_population": ward_data,
        "civic_issues": civic_data,
    }

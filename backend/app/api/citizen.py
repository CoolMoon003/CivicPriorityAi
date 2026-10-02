"""Citizen profile and owner-scoped complaint views for the existing demo role flow.

The project currently has no authentication/session mechanism. The profile ID is
therefore a browser-persisted demo identity, not proof of identity or authorization.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.admin import _priority_evidence
from backend.app.database.database import get_db
from backend.app.models.complaint import Complaint
from backend.app.models.outcome import Outcome
from backend.app.models.repair import Repair
from backend.app.models.user import User
from backend.app.services.damage_presentation import complaint_damage_fields
from backend.app.services.annotated_image_service import existing_annotated_path


router = APIRouter(prefix="/citizen", tags=["Citizen"])
BASE_DIR = Path(__file__).resolve().parents[3]


class CitizenProfileInput(BaseModel):
    name: str
    email: str
    phone: str | None = None


def _citizen_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
    if user is None or (user.role or "").upper() != "CITIZEN":
        raise HTTPException(status_code=404, detail="Citizen profile not found")
    return user


@router.post("/profiles")
def create_or_get_profile(payload: CitizenProfileInput, db: Session = Depends(get_db)):
    name = payload.name.strip()
    email = payload.email.strip().lower()
    if not name or "@" not in email:
        raise HTTPException(status_code=422, detail="A name and valid email are required")
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        if (user.role or "").upper() != "CITIZEN":
            raise HTTPException(status_code=409, detail="Email belongs to a non-citizen account")
        return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}

    user = User(name=name, email=email, phone=payload.phone, role="CITIZEN", is_active=1)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}


@router.get("/profiles/{user_id}")
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = _citizen_user(db, user_id)
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone}


@router.get("/{user_id}/complaints")
def my_complaints(user_id: int, db: Session = Depends(get_db)):
    _citizen_user(db, user_id)
    rows = (db.query(Complaint).filter(Complaint.user_id == user_id)
            .order_by(Complaint.created_at.desc()).all())
    statuses = {"pending": 0, "in_progress": 0, "resolved": 0, "rejected": 0}
    items = []
    for complaint in rows:
        priority_evidence = _priority_evidence(complaint, db)
        status = (complaint.status or "OPEN").upper()
        if status == "OPEN":
            statuses["pending"] += 1
        elif status in {"ASSIGNED", "IN_PROGRESS"}:
            statuses["in_progress"] += 1
        elif status in {"REPAIRED", "VERIFIED", "RESOLVED"}:
            statuses["resolved"] += 1
        elif status == "REJECTED":
            statuses["rejected"] += 1
        items.append({
            "id": complaint.id,
            "image_path": complaint.image_path,
            "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
            "description": complaint.description,
            "damage": complaint_damage_fields(complaint),
            "priority": {"score": priority_evidence["priority_score"],
                         "level": priority_evidence["priority_level"]},
            "status": complaint.status,
            "location": {"latitude": complaint.latitude, "longitude": complaint.longitude},
            "road": {"name": complaint.road_name, "type": complaint.road_type},
            "created_at": complaint.created_at.isoformat() if complaint.created_at else None,
        })
    return {"user_id": user_id, "count": len(items), "contribution_count": len(items),
            "statuses": statuses, "items": items}


@router.get("/{user_id}/complaints/{complaint_id}")
def my_complaint_detail(user_id: int, complaint_id: int, db: Session = Depends(get_db)):
    _citizen_user(db, user_id)
    complaint = (db.query(Complaint).filter(Complaint.id == complaint_id,
                                             Complaint.user_id == user_id).first())
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found for this citizen")

    priority = _priority_evidence(complaint, db)
    ai = priority["ai_prediction"]
    citizen_ai = {key: value for key, value in ai.items()
                  if key not in {"feature_values", "reason"}}
    technician = None
    if complaint.assigned_technician_id:
        technician = db.query(User).filter(User.id == complaint.assigned_technician_id).first()

    timeline = []
    if complaint.created_at:
        timeline.append({"event": "Complaint submitted", "status": "OPEN",
                         "created_at": complaint.created_at.isoformat()})
    outcomes = (db.query(Outcome).filter(Outcome.complaint_id == complaint.id)
                .order_by(Outcome.created_at.asc()).all())
    timeline.extend({"event": f"Repair {outcome.result.lower()}", "status": outcome.result,
                     "notes": outcome.notes,
                     "created_at": outcome.created_at.isoformat() if outcome.created_at else None}
                    for outcome in outcomes)
    if complaint.updated_at and complaint.updated_at != complaint.created_at:
        timeline.append({"event": "Complaint status last updated", "status": complaint.status,
                         "created_at": complaint.updated_at.isoformat()})

    return {
        "id": complaint.id, "user_id": complaint.user_id,
        "description": complaint.description, "image_path": complaint.image_path,
        "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
        "location": {"latitude": complaint.latitude, "longitude": complaint.longitude},
        "road": {"name": complaint.road_name, "type": complaint.road_type,
                 "u": complaint.road_u, "v": complaint.road_v, "key": complaint.road_key},
        "damage": complaint_damage_fields(complaint),
        "priority": {"score": priority["priority_score"], "level": priority["priority_level"],
                     "components": priority["components"], "explanations": priority["explanations"],
                     "recommended_action": complaint.recommended_action},
        "ai_prediction": citizen_ai,
        "status": complaint.status,
        "assigned_technician": ({"id": technician.id, "name": technician.name}
                                if technician else None),
        "created_at": complaint.created_at.isoformat() if complaint.created_at else None,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else None,
        "timeline": timeline,
    }

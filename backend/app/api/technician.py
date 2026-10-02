from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database.database import get_db
from backend.app.models.user import User
from backend.app.models.complaint import Complaint
from backend.app.models.repair import Repair
from backend.app.services.damage_presentation import complaint_damage_fields
from backend.app.services.annotated_image_service import existing_annotated_path


router = APIRouter(
    prefix="/technicians",
    tags=["Technicians"],
)
BASE_DIR = Path(__file__).resolve().parents[3]


@router.post("/")
def create_technician(
    name: str,
    email: str,
    phone: str | None = None,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists",
        )

    technician = User(
        name=name,
        email=email,
        phone=phone,
        role="TECHNICIAN",
        is_active=1,
    )

    db.add(technician)
    db.commit()
    db.refresh(technician)

    return {
        "message": "Technician created",
        "technician_id": technician.id,
        "name": technician.name,
        "email": technician.email,
        "phone": technician.phone,
        "role": technician.role,
    }


@router.get("/")
def list_technicians(
    db: Session = Depends(get_db),
):
    technicians = (
        db.query(User)
        .filter(
            User.role == "TECHNICIAN",
            User.is_active == 1,
        )
        .all()
    )

    return {
        "count": len(technicians),
        "technicians": [
            {
                "id": technician.id,
                "name": technician.name,
                "email": technician.email,
                "phone": technician.phone,
            }
            for technician in technicians
        ],
    }


@router.get("/{technician_id}/complaints")
def technician_complaints(
    technician_id: int,
    db: Session = Depends(get_db),
):
    technician = (
        db.query(User)
        .filter(
            User.id == technician_id,
            User.role == "TECHNICIAN",
        )
        .first()
    )

    if technician is None:
        raise HTTPException(
            status_code=404,
            detail="Technician not found",
        )

    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.assigned_technician_id
            == technician_id
        )
        .order_by(
            Complaint.priority_score.desc(),
            Complaint.created_at.desc(),
        )
        .all()
    )
    repairs_by_complaint = {}
    if complaints:
        repairs = (db.query(Repair)
                   .filter(Repair.complaint_id.in_([c.id for c in complaints]))
                   .order_by(Repair.created_at.desc()).all())
        for repair in repairs:
            repairs_by_complaint.setdefault(repair.complaint_id, repair)

    return {
        "technician": {
            "id": technician.id,
            "name": technician.name,
        },
        "count": len(complaints),
        "complaints": [
            {
                "id": complaint.id,
                "road_name": complaint.road_name,
                "priority": complaint.priority,
                "priority_score": complaint.priority_score,
                "status": complaint.status,
                "latitude": complaint.latitude,
                "longitude": complaint.longitude,
                "description": complaint.description,
                # Return each assigned complaint's own persisted evidence path
                # so the field workspace can show the correct image and labels.
                "image_path": complaint.image_path,
                "annotated_image_path": existing_annotated_path(complaint.image_path, BASE_DIR),
                "damage": complaint_damage_fields(complaint),
                "road_type": complaint.road_type,
                "created_at": (complaint.created_at.isoformat()
                               if complaint.created_at else None),
                "repair_record": ({
                    "id": repairs_by_complaint[complaint.id].id,
                    "repair_cost": repairs_by_complaint[complaint.id].repair_cost,
                    "repair_notes": repairs_by_complaint[complaint.id].repair_notes,
                    "completed_at": (repairs_by_complaint[complaint.id].completed_at.isoformat()
                                     if repairs_by_complaint[complaint.id].completed_at else None),
                    "verification_status": repairs_by_complaint[complaint.id].verification_status,
                } if complaint.id in repairs_by_complaint else None),
            }
            for complaint in complaints
        ],
    }


@router.patch("/{technician_id}/complaints/{complaint_id}/status")
def update_complaint_status(
    technician_id: int,
    complaint_id: int,
    status: str,
    db: Session = Depends(get_db),
):
    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.id == complaint_id,
            Complaint.assigned_technician_id
            == technician_id,
        )
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not assigned to this technician",
        )

    allowed_statuses = {
        "IN_PROGRESS",
        "REPAIRED",
    }

    status = status.upper()

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid technician status",
                "allowed": sorted(allowed_statuses),
            },
        )

    complaint.status = status

    db.commit()
    db.refresh(complaint)

    return {
        "message": "Complaint status updated",
        "complaint_id": complaint.id,
        "technician_id": technician_id,
        "status": complaint.status,
    }

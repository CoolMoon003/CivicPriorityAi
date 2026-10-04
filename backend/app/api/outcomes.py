from datetime import datetime
import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database.database import get_db
from backend.app.models.complaint import Complaint
from backend.app.models.repair import Repair
from backend.app.models.outcome import Outcome


router = APIRouter(
    prefix="/outcomes",
    tags=["Outcomes"],
)


@router.post("/repairs/{complaint_id}")
def create_repair(
    complaint_id: int,
    technician_id: int,
    repair_notes: str = "",
    repair_cost: float | None = None,
    db: Session = Depends(get_db),
):
    if repair_cost is not None and (not math.isfinite(repair_cost) or repair_cost < 0):
        raise HTTPException(status_code=422, detail="Repair cost must be a finite, non-negative value")

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

    if complaint.assigned_technician_id != technician_id:
        raise HTTPException(
            status_code=403,
            detail="Complaint is not assigned to this technician",
        )

    if complaint.status != "REPAIRED":
        raise HTTPException(
            status_code=400,
            detail="Complaint must be REPAIRED before creating a repair record",
        )

    existing = (
        db.query(Repair)
        .filter(
            Repair.complaint_id == complaint_id
        )
        .order_by(Repair.id.desc())
        .first()
    )

    # A rejected verification returns the complaint to IN_PROGRESS. Permit
    # the technician to submit a new completion record after that rework.
    if existing and (existing.verification_status or "").upper() != "REJECTED":
        raise HTTPException(
            status_code=400,
            detail="A repair record is already pending or verified",
        )

    repair = Repair(
        complaint_id=complaint_id,
        technician_id=technician_id,
        repair_notes=repair_notes,
        repair_cost=repair_cost,
        completed_at=datetime.utcnow(),
        verification_status="PENDING",
    )

    db.add(repair)
    db.commit()
    db.refresh(repair)

    return {
        "message": "Repair record created",
        "repair_id": repair.id,
        "complaint_id": complaint_id,
        "technician_id": technician_id,
        "repair_cost": repair_cost,
        "verification_status": repair.verification_status,
    }


@router.patch("/repairs/{repair_id}/verify")
def verify_repair(
    repair_id: int,
    approved: bool,
    verification_notes: str = "",
    db: Session = Depends(get_db),
):
    repair = (
        db.query(Repair)
        .filter(Repair.id == repair_id)
        .first()
    )

    if repair is None:
        raise HTTPException(
            status_code=404,
            detail="Repair record not found",
        )

    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.id == repair.complaint_id
        )
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    repair.verification_status = (
        "VERIFIED"
        if approved
        else "REJECTED"
    )

    repair.verification_notes = verification_notes
    repair.verified_at = datetime.utcnow()

    if approved:
        complaint.status = "VERIFIED"
    else:
        complaint.status = "IN_PROGRESS"

    outcome = Outcome(
        complaint_id=complaint.id,
        result=repair.verification_status,
        notes=verification_notes,
    )

    db.add(outcome)
    db.commit()

    return {
        "message": "Repair verification completed",
        "repair_id": repair.id,
        "complaint_id": complaint.id,
        "verification_status": repair.verification_status,
        "complaint_status": complaint.status,
    }


@router.get("/complaints/{complaint_id}")
def get_outcome(
    complaint_id: int,
    db: Session = Depends(get_db),
):
    repairs = (
        db.query(Repair)
        .filter(
            Repair.complaint_id == complaint_id
        )
        .all()
    )

    outcomes = (
        db.query(Outcome)
        .filter(
            Outcome.complaint_id == complaint_id
        )
        .order_by(Outcome.created_at.desc())
        .all()
    )

    return {
        "complaint_id": complaint_id,
        "repairs": [
            {
                "id": repair.id,
                "technician_id": repair.technician_id,
                "repair_notes": repair.repair_notes,
                "repair_cost": repair.repair_cost,
                "completed_at": (
                    repair.completed_at.isoformat()
                    if repair.completed_at
                    else None
                ),
                "verification_status": repair.verification_status,
                "verification_notes": repair.verification_notes,
                "verified_at": (
                    repair.verified_at.isoformat()
                    if repair.verified_at
                    else None
                ),
            }
            for repair in repairs
        ],
        "outcomes": [
            {
                "id": outcome.id,
                "result": outcome.result,
                "notes": outcome.notes,
                "created_at": outcome.created_at.isoformat(),
            }
            for outcome in outcomes
        ],
    }

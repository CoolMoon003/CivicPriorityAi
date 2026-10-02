from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from backend.app.database.database import Base


class Repair(Base):
    __tablename__ = "repairs"

    id = Column(Integer, primary_key=True, index=True)

    complaint_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    technician_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    repair_notes = Column(
        Text,
        nullable=True,
    )

    repair_cost = Column(
        Float,
        nullable=True,
    )

    before_image = Column(
        String,
        nullable=True,
    )

    after_image = Column(
        String,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    verified_at = Column(
        DateTime,
        nullable=True,
    )

    verification_status = Column(
        String,
        nullable=False,
        default="PENDING",
    )

    verification_notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
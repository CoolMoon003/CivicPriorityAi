from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, ForeignKey

from backend.app.database.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)

    # Citizen information
    user_id = Column(Integer, nullable=True)

    # Uploaded evidence
    image_path = Column(String, nullable=True)
    image_sha256 = Column(String(64), nullable=True, index=True)
    duplicate_of_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)

    # Citizen description
    description = Column(Text, nullable=True)

    # GPS
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Road matched from OSM
    road_u = Column(Integer, nullable=True)
    road_v = Column(Integer, nullable=True)
    road_key = Column(Integer, nullable=True)

    road_name = Column(String, nullable=True)
    road_type = Column(String, nullable=True)

    # AI damage analysis
    damage_type = Column(String, nullable=True)
    damage_severity = Column(String, nullable=True)
    damage_confidence = Column(Float, nullable=True)

    # Priority
    priority_score = Column(Float, nullable=True)
    priority = Column(String, nullable=True)
    recommended_action = Column(Text, nullable=True)

    # Workflow
    status = Column(
        String,
        default="OPEN",
        nullable=False,
    )

    assigned_technician_id = Column(Integer, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

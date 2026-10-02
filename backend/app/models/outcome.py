from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.database.database import Base


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, index=True)

    complaint_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    result = Column(
        String,
        nullable=False,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
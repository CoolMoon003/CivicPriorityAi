from __future__ import annotations

from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy.orm import Session

from backend.app.models.complaint import Complaint


class DuplicateService:
    """
    Finds existing complaints that likely refer to the same
    physical road problem.

    Matching is based on:
    - same/nearby OSM road segment
    - geographic distance
    - open/recent complaints
    """

    MAX_DISTANCE_METERS = 50.0
    RECENT_DAYS = 30

    @staticmethod
    def distance_m(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate approximate distance between GPS points."""

        earth_radius = 6_371_000

        phi1 = radians(lat1)
        phi2 = radians(lat2)

        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)

        a = (
            sin(delta_phi / 2) ** 2
            + cos(phi1)
            * cos(phi2)
            * sin(delta_lambda / 2) ** 2
        )

        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return earth_radius * c

    def find_duplicates(
        self,
        db: Session,
        latitude: float,
        longitude: float,
        road_u: int | None = None,
        road_v: int | None = None,
        road_key: int | None = None,
    ) -> list[dict]:

        cutoff = datetime.utcnow() - timedelta(days=self.RECENT_DAYS)
        complaints = (
            db.query(Complaint)
            .filter(Complaint.status.in_(("OPEN", "ASSIGNED", "IN_PROGRESS")))
            .filter(Complaint.created_at >= cutoff)
            .order_by(Complaint.created_at.desc())
            .all()
        )

        duplicates = []

        for complaint in complaints:

            # Prefer exact OSM road-segment matching.
            same_road = (
                road_u is not None
                and road_v is not None
                and road_key is not None
                and complaint.road_u == road_u
                and complaint.road_v == road_v
                and complaint.road_key == road_key
            )

            distance = self.distance_m(
                latitude,
                longitude,
                complaint.latitude,
                complaint.longitude,
            )

            nearby = distance <= self.MAX_DISTANCE_METERS

            if same_road or nearby:
                duplicates.append(
                    {
                        "complaint_id": complaint.id,
                        "distance_m": round(distance, 2),
                        "same_road_segment": same_road,
                        "status": complaint.status,
                        "created_at": complaint.created_at.isoformat(),
                    }
                )

        return duplicates

    def recurrence_count(
        self,
        db: Session,
        latitude: float,
        longitude: float,
        road_u: int | None = None,
        road_v: int | None = None,
        road_key: int | None = None,
    ) -> int:

        return len(
            self.find_duplicates(
                db=db,
                latitude=latitude,
                longitude=longitude,
                road_u=road_u,
                road_v=road_v,
                road_key=road_key,
            )
        )

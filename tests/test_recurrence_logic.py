from datetime import datetime, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.database import Base
from backend.app.models.complaint import Complaint
from backend.app.services.duplicate_service import DuplicateService
from backend.app.services.priority_features import recurrence_for


class RecurrenceLogicTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.now = datetime.utcnow()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def add(self, *, complaint_id, created_at, status="OPEN", lat=12.0, lon=79.0, road=(1, 2, 0)):
        complaint = Complaint(
            id=complaint_id, created_at=created_at, updated_at=created_at,
            status=status, latitude=lat, longitude=lon,
            road_u=road[0], road_v=road[1], road_key=road[2],
        )
        self.session.add(complaint)
        self.session.commit()
        return complaint

    def test_no_history_returns_zero(self):
        current = self.add(complaint_id=1, created_at=self.now)
        self.assertEqual(recurrence_for(current, self.session)[0], 0)

    def test_one_and_multiple_recent_matching_reports_count(self):
        self.add(complaint_id=1, created_at=self.now - timedelta(days=2))
        self.add(complaint_id=2, created_at=self.now - timedelta(days=1))
        current = self.add(complaint_id=3, created_at=self.now)
        self.assertEqual(recurrence_for(current, self.session)[0], 2)

    def test_old_unrelated_and_terminal_reports_are_excluded(self):
        self.add(complaint_id=1, created_at=self.now - timedelta(days=31))
        self.add(complaint_id=2, created_at=self.now - timedelta(days=2), road=(8, 9, 0), lat=12.1, lon=79.1)
        self.add(complaint_id=3, created_at=self.now - timedelta(days=2), status="REPAIRED")
        self.add(complaint_id=4, created_at=self.now - timedelta(days=2), status="VERIFIED")
        self.add(complaint_id=5, created_at=self.now - timedelta(days=2), status="REJECTED")
        current = self.add(complaint_id=6, created_at=self.now)
        self.assertEqual(recurrence_for(current, self.session), (0, 0))

    def test_duplicate_service_excludes_old_and_closed_reports(self):
        self.add(complaint_id=1, created_at=self.now - timedelta(days=2))
        self.add(complaint_id=2, created_at=self.now - timedelta(days=31))
        self.add(complaint_id=3, created_at=self.now - timedelta(days=2), status="RESOLVED")
        matches = DuplicateService().find_duplicates(self.session, 12.0, 79.0, 1, 2, 0)
        self.assertEqual([item["complaint_id"] for item in matches], [1])

    def test_deleted_complaint_is_not_counted(self):
        historical = self.add(complaint_id=1, created_at=self.now - timedelta(days=2))
        current = self.add(complaint_id=2, created_at=self.now)
        self.session.delete(historical)
        self.session.commit()
        self.assertEqual(recurrence_for(current, self.session), (0, 0))

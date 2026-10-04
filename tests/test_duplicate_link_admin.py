from __future__ import annotations

import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api import admin as admin_api
from backend.app.database.database import Base, get_db
from backend.app.models.complaint import Complaint
from backend.app.models.outcome import Outcome
from backend.app.models.repair import Repair


class DuplicateLinkAdminTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)()
        self.app = FastAPI()
        self.app.include_router(admin_api.router)
        self.app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(self.app)
        self.original = Complaint(latitude=12, longitude=79, status="OPEN")
        self.duplicate = Complaint(latitude=12, longitude=79, status="OPEN")
        self.session.add_all([self.original, self.duplicate])
        self.session.commit()
        self.repair = Repair(complaint_id=self.duplicate.id, technician_id=1)
        self.outcome = Outcome(complaint_id=self.duplicate.id, result="SYNTHETIC DEMO")
        self.session.add_all([self.repair, self.outcome])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
    def test_link_preserves_records_and_prevents_deleting_link_target(self):
        linked = self.client.patch(f"/admin/complaints/{self.duplicate.id}/duplicate-of/{self.original.id}")
        self.assertEqual(linked.status_code, 200, linked.text)
        self.assertEqual(self.duplicate.duplicate_of_id, self.original.id)
        self.assertEqual(self.session.query(Repair).filter_by(id=self.repair.id).count(), 1)
        self.assertEqual(self.session.query(Outcome).filter_by(id=self.outcome.id).count(), 1)

        deletion = self.client.delete(f"/admin/complaints/{self.original.id}")
        self.assertEqual(deletion.status_code, 409, deletion.text)
        self.assertIsNotNone(self.session.query(Complaint).filter_by(id=self.original.id).first())
        self.assertEqual(self.duplicate.duplicate_of_id, self.original.id)

    def test_duplicate_link_api_rejects_cycles(self):
        self.duplicate.duplicate_of_id = self.original.id
        self.session.commit()
        response = self.client.patch(f"/admin/complaints/{self.original.id}/duplicate-of/{self.duplicate.id}")
        self.assertEqual(response.status_code, 400, response.text)


if __name__ == "__main__":
    unittest.main()

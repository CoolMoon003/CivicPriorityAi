from __future__ import annotations

import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.database import Base, get_db
from backend.app.models.complaint import Complaint
from backend.app.models.outcome import Outcome
from backend.app.models.repair import Repair
from backend.app.api import complaints as api


class DuplicatePreventionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self.temp = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp.name)
        self.old_upload_dir = api.UPLOAD_DIR
        api.UPLOAD_DIR = self.upload_dir
        self.app = FastAPI()
        self.app.include_router(api.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)
        self.image_bytes = self.make_image()

    def tearDown(self):
        api.UPLOAD_DIR = self.old_upload_dir
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        self.temp.cleanup()

    @staticmethod
    def make_image():
        import io
        stream = io.BytesIO()
        Image.new("RGB", (16, 16), (18, 50, 90)).save(stream, format="PNG")
        return stream.getvalue()

    def add_complaint(self, *, image_bytes=None, lat=12.0, lon=79.0, status="OPEN", image_hash=True):
        path = None
        digest = None
        if image_bytes is not None:
            name = f"prior-{self.db.query(Complaint).count()}.png"
            target = self.upload_dir / name
            target.write_bytes(image_bytes)
            path = str(target)
            digest = hashlib.sha256(image_bytes).hexdigest() if image_hash else None
        complaint = Complaint(image_path=path, image_sha256=digest, latitude=lat, longitude=lon, status=status)
        self.db.add(complaint)
        self.db.commit()
        return complaint

    def post(self, *, image=None, filename="a.png", lat=12.0, lon=79.0, confirm=False):
        data = {"latitude": str(lat), "longitude": str(lon), "continue_as_separate": str(confirm).lower()}
        files = {"image": (filename, image, "image/png")} if image is not None else None
        return self.client.post("/complaints/", data=data, files=files)

    def test_exact_image_duplicate_rejected_before_storage_even_with_different_filename(self):
        prior = self.add_complaint(image_bytes=self.image_bytes)
        prior.status = "IN_PROGRESS"
        repair = Repair(complaint_id=prior.id, technician_id=7, repair_notes="Preserve me")
        outcome = Outcome(complaint_id=prior.id, result="IN_PROGRESS", notes="Keep evidence")
        self.db.add_all([repair, outcome])
        self.db.commit()
        original_path = Path(prior.image_path)
        original_bytes = original_path.read_bytes()
        before = set(self.upload_dir.iterdir())
        response = self.post(image=self.image_bytes, filename="renamed.png", lat=13)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["existing_complaint_id"], prior.id)
        self.assertEqual(set(self.upload_dir.iterdir()), before)
        self.assertEqual(self.db.query(Complaint).count(), 1)
        self.assertEqual(prior.status, "IN_PROGRESS")
        self.assertEqual(original_path.read_bytes(), original_bytes)
        self.assertEqual(self.db.query(Repair).filter_by(complaint_id=prior.id).count(), 1)
        self.assertEqual(self.db.query(Outcome).filter_by(complaint_id=prior.id).count(), 1)

    def test_location_warning_requires_confirmation_and_closed_reports_are_ignored(self):
        self.add_complaint(lat=12.0, lon=79.0)
        warning = self.post(image=self.make_image(), lat=12.000001, lon=79.0)
        self.assertTrue(warning.json()["requires_confirmation"])
        # A resolved complaint does not raise a location warning.
        self.db.query(Complaint).update({Complaint.status: "RESOLVED"})
        self.db.commit()
        response = self.post(image=None, lat=12.0, lon=79.0)
        self.assertNotIn("requires_confirmation", response.json())

    def test_nearby_distinct_report_can_be_confirmed_and_created(self):
        prior = self.add_complaint(lat=12.0, lon=79.0)
        priority = SimpleNamespace(score=1, priority="LOW", recommended_action="Inspect", factors={}, components={
            "damage": 0, "confidence": 0, "road_importance": 0, "facilities": 0,
            "recurrence": 0, "population": 0, "district_safety": 0,
        }, explanations=[])
        with patch.object(api.road_matcher, "match", return_value={"u": None, "v": None, "key": None, "road_name": None, "highway": None}), \
             patch.object(api.priority_engine, "calculate", return_value=priority), \
             patch.object(api, "predict_new_complaint", return_value={}):
            warning = self.post(lat=12.000001, lon=79.0)
            self.assertTrue(warning.json()["requires_confirmation"])
            created = self.post(lat=12.000001, lon=79.0, confirm=True)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertIn("complaint_id", created.json())
        self.assertEqual(self.db.query(Complaint).count(), 2)
        self.assertEqual(self.db.query(Complaint).filter_by(id=prior.id).one().status, "OPEN")

    def test_legacy_record_without_hash_is_compared_from_image_file(self):
        prior = self.add_complaint(image_bytes=self.image_bytes, image_hash=False)
        response = self.post(image=self.image_bytes, lat=13)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["existing_complaint_id"], prior.id)
        self.assertEqual(prior.image_sha256, hashlib.sha256(self.image_bytes).hexdigest())


if __name__ == "__main__":
    unittest.main()

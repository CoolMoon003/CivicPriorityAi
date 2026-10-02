from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai.road_damage_detector import DamageDetection, Detection
from backend.app.database.database import Base, get_db
from backend.app.models.complaint import Complaint
from backend.app.models.outcome import Outcome
from backend.app.models.repair import Repair
from backend.app.services.annotated_image_service import render_annotated_image
from backend.app.services.complaint_deletion import (
    safe_complaint_uploads_to_remove,
    valid_admin_delete_token,
)
from backend.app.services.demo_dataset_images import TYPE_BY_ID, image_candidates


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnnotationServiceTests(unittest.TestCase):
    def _possible_pothole(self) -> DamageDetection:
        box = Detection(
            class_id=3,
            class_name="Pothole (D40)",
            damage_type="pothole",
            confidence=0.2022,
            x1=30, y1=25, x2=100, y2=95,
            detection_state="possible",
            severity="high",
        )
        return DamageDetection(
            damage_type="pothole", severity="high", confidence=box.confidence,
            description="Possible pothole; uncertain.", detection_state="possible",
            detections=[box], primary_detection=box,
        )

    def test_actual_detection_box_creates_sidecar_without_mutating_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "upload.jpg"
            Image.new("RGB", (140, 120), (120, 120, 120)).save(original)
            before = file_digest(original)
            result = render_annotated_image(original, self._possible_pothole())
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
            self.assertEqual(before, file_digest(original))
            with Image.open(result) as rendered:
                self.assertEqual(rendered.size, (140, 120))

    def test_no_reliable_detection_does_not_generate_boxes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "upload.jpg"
            Image.new("RGB", (100, 80), (10, 20, 30)).save(original)
            detection = DamageDetection("unknown", "unknown", 0.0, "No reliable detection")
            self.assertIsNone(render_annotated_image(original, detection))
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["upload.jpg"])

    def test_sub_possible_candidate_is_not_drawn(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "upload.jpg"
            Image.new("RGB", (100, 80), (10, 20, 30)).save(original)
            weak = Detection(3, "Pothole (D40)", "pothole", .05, 10, 10, 50, 50,
                             "no_reliable_detection", "high")
            detection = DamageDetection("unknown", "unknown", 0.0, "No reliable detection", detections=[weak])
            self.assertIsNone(render_annotated_image(original, detection))
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["upload.jpg"])

    def test_all_four_ground_truth_classes_are_read_without_modifying_labels(self):
        self.assertEqual(TYPE_BY_ID, {
            0: "longitudinal_crack", 1: "transverse_crack",
            2: "alligator_crack", 3: "pothole",
        })
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, labels = root / "images", root / "labels"
            images.mkdir(); labels.mkdir()
            label_bytes = b"0 0.5 0.5 0.4 0.3\n1 0.5 0.5 0.5 0.4\n2 0.5 0.5 0.6 0.5\n3 0.5 0.5 0.7 0.6\n"
            label = labels / "sample.txt"
            label.write_bytes(label_bytes)
            Image.new("RGB", (32, 32)).save(images / "sample.jpg")
            with patch("backend.app.services.demo_dataset_images.IMAGE_DIR", images), patch(
                "backend.app.services.demo_dataset_images.LABEL_DIR", labels
            ):
                candidates = image_candidates(max_candidates_per_class=1)
            self.assertEqual(set(candidates), set(TYPE_BY_ID))
            self.assertTrue(all(candidates[class_id] for class_id in TYPE_BY_ID))
            self.assertEqual(label.read_bytes(), label_bytes)


class ComplaintDeletionTests(unittest.TestCase):
    def test_delete_capability_and_file_scope_are_conservative(self):
        self.assertTrue(valid_admin_delete_token("0123456789abcdef0123456789abcdef", "0123456789abcdef0123456789abcdef"))
        self.assertFalse(valid_admin_delete_token("0123456789abcdef0123456789abcdef", None))
        self.assertFalse(valid_admin_delete_token("0123456789abcdef0123456789abcdef", "wrong"))
        root = Path(tempfile.gettempdir()) / "civic-priority-deletion-test"
        user_upload = "data/uploads/0123456789abcdef0123456789abcdef.jpg"
        paths = safe_complaint_uploads_to_remove(user_upload, root)
        self.assertEqual(len(paths), 2)
        self.assertEqual(safe_complaint_uploads_to_remove(user_upload, root, shared_reference=True), [])
        self.assertEqual(safe_complaint_uploads_to_remove("data/uploads/demo_unified/file.jpg", root), [])
        self.assertEqual(safe_complaint_uploads_to_remove("data/processed/road_damage_unified/images/val/a.jpg", root), [])

    def test_admin_endpoint_requires_token_then_deletes_only_unshared_owned_upload(self):
        import backend.app.api.admin as admin_api

        previous_token = os.environ.get("CIVIC_ADMIN_DELETE_TOKEN")
        os.environ["CIVIC_ADMIN_DELETE_TOKEN"] = "0123456789abcdef0123456789abcdef"
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = TestSession()
        image_name = f"{uuid4().hex}.jpg"
        upload_dir = admin_api.BASE_DIR / "data" / "uploads"
        annotation_dir = upload_dir / "annotated"
        upload_dir.mkdir(parents=True, exist_ok=True)
        annotation_dir.mkdir(parents=True, exist_ok=True)
        original = upload_dir / image_name
        annotation = annotation_dir / f"{Path(image_name).stem}.annotated.jpg"
        Image.new("RGB", (30, 20)).save(original)
        Image.new("RGB", (30, 20)).save(annotation)
        complaint = Complaint(id=987654321, image_path=f"data/uploads/{image_name}", latitude=1, longitude=2)
        session.add(complaint)
        session.add(Repair(complaint_id=complaint.id, technician_id=1))
        session.add(Outcome(complaint_id=complaint.id, result="REJECTED"))
        session.commit()

        app = FastAPI()
        app.include_router(admin_api.router)

        def override_db():
            yield session

        app.dependency_overrides[get_db] = override_db
        try:
            with TestClient(app) as client:
                denied = client.delete(f"/admin/complaints/{complaint.id}")
                self.assertEqual(denied.status_code, 403)
                self.assertIsNotNone(session.query(Complaint).filter_by(id=complaint.id).first())
                deleted = client.delete(
                    f"/admin/complaints/{complaint.id}",
                    headers={"X-Civic-Admin-Token": "0123456789abcdef0123456789abcdef"},
                )
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertIsNone(session.query(Complaint).filter_by(id=complaint.id).first())
                self.assertEqual(session.query(Repair).filter_by(complaint_id=complaint.id).count(), 0)
                self.assertEqual(session.query(Outcome).filter_by(complaint_id=complaint.id).count(), 0)
                self.assertFalse(original.exists())
                self.assertFalse(annotation.exists())
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
            original.unlink(missing_ok=True)
            annotation.unlink(missing_ok=True)
            if previous_token is None:
                os.environ.pop("CIVIC_ADMIN_DELETE_TOKEN", None)
            else:
                os.environ["CIVIC_ADMIN_DELETE_TOKEN"] = previous_token


if __name__ == "__main__":
    unittest.main()

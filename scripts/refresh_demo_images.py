"""Replace only marked synthetic demo photos with verified Unified samples.

This keeps complaint IDs and repair/outcome relationships. It never mutates
Unified source images or labels and leaves old, unreferenced demo photos alone.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.road_damage_detector import RoadDamageDetector
from backend.app.database.database import SessionLocal
from backend.app.models.complaint import Complaint
from backend.app.scoring.priority_engine import PriorityEngine
from backend.app.services.annotated_image_service import render_annotated_image, project_relative_path
from backend.app.services.demo_dataset_images import TYPE_BY_ID, select_demo_images
from backend.app.services.duplicate_service import DuplicateService
from backend.app.services.priority_features import road_features_for


DEMO_PREFIX = "[SYNTHETIC DEMO v1]"
UPLOAD_DIR = ROOT / "data" / "uploads"
DEMO_DIR = UPLOAD_DIR / "demo_unified"
DATABASE_FILE = ROOT / "data" / "civic_priority.db"


def run(apply_changes: bool, candidate_limit: int) -> None:
    if not DATABASE_FILE.is_file():
        raise FileNotFoundError(f"Database file not found: {DATABASE_FILE}")
    with SessionLocal() as db:
        demos = (db.query(Complaint)
                 .filter(Complaint.description.like(f"{DEMO_PREFIX}%"))
                 .order_by(Complaint.id.asc()).all())
        if not demos:
            print("No explicitly marked synthetic demo complaints found; no changes made.")
            return

        existing_hashes: set[str] = set()
        demo_ids = {complaint.id for complaint in demos}
        for complaint in db.query(Complaint).all():
            if complaint.id not in demo_ids and complaint.image_path:
                path = Path(complaint.image_path)
                if not path.is_absolute():
                    path = ROOT / path
                if path.is_file():
                    import hashlib
                    existing_hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())

        detector = RoadDamageDetector()
        selected = select_demo_images(
            detector, len(demos), existing_hashes=existing_hashes,
            max_candidates_per_class=candidate_limit,
        )
        print(f"Marked synthetic demo complaints: {len(demos)}")
        print("Planned dataset classes:", dict(Counter(TYPE_BY_ID[item.ground_truth_class_id] for item in selected)))
        for complaint, item in zip(demos, selected):
            print(
                f"#{complaint.id}: {item.source.name} | GT={TYPE_BY_ID[item.ground_truth_class_id]} "
                f"| YOLO={item.prediction.damage_type} {item.prediction.confidence:.3%} "
                f"({item.prediction.detection_state})"
            )
        if not apply_changes:
            print("Dry run only; no image or database files were changed. Rerun with --apply to replace demo assets.")
            return

        backup = DATABASE_FILE.with_name(
            f"{DATABASE_FILE.stem}.pre_unified_demo_refresh_{datetime.now():%Y%m%d_%H%M%S}{DATABASE_FILE.suffix}"
        )
        with sqlite3.connect(DATABASE_FILE) as source_db, sqlite3.connect(backup) as backup_db:
            source_db.backup(backup_db)
        print(f"Database backup: {backup}")

        created_assets: list[Path] = []
        try:
            DEMO_DIR.mkdir(parents=True, exist_ok=True)
            for complaint, item in zip(demos, selected):
                destination = DEMO_DIR / f"{item.sha256[:12]}_{item.source.name}"
                if destination.exists():
                    import hashlib
                    if hashlib.sha256(destination.read_bytes()).hexdigest() != item.sha256:
                        raise RuntimeError(f"Refusing to overwrite non-matching demo asset: {destination}")
                else:
                    shutil.copy2(item.source, destination)
                    created_assets.append(destination)
                output_root = DEMO_DIR / "annotated"
                annotated = render_annotated_image(destination, item.as_damage_detection(), output_root)
                if annotated is None:
                    raise RuntimeError(f"Expected real YOLO annotation was not generated for {destination}")
                if annotated not in created_assets:
                    created_assets.append(annotated)

                result = item.as_damage_detection()
                complaint.image_path = project_relative_path(destination, ROOT)
                complaint.damage_type = result.damage_type
                complaint.damage_severity = result.severity
                complaint.damage_confidence = result.confidence
                complaint.description = (
                    f"{DEMO_PREFIX} Unified validation sample with ground-truth {result.damage_type}; "
                    f"YOLO26 produced a {result.detection_state} {item.prediction.class_name} detection. "
                    "Synthetic workflow example only; the image is not geolocated to this Vellore road segment."
                )

            db.flush()
            priority_engine = PriorityEngine()
            duplicate_service = DuplicateService()
            for complaint in demos:
                duplicates = duplicate_service.find_duplicates(
                    db, complaint.latitude, complaint.longitude,
                    complaint.road_u, complaint.road_v, complaint.road_key,
                )
                duplicates = [row for row in duplicates if row.get("complaint_id") != complaint.id]
                road = road_features_for(complaint)
                priority = priority_engine.calculate(
                    complaint.damage_type, complaint.damage_severity,
                    complaint.damage_confidence, road, repeat_reports=len(duplicates),
                )
                complaint.priority_score = priority.score
                complaint.priority = priority.priority
                complaint.recommended_action = priority.recommended_action
            db.commit()
        except Exception:
            db.rollback()
            for asset in created_assets:
                try:
                    asset.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        print("Updated marked synthetic demo records; complaint IDs, statuses, assignments, repairs, and outcomes were preserved.")
        print(f"Original copies and generated annotations: {DEMO_DIR}")
        print("Existing image files and Unified dataset files were not deleted or modified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the verified replacements; default is read-only")
    parser.add_argument("--candidate-limit", type=int, default=128,
                        help="Maximum visibility-ranked candidates per class to test")
    arguments = parser.parse_args()
    run(arguments.apply, arguments.candidate_limit)

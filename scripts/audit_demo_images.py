"""Read-only audit for marked synthetic demo evidence; writes a CSV report."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.detection_policy import DetectionPolicy
from backend.app.database.database import SessionLocal
from backend.app.models.complaint import Complaint
from backend.app.services.annotated_image_service import existing_annotated_path
from backend.app.services.demo_dataset_images import TYPE_BY_ID


DEMO_PREFIX = "[SYNTHETIC DEMO v1]"
LABEL_DIR = ROOT / "data" / "processed" / "road_damage_unified" / "labels" / "val"
OUTPUT = ROOT / "docs" / "demo_image_audit.csv"
SEVERITY = {
    "pothole": "high",
    "alligator_crack": "high",
    "longitudinal_crack": "medium",
    "transverse_crack": "medium",
}


def ground_truth_ids(filename: str) -> set[int]:
    source_name = filename.split("_", 1)[1]
    label = LABEL_DIR / f"{Path(source_name).stem}.txt"
    ids = set()
    for line in label.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields:
            ids.add(int(fields[0]))
    return ids


def run() -> None:
    policy = DetectionPolicy.from_environment()
    rows = []
    with SessionLocal() as db:
        demos = (db.query(Complaint)
                 .filter(Complaint.description.like(f"{DEMO_PREFIX}%"))
                 .order_by(Complaint.id.asc()).all())
        all_count = db.query(Complaint).count()
        for complaint in demos:
            image = Path(complaint.image_path)
            if not image.is_absolute():
                image = ROOT / image
            gt_ids = ground_truth_ids(image.name) if image.is_file() and image.parent.name == "demo_unified" else set()
            gt_type = ";".join(TYPE_BY_ID[value] for value in sorted(gt_ids))
            damage_type = (complaint.damage_type or "unknown").lower()
            confidence = float(complaint.damage_confidence or 0.0)
            state = policy.state_for(confidence) if damage_type != "unknown" else "no_reliable_detection"
            annotation = existing_annotated_path(complaint.image_path, ROOT)
            rows.append({
                "complaint_id": complaint.id,
                "image_filename": image.name,
                "ground_truth_classes": gt_type,
                "ground_truth_matches_stored_detection": str(
                    damage_type != "unknown" and any(TYPE_BY_ID.get(class_id) == damage_type for class_id in gt_ids)
                ).lower(),
                "yolo_primary_class_stored": damage_type,
                "yolo_confidence": f"{confidence:.6f}",
                "detection_state": state,
                "damage_severity": complaint.damage_severity or "unknown",
                "severity_matches_class_policy": str(
                    (complaint.damage_severity or "unknown").lower() == SEVERITY.get(damage_type, "unknown")
                ).lower(),
                "overall_priority_score": complaint.priority_score,
                "overall_priority_level": complaint.priority,
                "annotated_image_path": annotation or "",
                "annotated_image_exists": str(bool(annotation)).lower(),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["complaint_id"])
        writer.writeheader()
        writer.writerows(rows)
    from collections import Counter
    classes = Counter(row["yolo_primary_class_stored"] for row in rows)
    mismatches = [row["complaint_id"] for row in rows
                  if row["ground_truth_matches_stored_detection"] != "true"
                  or row["severity_matches_class_policy"] != "true"
                  or row["annotated_image_exists"] != "true"]
    print(f"total_complaints={all_count}; marked_demos={len(rows)}; unmarked_preserved={all_count-len(rows)}")
    print(f"class_distribution={dict(classes)}; issues={mismatches}")
    print(f"audit_csv={OUTPUT}")


if __name__ == "__main__":
    run()

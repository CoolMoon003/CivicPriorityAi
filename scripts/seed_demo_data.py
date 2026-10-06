"""Seed explicitly synthetic Vellore demo records without replacing live data.

Dry-run is the default. Use --apply to append enough marked records to bring
the complaint table to 50 total rows. Existing records are never edited or
deleted. All damage values come from the configured RoadDamageDetector.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import random
import shutil
import sys

from shapely.geometry import LineString
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.road_damage_detector import DamageDetection, RoadDamageDetector
from backend.app.database.database import SessionLocal
from backend.app.models.complaint import Complaint
from backend.app.models.outcome import Outcome
from backend.app.models.repair import Repair
from backend.app.models.user import User
from backend.app.scoring.priority_engine import PriorityEngine
from backend.app.services.duplicate_service import DuplicateService
from backend.app.services.priority_features import road_features_for
from backend.app.services.road_matcher import RoadMatcher
from backend.app.services.annotated_image_service import render_annotated_image
from backend.app.services.demo_dataset_images import select_demo_images

TARGET_TOTAL_COMPLAINTS = 50
SEED = 20260928
DEMO_PREFIX = "[SYNTHETIC DEMO v1]"
UPLOAD_DIR = ROOT / "data" / "uploads"
IMAGE_DIR = ROOT / "data" / "processed" / "road_damage_unified" / "images" / "val"
LABEL_DIR = ROOT / "data" / "processed" / "road_damage_unified" / "labels" / "val"
DATABASE_FILE = ROOT / "data" / "civic_priority.db"
BACKUP_FILE = ROOT / "data" / "civic_priority.pre_demo_seed.sqlite3"
GRAPH_FILE = ROOT / "data" / "vellore" / "vellore_drive_network.graphml"
ROAD_FEATURES_FILE = ROOT / "data" / "processed" / "vellore_road_features.geojson"

TECHNICIANS = (
    ("Muthuvel Kumar (Demo)", "ravi.kumar@technician.demo.invalid"),
    ("Suresh Babu (Demo)", "suresh.babu@technician.demo.invalid"),
    ("Arun Prakash (Demo)", "arun.prakash@technician.demo.invalid"),
    ("Vignesh Kumar (Demo)", "vignesh.kumar@technician.demo.invalid"),
    ("Karthik Raj (Demo)", "karthik.raj@technician.demo.invalid"),
    ("Manoj Kumar (Demo)", "manoj.kumar@technician.demo.invalid"),
)
CITIZENS = (
    "Arjun Kumar", "Priya S", "Karthik Raj", "Divya R", "Suresh Kumar",
    "Anjali M", "Vignesh P", "Harini K", "Rahul S", "Meena K",
)
STATUSES = ("OPEN",) * 14 + ("ASSIGNED",) * 10 + ("IN_PROGRESS",) * 10 + ("REPAIRED",) * 6 + ("VERIFIED",) * 4
DETECTION_CLASSES = ("pothole", "longitudinal_crack", "transverse_crack", "alligator_crack")
CLASS_ID_BY_DAMAGE = {
    "longitudinal_crack": 0,
    "transverse_crack": 1,
    "alligator_crack": 2,
    "pothole": 3,
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def annotated_class_ids(image_path: Path) -> set[int]:
    """Read the matching Unified validation annotation; never infer from filenames."""
    label_path = LABEL_DIR / image_path.relative_to(IMAGE_DIR).with_suffix(".txt")
    if not label_path.is_file():
        raise FileNotFoundError(f"Unified annotation not found for {image_path.name}: {label_path}")
    class_ids = set()
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        class_id = int(parts[0])
        if class_id not in CLASS_ID_BY_DAMAGE.values():
            raise ValueError(f"Unexpected Unified class ID {class_id} in {label_path}:{line_number}")
        class_ids.add(class_id)
    return class_ids


def choose_images(detector: RoadDamageDetector, count: int, existing_hashes: set[str]):
    selected = select_demo_images(detector, count, existing_hashes=existing_hashes)
    return [(item.source, item.sha256, item.as_damage_detection()) for item in selected]


def road_point_pairs(matcher: RoadMatcher, pair_count: int, existing_points: list[tuple[float, float]]):
    """Choose real OSM edges and validate each pair through the existing matcher."""
    graph = matcher.graph
    edges = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        highway = data.get("highway")
        highway = highway[0] if isinstance(highway, list) and highway else highway
        if str(highway).lower() not in PriorityEngine.ROAD_IMPORTANCE:
            continue
        name = data.get("name")
        if isinstance(name, list):
            name = name[0] if name else None
        if not name:
            continue
        geometry = data.get("geometry")
        if geometry is None:
            geometry = LineString([(graph.nodes[u]["x"], graph.nodes[u]["y"]),
                                   (graph.nodes[v]["x"], graph.nodes[v]["y"])])
        if not hasattr(geometry, "interpolate") or geometry.length == 0:
            continue
        edges.append((str(highway).lower(), str(name), geometry))

    rng = random.Random(SEED)
    by_type = defaultdict(list)
    for edge in edges:
        by_type[edge[0]].append(edge)
    for road_type in by_type:
        rng.shuffle(by_type[road_type])

    road_types = sorted(by_type)
    candidates = []
    while road_types:
        for road_type in list(road_types):
            if by_type[road_type]:
                candidates.append(by_type[road_type].pop())
            else:
                road_types.remove(road_type)
    rng.shuffle(candidates)

    chosen, chosen_centers = [], []
    for _minimum_existing_distance in (100.0, 50.0, 0.0):
        for road_type, name, geometry in candidates:
            if len(chosen) >= pair_count:
                break
            center = geometry.interpolate(0.5, normalized=True)
            lat, lon = center.y, center.x
            if any(DuplicateService.distance_m(lat, lon, old_lat, old_lon) < _minimum_existing_distance
                   for old_lat, old_lon in existing_points):
                continue
            if any(DuplicateService.distance_m(lat, lon, old_lat, old_lon) < 120
                   for old_lat, old_lon in chosen_centers):
                continue
            points = [geometry.interpolate(fraction, normalized=True) for fraction in (0.49, 0.51)]
            matched = [matcher.match(point.y, point.x) for point in points]
            road_ids = {(item["u"], item["v"], item["key"]) for item in matched}
            if len(road_ids) != 1:
                continue
            if any(item.get("road_name") is None for item in matched):
                continue
            chosen.append([(float(point.y), float(point.x), item) for point, item in zip(points, matched)])
            chosen_centers.append((lat, lon))
        if len(chosen) >= pair_count:
            break
    if len(chosen) < pair_count:
        raise RuntimeError(f"Matched only {len(chosen)} distinct, named OSM road segments; need {pair_count}.")
    return chosen


def ensure_demo_users(db: Session):
    technicians = []
    for name, email in TECHNICIANS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(name=name, email=email, role="TECHNICIAN", is_active=1)
            db.add(user)
            db.flush()
        technicians.append(user)
    citizens = []
    for index, name in enumerate(CITIZENS, 1):
        email = f"citizen{index:02d}@citizen.demo.invalid"
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(name=f"{name} (Demo)", email=email, role="CITIZEN", is_active=1)
            db.add(user)
            db.flush()
        citizens.append(user)
    return technicians, citizens


def run(apply: bool) -> None:
    if not IMAGE_DIR.is_dir() or not LABEL_DIR.is_dir() or not GRAPH_FILE.is_file() or not ROAD_FEATURES_FILE.is_file():
        raise FileNotFoundError("Required local Unified road-damage or Vellore road data is missing.")
    db = SessionLocal()
    try:
        existing_count = db.query(Complaint).count()
        existing_rows = db.query(Complaint).all()
        existing_hashes = set()
        for complaint in existing_rows:
            if not complaint.image_path:
                continue
            path = Path(complaint.image_path)
            if not path.is_absolute():
                path = ROOT / path
            if path.is_file():
                existing_hashes.add(file_hash(path))
        number_to_create = max(0, TARGET_TOTAL_COMPLAINTS - existing_count)
        if number_to_create == 0:
            print(f"No seed required: {existing_count} complaints already meet the {TARGET_TOTAL_COMPLAINTS}-record target.")
            return

        detector = RoadDamageDetector()
        if detector.model is None:
            raise RuntimeError(f"YOLO model unavailable: {detector.model_error}")
        chosen_images = choose_images(detector, number_to_create, existing_hashes)
        image_class_counts = Counter(item[2].damage_type for item in chosen_images)
        print("Actual YOLO results for selected images:", dict(image_class_counts))
        print(f"Planned synthetic complaint additions: {number_to_create}; no existing rows changed.")
        matcher = RoadMatcher(GRAPH_FILE, ROAD_FEATURES_FILE)
        existing_points = [(c.latitude, c.longitude) for c in existing_rows]
        road_pairs = road_point_pairs(matcher, (number_to_create + 1) // 2, existing_points)
        print(f"Validated real OSM road groups: {len(road_pairs)}; every paired point matched to one existing segment.")
        if not apply:
            print("DRY RUN only. Review the result, then rerun with --apply to append the data.")
            return

        if not DATABASE_FILE.is_file():
            raise FileNotFoundError(f"Database file not found: {DATABASE_FILE}")
        if not BACKUP_FILE.exists():
            shutil.copy2(DATABASE_FILE, BACKUP_FILE)
            print(f"Database backup saved: {BACKUP_FILE}")

        technicians, citizens = ensure_demo_users(db)
        db.flush()
        duplicate_service = DuplicateService()
        priority_engine = PriorityEngine()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        created: list[Complaint] = []
        repairs_created = outcomes_created = images_copied = 0

        for index, (source, digest, detection) in enumerate(chosen_images):
            pair = road_pairs[index // 2]
            latitude, longitude, road = pair[index % 2]
            duplicates = duplicate_service.find_duplicates(
                db, latitude, longitude, road.get("u"), road.get("v"), road.get("key")
            )
            recurrence = len(duplicates)
            priority = priority_engine.calculate(
                detection.damage_type, detection.severity, detection.confidence,
                road, repeat_reports=recurrence,
            )
            road_type = road.get("highway")
            if isinstance(road_type, list):
                road_type = road_type[0] if road_type else None
            status = STATUSES[index]
            technician = None if status == "OPEN" else technicians[(index // 2) % len(technicians)]
            citizen = citizens[index % len(citizens)]
            age_days = 3 + ((index * 13) % 110)
            created_at = now - timedelta(days=age_days)
            image_name = f"demo-unified-v2-{source.name}"
            image_path = UPLOAD_DIR / "demo_unified" / image_name
            image_path.parent.mkdir(parents=True, exist_ok=True)
            if image_path.exists():
                if file_hash(image_path) != digest:
                    raise RuntimeError(f"Refusing to overwrite non-matching demo image: {image_path}")
            else:
                shutil.copy2(source, image_path)
                images_copied += 1
            if render_annotated_image(image_path, detection) is None:
                raise RuntimeError(f"YOLO detections could not be annotated for demo image {image_path}")

            complaint = Complaint(
                user_id=citizen.id,
                image_path=str(image_path.relative_to(ROOT)),
                description=(
                    f"{DEMO_PREFIX} Workflow demonstration only. Image is a Unified validation sample; "
                    "the displayed class has matching ground-truth annotation and YOLO evidence. "
                    "It is not geolocated to this synthetic Vellore road point; no real civic report is represented."
                ),
                latitude=latitude, longitude=longitude,
                road_u=road.get("u"), road_v=road.get("v"), road_key=road.get("key"),
                road_name=(road.get("road_name")[0] if isinstance(road.get("road_name"), list)
                           else road.get("road_name")),
                road_type=road_type,
                damage_type=detection.damage_type,
                damage_severity=detection.severity,
                damage_confidence=detection.confidence,
                priority_score=priority.score, priority=priority.priority,
                recommended_action=priority.recommended_action,
                status=status,
                assigned_technician_id=technician.id if technician else None,
                created_at=created_at, updated_at=created_at,
            )
            db.add(complaint)
            db.flush()
            created.append(complaint)

            if status in {"REPAIRED", "VERIFIED"}:
                repair = Repair(
                    complaint_id=complaint.id,
                    technician_id=technician.id,
                    repair_notes=(f"{DEMO_PREFIX} Example workflow completion only; not a real repair."),
                    repair_cost=None,
                    completed_at=created_at + timedelta(days=1),
                    verification_status="VERIFIED" if status == "VERIFIED" else "PENDING",
                )
                if status == "VERIFIED":
                    repair.verified_at = created_at + timedelta(days=2)
                    repair.verification_notes = f"{DEMO_PREFIX} Example verification only; not a real inspection."
                db.add(repair)
                repairs_created += 1
                if status == "VERIFIED":
                    db.add(Outcome(
                        complaint_id=complaint.id,
                        result="VERIFIED",
                        notes=f"{DEMO_PREFIX} Example workflow state only; not a real repair outcome.",
                        created_at=created_at + timedelta(days=2),
                    ))
                    outcomes_created += 1

        # Recalculate only the newly inserted demo baselines against the final
        # synthetic recurrence set, using the same rule engine as complaints.
        for complaint in created:
            duplicates = duplicate_service.find_duplicates(
                db, complaint.latitude, complaint.longitude,
                complaint.road_u, complaint.road_v, complaint.road_key,
            )
            duplicates = [item for item in duplicates if item["complaint_id"] != complaint.id]
            road = road_features_for(complaint)
            priority = priority_engine.calculate(
                complaint.damage_type, complaint.damage_severity,
                complaint.damage_confidence, road, repeat_reports=len(duplicates),
            )
            complaint.priority_score = priority.score
            complaint.priority = priority.priority
            complaint.recommended_action = priority.recommended_action

        db.commit()
        print(f"Synthetic demo complaints added: {len(created)}")
        print(f"Total complaints now: {existing_count + len(created)} (pre-existing rows preserved: {existing_count})")
        print(f"Demo technicians available: {len(technicians)}; active total: {db.query(User).filter(User.role == 'TECHNICIAN', User.is_active == 1).count()}")
        print(f"Synthetic workflow repair records: {repairs_created}; synthetic outcomes: {outcomes_created}; no costs recorded")
        print(f"RDD images copied into data/uploads: {images_copied}; distinct images selected: {len(chosen_images)}")
        print(f"YOLO detections by stored model result: {dict(image_class_counts)}")
        print("Priority model and its training data were not changed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Append marked synthetic records; default is read-only dry-run")
    run(parser.parse_args().apply)

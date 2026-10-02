"""Deterministically pick Unified validation images with real YOLO support."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from backend.ai.road_damage_detector import DamageDetection, Detection, RoadDamageDetector


PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMAGE_DIR = PROJECT_ROOT / "data" / "processed" / "road_damage_unified" / "images" / "val"
LABEL_DIR = PROJECT_ROOT / "data" / "processed" / "road_damage_unified" / "labels" / "val"
CLASS_IDS = (0, 1, 2, 3)
TYPE_BY_ID = {
    0: "longitudinal_crack",
    1: "transverse_crack",
    2: "alligator_crack",
    3: "pothole",
}


@dataclass(frozen=True)
class DemoImage:
    source: Path
    sha256: str
    ground_truth_class_id: int
    prediction: Detection
    detections: tuple[Detection, ...]

    def as_damage_detection(self) -> DamageDetection:
        damage_type = TYPE_BY_ID[self.ground_truth_class_id]
        return DamageDetection(
            damage_type=damage_type,
            severity=RoadDamageDetector.SEVERITY_BY_CLASS[damage_type],
            confidence=self.prediction.confidence,
            description=f"YOLO26 {self.prediction.detection_state} {self.prediction.class_name} candidate.",
            detection_state=self.prediction.detection_state,
            detections=list(self.detections),
            primary_detection=self.prediction,
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _label_score(label: Path) -> dict[int, tuple[float, int]]:
    by_class: dict[int, tuple[float, int]] = {}
    for line_num, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 5:
            raise ValueError(f"Malformed Unified label at {label}:{line_num}")
        class_id = int(fields[0])
        if class_id not in TYPE_BY_ID:
            raise ValueError(f"Unsupported Unified class ID {class_id} in {label}:{line_num}")
        width, height = float(fields[3]), float(fields[4])
        if not 0 < width <= 1 or not 0 < height <= 1:
            raise ValueError(f"Invalid normalized box dimensions in {label}:{line_num}")
        area, count = by_class.get(class_id, (0.0, 0))
        by_class[class_id] = (max(area, width * height), count + 1)
    return by_class


def image_candidates(max_candidates_per_class: int = 128) -> dict[int, list[tuple[Path, float, int]]]:
    if not IMAGE_DIR.is_dir() or not LABEL_DIR.is_dir():
        raise FileNotFoundError(f"Unified validation images/labels are missing: {IMAGE_DIR} / {LABEL_DIR}")
    grouped: dict[int, list[tuple[Path, float, int]]] = {class_id: [] for class_id in CLASS_IDS}
    for label in LABEL_DIR.glob("*.txt"):
        image = next((candidate for candidate in IMAGE_DIR.glob(f"{label.stem}.*")
                      if candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}), None)
        if image is None:
            continue
        by_class = _label_score(label)
        for class_id, (area, count) in by_class.items():
            grouped[class_id].append((image, area, count))
    for class_id, candidates in grouped.items():
        candidates.sort(key=lambda item: (-item[1], -item[2], item[0].name.casefold()))
        grouped[class_id] = candidates[:max_candidates_per_class]
    return grouped


def select_demo_images(
    detector: RoadDamageDetector,
    count: int,
    existing_hashes: set[str] | None = None,
    max_candidates_per_class: int = 128,
) -> list[DemoImage]:
    if count < 1:
        return []
    if detector.model is None:
        raise RuntimeError(f"YOLO26 model unavailable: {detector.model_error}")
    grouped = image_candidates(max_candidates_per_class)
    targets = [CLASS_IDS[index % len(CLASS_IDS)] for index in range(count)]
    seen_hashes = set(existing_hashes or ())
    used_images: set[Path] = set()
    predictions: dict[Path, DamageDetection] = {}
    chosen: list[DemoImage] = []

    for target_id in targets:
        match = None
        for image, _area, _box_count in grouped[target_id]:
            image = image.resolve()
            if image in used_images:
                continue
            digest = _sha256(image)
            if digest in seen_hashes:
                continue
            prediction = predictions.get(image)
            if prediction is None:
                prediction = detector.predict(str(image))
                predictions[image] = prediction
            target_type = TYPE_BY_ID[target_id]
            target_boxes = [box for box in prediction.detections
                            if box.class_id == target_id and box.damage_type == target_type]
            if not target_boxes:
                continue
            primary = max(target_boxes, key=lambda box: (box.confidence, -box.y1, -box.x1))
            match = DemoImage(image, digest, target_id, primary, tuple(prediction.detections))
            break
        if match is None:
            raise RuntimeError(
                f"Could not find a distinct, YOLO-supported Unified image for class {target_id}; "
                "no demo records were changed. Increase the deterministic candidate limit or reduce demo count."
            )
        chosen.append(match)
        seen_hashes.add(match.sha256)
        used_images.add(match.source.resolve())
    return chosen

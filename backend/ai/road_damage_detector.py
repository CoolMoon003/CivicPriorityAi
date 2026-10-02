from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional

from backend.ai.detection_policy import (
    CONFIRMED,
    DEFAULT_POLICY,
    NO_RELIABLE_DETECTION,
    POSSIBLE,
    DetectionPolicy,
)


@dataclass
class Detection:
    """Plain-Python representation of one model bounding-box prediction."""

    class_id: int
    class_name: str
    damage_type: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    detection_state: str
    severity: str

    def as_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "damage_type": self.damage_type,
            "detection_state": self.detection_state,
            "severity": self.severity,
            "confidence": self.confidence,
            "bbox": {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2},
        }


@dataclass
class DamageDetection:
    damage_type: str
    severity: str
    confidence: float
    description: str
    detection_state: str = NO_RELIABLE_DETECTION
    detections: list[Detection] = field(default_factory=list)
    primary_detection: Detection | None = None

    @property
    def all_relevant_detections(self) -> list[Detection]:
        return self.detections


class RoadDamageDetector:
    """YOLO26 road-damage adapter; severity remains application policy."""

    EXPECTED_CLASSES = {
        0: ("Longitudinal Crack (D00)", "longitudinal_crack"),
        1: ("Transverse Crack (D10)", "transverse_crack"),
        2: ("Alligator Crack (D20)", "alligator_crack"),
        3: ("Pothole (D40)", "pothole"),
    }
    DAMAGE_TYPES = {value[1] for value in EXPECTED_CLASSES.values()} | {"unknown"}
    SEVERITIES = {"low", "medium", "high", "unknown"}
    SEVERITY_BY_CLASS = {
        "pothole": "high",
        "alligator_crack": "high",
        "longitudinal_crack": "medium",
        "transverse_crack": "medium",
    }
    SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "unknown": 0}
    DEFAULT_CONFIDENCE_THRESHOLD = DEFAULT_POLICY.confirmed_threshold

    def __init__(self, model_path: Optional[str] = None):
        self.project_root = Path(__file__).resolve().parents[2]
        configured_path = model_path or os.getenv("CIVIC_ROAD_DAMAGE_MODEL")
        path = Path(configured_path) if configured_path else self.project_root / "models" / "YOLO26s_RDD_Base.pt"
        self.model_path = path if path.is_absolute() else self.project_root / path
        self.policy = DetectionPolicy.from_environment()
        self.confidence_threshold = self.policy.confirmed_threshold
        self.possible_threshold = self.policy.possible_threshold
        self.inference_size = self.policy.inference_size
        self.fallback_inference_size = self.policy.fallback_inference_size

        self.model = None
        self.model_error: str | None = None
        self.last_timing_ms: dict[str, float] = {}
        self.last_inference_sizes: list[int] = []
        self.class_names: dict[int, str] = {}
        if not self.model_path.is_file():
            self.model_error = f"YOLO26 checkpoint not found: {self.model_path}"
        else:
            self._load_model()

    @classmethod
    def validate_class_mapping(cls, names) -> None:
        """Require the four expected IDs and labels before accepting a model."""
        if isinstance(names, dict):
            entries = {int(key): str(value) for key, value in names.items()}
        elif isinstance(names, (list, tuple)):
            entries = {index: str(value) for index, value in enumerate(names)}
        else:
            raise ValueError(f"Invalid YOLO26 class names mapping: {names!r}")
        if set(entries) != set(cls.EXPECTED_CLASSES):
            raise ValueError(f"YOLO26 must contain exactly class IDs 0-3; got {entries!r}")
        for class_id, (expected_label, _) in cls.EXPECTED_CLASSES.items():
            actual = _normalize_label(entries[class_id])
            expected_base, expected_code = expected_label[:-1].split(" (")
            expected_base = _normalize_label(expected_base)
            expected_code = _normalize_label(expected_code)
            # Permit D-code before or after the name, or omitted, while still
            # rejecting a conflicting code or a different class name.
            actual_base = actual.replace(expected_code, "")
            found_codes = [f"d{number:02d}" for number in range(100) if f"d{number:02d}" in actual]
            if actual_base != expected_base or any(code != expected_code for code in found_codes):
                raise ValueError(
                    f"YOLO26 class mapping mismatch at ID {class_id}: expected "
                    f"{expected_label!r}, got {entries[class_id]!r}"
                )

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO

            model = YOLO(str(self.model_path))
            self.validate_class_mapping(model.names)
            self.class_names = _names_by_id(model.names)
            self.model = model
        except Exception as exc:
            self.model_error = f"Could not load or validate YOLO26 checkpoint {self.model_path}: {exc}"
            self.model = None

    def predict(self, image_path: str) -> DamageDetection:
        image = Path(image_path)
        if not image.exists():
            raise FileNotFoundError(f"Image not found: {image}")
        if not image.is_file():
            raise ValueError(f"Not a file: {image}")
        try:
            from PIL import Image

            with Image.open(image) as source_image:
                source_image.verify()
        except Exception as exc:
            raise ValueError(f"Invalid image file {image}: {exc}") from exc
        if self.model is None:
            raise RuntimeError(self.model_error or "YOLO26 model is unavailable")

        self.last_timing_ms = {}
        self.last_inference_sizes = []

        def infer_at_size(size: int) -> list[Detection]:
            try:
                results = self.model.predict(
                    source=str(image), conf=self.possible_threshold,
                    imgsz=size, verbose=False, device="cpu"
                )
            except Exception as exc:
                raise RuntimeError(f"YOLO26 inference failed for {image} at imgsz={size}: {exc}") from exc
            self.last_inference_sizes.append(size)
            found: list[Detection] = []
            for result in results or []:
                speed = getattr(result, "speed", None)
                if isinstance(speed, dict):
                    for key in ("preprocess", "inference", "postprocess"):
                        if key in speed:
                            self.last_timing_ms[key] = self.last_timing_ms.get(key, 0.0) + float(speed[key])
                boxes = getattr(result, "boxes", None)
                if boxes is None:
                    continue
                classes = getattr(boxes, "cls", None)
                confidences = getattr(boxes, "conf", None)
                xyxy = getattr(boxes, "xyxy", None)
                if classes is None or confidences is None or xyxy is None:
                    continue
                for class_id_value, confidence_value, coords in zip(classes, confidences, xyxy):
                    class_id = int(_scalar(class_id_value))
                    if class_id not in self.EXPECTED_CLASSES:
                        raise RuntimeError(f"YOLO26 returned unexpected class ID {class_id}")
                    confidence = float(_scalar(confidence_value))
                    state = self.policy.state_for(confidence)
                    if state == NO_RELIABLE_DETECTION:
                        continue
                    _, damage_type = self.EXPECTED_CLASSES[class_id]
                    class_name = self.class_names.get(class_id, self.EXPECTED_CLASSES[class_id][0])
                    coords = coords.tolist() if hasattr(coords, "tolist") else list(coords)
                    found.append(Detection(
                        class_id=class_id,
                        class_name=class_name,
                        damage_type=damage_type,
                        detection_state=state,
                        severity=self.SEVERITY_BY_CLASS[damage_type],
                        confidence=confidence,
                        x1=float(coords[0]), y1=float(coords[1]),
                        x2=float(coords[2]), y2=float(coords[3]),
                    ))
            return found

        detections = infer_at_size(self.inference_size)
        if not detections and self.fallback_inference_size and self.fallback_inference_size != self.inference_size:
            # A single larger pass is conditional: normal detections stay at
            # 640, while resolution-sensitive misses can surface as uncertain.
            detections = infer_at_size(self.fallback_inference_size)

        if not detections:
            return DamageDetection(
                damage_type="unknown", severity="unknown", confidence=0.0,
                description=(
                    "No reliable road-damage detection was produced. "
                    f"Possible evidence begins at {self.possible_threshold:.0%} confidence. "
                    f"Checked image sizes: {', '.join(map(str, self.last_inference_sizes))}."
                ),
                detection_state=NO_RELIABLE_DETECTION,
            )

        # Stable tie-breaks: severity, confidence, then lower class ID and box position.
        primary = select_primary_detection(detections)
        counts = Counter(item.damage_type for item in detections)
        labels = {
            "pothole": ("pothole", "potholes"),
            "longitudinal_crack": ("longitudinal crack", "longitudinal cracks"),
            "transverse_crack": ("transverse crack", "transverse cracks"),
            "alligator_crack": ("alligator crack", "alligator cracks"),
        }
        summary = ", ".join(
            f"{count} {labels[damage_type][0 if count == 1 else 1]}"
            for damage_type, count in sorted(counts.items())
        )
        if primary.detection_state == POSSIBLE:
            description = (
                f"Possible {primary.damage_type.replace('_', ' ')} evidence "
                f"({primary.confidence:.2%}); AI uncertain. Manual verification recommended."
            )
        else:
            description = (
                f"Detected {len(detections)} road damage{'s' if len(detections) != 1 else ''}: {summary}. "
                f"Primary: {primary.damage_type.replace('_', ' ')} ({primary.confidence:.0%} confidence)."
            )
        return DamageDetection(
            damage_type=primary.damage_type,
            severity=primary.severity,
            confidence=primary.confidence,
            description=description,
            detection_state=primary.detection_state,
            detections=detections,
            primary_detection=primary,
        )


def _normalize_label(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _scalar(value) -> float:
    return float(value.item() if hasattr(value, "item") else value)


def _names_by_id(names) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(key): str(value) for key, value in names.items()}
    return {index: str(value) for index, value in enumerate(names)}


def select_primary_detection(detections: list[Detection]) -> Detection:
    """Severity-first selection with stable state, confidence, and box tie-breaks."""
    return max(detections, key=lambda item: (
        RoadDamageDetector.SEVERITY_RANK[item.severity],
        item.detection_state == CONFIRMED,
        item.confidence,
        -item.class_id,
        -item.y1,
        -item.x1,
        -item.y2,
        -item.x2,
    ))

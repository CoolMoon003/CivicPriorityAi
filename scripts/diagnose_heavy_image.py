r"""CPU-only multi-resolution diagnostic for a selected road-damage image.

Usage:
  .venv\Scripts\python.exe scripts\diagnose_heavy_image.py
  .venv\Scripts\python.exe scripts\diagnose_heavy_image.py path\to\road-image.jpg

The 0.001 threshold is diagnostic only. It never changes production policy.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.detection_policy import DEFAULT_POLICY, NO_RELIABLE_DETECTION  # noqa: E402
from backend.ai.road_damage_detector import (  # noqa: E402
    Detection,
    RoadDamageDetector,
    select_primary_detection,
)


CHECKPOINT = ROOT / "models" / "YOLO26s_RDD_Base.pt"
DEFAULT_IMAGE = ROOT / "data" / "sample" / "road_damage" / "India_000361.jpg"
SIZES = (640, 832, 1024, 1280)
DIAGNOSTIC_CONFIDENCE = 0.001
OUTPUT_IMAGE = ROOT / "runs" / "inference" / "heavy_diagnostic" / "heavy.jpg"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE)
    args = parser.parse_args()
    image = args.image.resolve()
    if not image.is_file():
        parser.error(f"Image not found: {image}")
    if not CHECKPOINT.is_file():
        parser.error(f"Active YOLO26 checkpoint not found: {CHECKPOINT}")

    from ultralytics import YOLO
    from PIL import Image

    model = YOLO(str(CHECKPOINT))
    RoadDamageDetector.validate_class_mapping(model.names)
    print(f"checkpoint={CHECKPOINT}")
    print(f"runtime_class_names={model.names}")
    print(f"production_confirmed_threshold={DEFAULT_POLICY.confirmed_threshold:.3f}")
    print(f"production_possible_threshold={DEFAULT_POLICY.possible_threshold:.3f}")
    print(f"diagnostic_confidence={DIAGNOSTIC_CONFIDENCE:.3f} (diagnostic only)")

    best_by_class = {name: 0.0 for name in RoadDamageDetector.SEVERITY_BY_CLASS}
    selected_at_size: dict[int, Detection | None] = {}
    annotated = None

    for size in SIZES:
        results = model.predict(
            source=str(image), imgsz=size, conf=DIAGNOSTIC_CONFIDENCE,
            verbose=False, device="cpu",
        )
        result = results[0] if results else None
        candidates: list[Detection] = []
        boxes = getattr(result, "boxes", None) if result is not None else None
        if boxes is not None:
            names = getattr(result, "names", None) or model.names
            for box in boxes:
                class_id = int(box.cls.item())
                class_name = names[class_id] if isinstance(names, (list, tuple)) else names[class_id]
                if class_id not in RoadDamageDetector.EXPECTED_CLASSES:
                    raise RuntimeError(f"Model returned unexpected class ID {class_id}")
                _, damage_type = RoadDamageDetector.EXPECTED_CLASSES[class_id]
                confidence = float(box.conf.item())
                best_by_class[damage_type] = max(best_by_class[damage_type], confidence)
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                state = DEFAULT_POLICY.state_for(confidence)
                print(
                    f"imgsz={size} class_id={class_id} class={class_name} "
                    f"confidence={confidence:.4%} bbox={[round(x, 2) for x in (x1, y1, x2, y2)]}"
                )
                if state != NO_RELIABLE_DETECTION:
                    candidates.append(Detection(
                        class_id, str(class_name), damage_type, confidence,
                        x1, y1, x2, y2, state,
                        RoadDamageDetector.SEVERITY_BY_CLASS[damage_type],
                    ))
        primary = select_primary_detection(candidates) if candidates else None
        selected_at_size[size] = primary
        print(f"imgsz={size} policy_primary={primary.as_dict() if primary else 'none'}")
        if size == 1280 and result is not None:
            annotated = result.plot()

    print("highest_confidence_by_class:")
    for damage_type, confidence in best_by_class.items():
        print(f"  {damage_type}: {confidence:.4%}")
    print("selected_production_policy_primary_by_size:")
    for size, primary in selected_at_size.items():
        if primary:
            print(f"  {size}: {primary.damage_type} {primary.confidence:.4%} ({primary.detection_state})")
        else:
            print(f"  {size}: none")

    if annotated is not None:
        import numpy as np

        OUTPUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.asarray(annotated)[:, :, ::-1].copy()).save(OUTPUT_IMAGE)
        print(f"annotated_output={OUTPUT_IMAGE}")
    else:
        print("annotated_output=not saved; YOLO returned no result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

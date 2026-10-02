"""Print raw and application-wrapped YOLO detections for one exact image.

Usage:
  .venv\\Scripts\\python.exe scripts\\diagnose_road_damage.py data\\uploads\\<image>.jpg

This is a read-only diagnostic. It never modifies the image, checkpoint, or DB.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = ROOT / "models" / "YOLO26s_RDD_Base.pt"
sys.path.insert(0, str(ROOT))

from backend.ai.road_damage_detector import RoadDamageDetector  # noqa: E402


def parse_values(value: str, cast):
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def describe_image(path: Path) -> None:
    with Image.open(path) as image:
        exif_orientation = image.getexif().get(274)
        oriented = ImageOps.exif_transpose(image)
        print("IMAGE")
        print(f"  path: {path}")
        print(f"  absolute: {path.resolve()}")
        print(f"  exists: {path.is_file()}")
        print(f"  size_bytes: {path.stat().st_size}")
        print(f"  format: {image.format}")
        print(f"  dimensions: {image.width}x{image.height}")
        print(f"  mode/channels: {image.mode}/{len(image.getbands())}")
        print(f"  exif_orientation: {exif_orientation!r}")
        print(f"  exif_transposed_dimensions: {oriented.width}x{oriented.height}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="Checkpoint override; defaults to CIVIC_ROAD_DAMAGE_MODEL or the current production checkpoint")
    parser.add_argument("--confidences", default="0.01,0.05,0.10,0.15,0.25,0.40")
    parser.add_argument("--sizes", default="640", help="Comma-separated Ultralytics imgsz values")
    args = parser.parse_args()
    image_path = args.image if args.image.is_absolute() else ROOT / args.image
    configured_checkpoint = args.checkpoint or (Path(os.environ["CIVIC_ROAD_DAMAGE_MODEL"]) if os.getenv("CIVIC_ROAD_DAMAGE_MODEL") else DEFAULT_CHECKPOINT)
    checkpoint = configured_checkpoint if configured_checkpoint.is_absolute() else ROOT / configured_checkpoint
    if not image_path.is_file():
        parser.error(f"Image does not exist: {image_path}")
    if not checkpoint.is_file():
        parser.error(f"Checkpoint does not exist: {checkpoint}")

    describe_image(image_path)
    print("CHECKPOINT")
    print(f"  active_path: {checkpoint.resolve()}")
    print(f"  size_bytes: {checkpoint.stat().st_size}")
    print(f"  modified: {datetime.fromtimestamp(checkpoint.stat().st_mtime).isoformat()}")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    print(f"  sha256: {digest}")

    from ultralytics import YOLO

    model = YOLO(str(checkpoint))
    print(f"  names: {model.names}")
    print(f"  class_count: {len(model.names)}")
    print(f"  task: {model.task}")
    training_args = getattr(model, "overrides", {}) or {}
    print(f"  training_imgsz: {training_args.get('imgsz', 'not present in model overrides')}")

    confidences = parse_values(args.confidences, float)
    sizes = parse_values(args.sizes, int)
    for imgsz in sizes:
        for confidence in confidences:
            results = model.predict(source=str(image_path), conf=confidence, imgsz=imgsz, verbose=False)
            print(f"RAW imgsz={imgsz} conf={confidence:.2f}")
            total = 0
            for result in results or []:
                boxes = getattr(result, "boxes", None)
                if boxes is None:
                    continue
                names = getattr(result, "names", None) or model.names
                for box in boxes:
                    class_id = int(box.cls.item())
                    score = float(box.conf.item())
                    xyxy = [round(float(v), 2) for v in box.xyxy[0].tolist()]
                    class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else names[class_id]
                    print(f"  class_id={class_id} class={class_name} confidence={score:.6f} xyxy={xyxy}")
                    total += 1
            print(f"  raw_box_count={total}")

    detector = RoadDamageDetector(str(checkpoint))
    print(f"WRAPPER confidence_threshold={detector.confidence_threshold}")
    print(f"  model_loaded={detector.model is not None} error={detector.model_error}")
    result = detector.predict(str(image_path))
    print("  primary:")
    print(json.dumps({
        "damage_type": result.damage_type,
        "severity": result.severity,
        "confidence": result.confidence,
        "description": result.description,
    }, indent=2))
    print("  standardized_detections:")
    print(json.dumps([item.as_dict() for item in result.detections], indent=2))
    print(f"  timing_ms={json.dumps(detector.last_timing_ms, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

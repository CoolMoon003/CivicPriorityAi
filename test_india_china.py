r"""Small stratified YOLO26 validation diagnostic (never scans the full val set).

Usage:
  .venv\Scripts\python.exe test_india_china.py --per-class-origin 2

Reports confidence-threshold behavior and class-aware IoU@0.5 matches. Confidence
is not correctness; this script compares predictions to the dataset labels.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.ai.road_damage_detector import RoadDamageDetector  # noqa: E402

MODEL_PATH = ROOT / "models" / "YOLO26s_RDD_Base.pt"
IMAGE_DIR = ROOT / "data" / "processed" / "road_damage_unified" / "images" / "val"
LABEL_DIR = ROOT / "data" / "processed" / "road_damage_unified" / "labels" / "val"
CLASS_NAMES = {
    0: "Longitudinal Crack (D00)",
    1: "Transverse Crack (D10)",
    2: "Alligator Crack (D20)",
    3: "Pothole (D40)",
}
THRESHOLDS = (0.10, 0.15, 0.20, 0.25)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    items = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            class_id = int(fields[0])
            if class_id in CLASS_NAMES:
                items.append((class_id, *(float(value) for value in fields[1:5])))
        except ValueError:
            continue
    return items


def image_for_label(label: Path) -> Path | None:
    return next((IMAGE_DIR / f"{label.stem}{ext}" for ext in IMAGE_EXTENSIONS
                 if (IMAGE_DIR / f"{label.stem}{ext}").is_file()), None)


def source_of(filename: str) -> str | None:
    name = filename.lower()
    if "india" in name:
        return "India"
    if "china" in name:
        return "China"
    return None


def iou_xyxy(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def gt_xyxy(label, width, height):
    class_id, cx, cy, box_w, box_h = label
    return class_id, ((cx - box_w / 2) * width, (cy - box_h / 2) * height,
                      (cx + box_w / 2) * width, (cy + box_h / 2) * height)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class-origin", type=int, default=2,
                        help="Images per class and India/China source (default: 2; max: 10)")
    parser.add_argument("--seed", type=int, default=2609)
    args = parser.parse_args()
    if not 1 <= args.per_class_origin <= 10:
        parser.error("--per-class-origin must be between 1 and 10")
    if not MODEL_PATH.is_file() or not IMAGE_DIR.is_dir() or not LABEL_DIR.is_dir():
        parser.error("YOLO26 checkpoint or processed validation image/label directory is missing")

    labels_by_image = {}
    groups = defaultdict(list)
    for label_path in LABEL_DIR.glob("*.txt"):
        image_path = image_for_label(label_path)
        origin = source_of(label_path.name)
        if not image_path or not origin:
            continue
        labels = read_labels(label_path)
        labels_by_image[image_path] = labels
        for class_id in sorted({item[0] for item in labels}):
            groups[(origin, class_id)].append(image_path)

    rng = random.Random(args.seed)
    selected = set()
    for key, paths in sorted(groups.items()):
        chosen = sorted(rng.sample(paths, min(args.per_class_origin, len(paths))))
        selected.update(chosen)
        print(f"sample_stratum={key[0]}/{CLASS_NAMES[key[1]]} selected_images={len(chosen)} available={len(paths)}")
    print(f"unique_sample_images={len(selected)} (validation total is not scanned for inference)")

    from ultralytics import YOLO

    model = YOLO(str(MODEL_PATH))
    RoadDamageDetector.validate_class_mapping(model.names)
    print(f"runtime_model_names={model.names}")
    print("note=confidence is not correctness; correctness below uses class-aware IoU >= 0.50")

    records = []
    for image_path in sorted(selected):
        result = model.predict(source=str(image_path), imgsz=640, conf=0.001,
                               verbose=False, device="cpu")[0]
        height, width = result.orig_shape
        predictions = []
        if result.boxes is not None:
            for box in result.boxes:
                xyxy = tuple(float(value) for value in box.xyxy[0].tolist())
                predictions.append((int(box.cls.item()), float(box.conf.item()), xyxy))
        ground_truth = [gt_xyxy(item, width, height) for item in labels_by_image[image_path]]
        records.append((source_of(image_path.name), image_path.name, ground_truth, predictions))

    for threshold in THRESHOLDS:
        print(f"\nthreshold={threshold:.2f}")
        for origin in ("India", "China"):
            for class_id, class_name in CLASS_NAMES.items():
                tp = fp = fn = 0
                images = 0
                for record_origin, _, ground_truth, predictions in records:
                    if record_origin != origin:
                        continue
                    gt_boxes = [box for cls, box in ground_truth if cls == class_id]
                    pred_boxes = sorted(
                        [(conf, box) for cls, conf, box in predictions
                         if cls == class_id and conf >= threshold],
                        key=lambda item: -item[0],
                    )
                    if gt_boxes or pred_boxes:
                        images += 1
                    matched = set()
                    for _, pred in pred_boxes:
                        best = max(((iou_xyxy(pred, gt), index) for index, gt in enumerate(gt_boxes)
                                    if index not in matched), default=(0.0, -1))
                        if best[0] >= 0.5:
                            tp += 1
                            matched.add(best[1])
                        else:
                            fp += 1
                    fn += len(gt_boxes) - len(matched)
                precision = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / (tp + fn) if tp + fn else 0.0
                if tp + fp + fn:
                    print(f"  {origin:5s} {class_name:27s} P={precision:.3f} R={recall:.3f} TP={tp} FP={fp} FN={fn} active_images={images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

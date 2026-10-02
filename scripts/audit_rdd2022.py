"""Read-only integrity and class-balance audit for the local RDD2022 India YOLO data."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import math

from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "RDD2022_India" / "data"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    config = yaml.safe_load((DATA / "data.yaml").read_text(encoding="utf-8"))
    names = config["names"]
    names = {int(key): value for key, value in names.items()} if isinstance(names, dict) else dict(enumerate(names))
    print("Class map:", names)

    for split in ("train", "valid", "test"):
        image_root = DATA / "images" / split
        label_root = DATA / "labels" / split
        images = sorted(path for path in image_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
        labels = sorted(label_root.rglob("*.txt"))
        image_keys = {path.relative_to(image_root).with_suffix("").as_posix() for path in images}
        label_keys = {path.relative_to(label_root).with_suffix("").as_posix() for path in labels}
        box_counts, image_counts, issues, dimensions = Counter(), Counter(), Counter(), Counter()
        empty_labels = 0
        for image in images:
            label = label_root / image.relative_to(image_root).with_suffix(".txt")
            try:
                with Image.open(image) as opened:
                    opened.verify()
                with Image.open(image) as opened:
                    width, height = opened.size
                    dimensions[(width, height)] += 1
            except Exception:
                issues["corrupt_images"] += 1
                continue
            if not label.is_file():
                continue
            content = label.read_text(encoding="utf-8").strip()
            if not content:
                empty_labels += 1
                continue
            present = set()
            for row in content.splitlines():
                parts = row.split()
                if len(parts) != 5:
                    issues["malformed_rows"] += 1
                    continue
                try:
                    class_id = int(parts[0])
                    x, y, box_w, box_h = map(float, parts[1:])
                except (ValueError, OverflowError):
                    issues["malformed_values"] += 1
                    continue
                values = (x, y, box_w, box_h)
                if class_id not in names:
                    issues["invalid_class_ids"] += 1
                    continue
                if any(not math.isfinite(value) for value in values) or not all(0 <= value <= 1 for value in values) or box_w <= 0 or box_h <= 0:
                    issues["invalid_yolo_boxes"] += 1
                    continue
                if x - box_w / 2 < 0 or y - box_h / 2 < 0 or x + box_w / 2 > 1 or y + box_h / 2 > 1:
                    issues["boxes_crossing_image_edge"] += 1
                box_counts[class_id] += 1
                present.add(class_id)
            for class_id in present:
                image_counts[class_id] += 1

        print(f"\n{split}: images={len(images)} labels={len(labels)} empty_labels={empty_labels}")
        print(f"  images_without_matching_label={len(image_keys - label_keys)} orphan_label_files={len(label_keys - image_keys)}")
        print(f"  dimensions={dict(dimensions)}")
        print(f"  images_with_class={{{', '.join(f'{names[k]}: {image_counts[k]}' for k in names)}}}")
        print(f"  boxes_by_class={{{', '.join(f'{names[k]}: {box_counts[k]}' for k in names)}}}")
        print(f"  integrity_issues={dict(issues)}")


if __name__ == "__main__":
    main()

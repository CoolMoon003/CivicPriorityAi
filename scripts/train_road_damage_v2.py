"""Train a separate class-aware fine-tune without replacing the active detector.

Transverse-crack images are repeated in the training manifest because the
audited dataset has only 50 boxes in 44 images for that class. The original
images and labels are not changed; normal Ultralytics augmentation still runs.
Validation uses the untouched `valid` split.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import random

import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "raw" / "RDD2022_India" / "data"
INITIAL_WEIGHTS = ROOT / "experiments" / "road_damage_training" / "historical_RDD2022" / "road_damage_v1" / "weights" / "best.pt"
PROJECT = ROOT / "experiments" / "road_damage_training" / "historical_RDD2022"
RUN_NAME = "road_damage_v2"
CONFIG_DIR = PROJECT / "road_damage_v2_config"


def build_training_manifest(transverse_repeat: int) -> tuple[Path, Path, Counter]:
    source = yaml.safe_load((DATA_ROOT / "data.yaml").read_text(encoding="utf-8"))
    names = source["names"]
    names = {int(key): value for key, value in names.items()} if isinstance(names, dict) else dict(enumerate(names))
    if names != {0: "longitudinal_crack", 1: "transverse_crack", 2: "alligator_crack", 3: "pothole"}:
        raise ValueError(f"Unexpected RDD2022 class mapping; refusing to train: {names}")
    if transverse_repeat < 1:
        raise ValueError("transverse_repeat must be at least 1")

    image_root = DATA_ROOT / "images" / "train"
    label_root = DATA_ROOT / "labels" / "train"
    weighted_images = []
    for image in sorted(path for path in image_root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}):
        label = label_root / image.relative_to(image_root).with_suffix(".txt")
        classes = set()
        if label.is_file():
            for row in label.read_text(encoding="utf-8").splitlines():
                parts = row.split()
                if parts:
                    try:
                        classes.add(int(parts[0]))
                    except ValueError:
                        continue
        repeats = transverse_repeat if 1 in classes else 1
        weighted_images.extend([str(image.resolve())] * repeats)

    random.Random(42).shuffle(weighted_images)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    manifest = CONFIG_DIR / "train_images.txt"
    manifest.write_text("\n".join(weighted_images) + "\n", encoding="utf-8")
    data_yaml = CONFIG_DIR / "data.yaml"
    custom_data = {
        "path": str(DATA_ROOT),
        "train": str(manifest),
        "val": str(DATA_ROOT / "images" / "valid"),
        "test": str(DATA_ROOT / "images" / "test"),
        "nc": 4,
        "names": names,
    }
    data_yaml.write_text(yaml.safe_dump(custom_data, sort_keys=False), encoding="utf-8")
    return manifest, data_yaml, Counter(weighted_images)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--transverse-repeat", type=int, default=8)
    parser.add_argument("--resume", action="store_true", help="Resume from road_damage_v2/weights/last.pt")
    args = parser.parse_args()
    target = PROJECT / RUN_NAME
    if (target / "weights" / "best.pt").exists() and not args.resume:
        raise FileExistsError(f"Refusing to overwrite existing v2 checkpoint: {target / 'weights' / 'best.pt'}")
    resume_checkpoint = target / "weights" / "last.pt"
    if args.resume and not resume_checkpoint.is_file():
        raise FileNotFoundError(f"Cannot resume without {resume_checkpoint}")
    if not args.resume and not INITIAL_WEIGHTS.is_file():
        raise FileNotFoundError(f"Initial checkpoint not found: {INITIAL_WEIGHTS}")

    manifest, data_yaml, samples = build_training_manifest(args.transverse_repeat)
    print(f"Starting from: {resume_checkpoint if args.resume else INITIAL_WEIGHTS}")
    print(f"Training manifest: {manifest} ({sum(samples.values())} image entries)")
    print(f"Transverse-containing entries repeated {args.transverse_repeat}x; {data_yaml}")
    model = YOLO(str(resume_checkpoint if args.resume else INITIAL_WEIGHTS))
    if args.resume:
        model.train(resume=True, device="cpu")
        print(f"Resumed v2 checkpoint: {target / 'weights' / 'best.pt'}")
        return
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=0,
        device="cpu",
        cache=False,
        optimizer="auto",
        project=str(PROJECT),
        name=RUN_NAME,
        exist_ok=True,
        seed=42,
        deterministic=True,
        save=True,
        save_period=5,
        val=True,
        plots=True,
        close_mosaic=10,
    )
    print(f"Best v2 checkpoint: {target / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()

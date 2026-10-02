"""Compare v1 and v2 YOLO checkpoints on held-out splits and fixed complaints.

This is read-only with respect to complaints and checkpoints. Metrics/plots are
written to runs/evaluation/road_damage_model_comparison/.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "experiments/road_damage_training/historical_RDD2022/road_damage_v1/weights/best.pt"
V2 = ROOT / "experiments/road_damage_training/historical_RDD2022/road_damage_v2/weights/best.pt"
DATA = ROOT / "data/raw/RDD2022_India/data/data.yaml"
DB = ROOT / "data/civic_priority.db"
OUT = ROOT / "runs/evaluation/road_damage_model_comparison"


def complaint_images() -> dict[int, Path]:
    with sqlite3.connect(DB) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(complaints)")}
        if not {"id", "image_path"}.issubset(columns):
            raise RuntimeError(f"Unexpected complaint schema: {sorted(columns)}")
        rows = conn.execute(
            "SELECT id, image_path FROM complaints WHERE id IN (6,7,13,19,51)"
        ).fetchall()
    images = {}
    for complaint_id, stored in rows:
        if not stored:
            continue
        path = Path(stored)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            images[int(complaint_id)] = path.resolve()
        else:
            print(f"COMPLAINT_IMAGE_MISSING id={complaint_id} stored={stored} resolved={path}")
    # Complaint #51 path is part of the requested exact-image comparison.
    explicit_51 = ROOT / "data/uploads/03eee4dc78bc45ccb0df3d610a5ef2ce.jpg"
    if explicit_51.is_file():
        images[51] = explicit_51.resolve()
    return images


def result_metrics(metrics) -> dict:
    box = metrics.box
    names = metrics.names
    per_class = {}
    for class_id, name in names.items():
        per_class[str(name)] = {
            "precision": float(box.p[class_id]) if class_id < len(box.p) else None,
            "recall": float(box.r[class_id]) if class_id < len(box.r) else None,
            "ap50": float(box.ap50[class_id]) if class_id < len(box.ap50) else None,
            "ap50_95": float(box.ap[class_id]) if class_id < len(box.ap) else None,
        }
    return {
        "precision": float(box.mp), "recall": float(box.mr),
        "map50": float(box.map50), "map50_95": float(box.map),
        "per_class": per_class,
    }


def image_predictions(model: YOLO, checkpoint: Path, images: dict[int, Path]) -> dict:
    output = {}
    for complaint_id, path in sorted(images.items()):
        for conf in (0.01, 0.25):
            results = model.predict(
                source=str(path), conf=conf, imgsz=640, device="cpu", verbose=False
            )
            boxes_out = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    cls = int(box.cls.item())
                    boxes_out.append({
                        "class_id": cls,
                        "class": result.names.get(cls, str(cls)),
                        "confidence": float(box.conf.item()),
                        "xyxy": [round(float(x), 2) for x in box.xyxy[0].tolist()],
                    })
            output[f"{complaint_id}@{conf:.2f}"] = {
                "path": str(path), "count": len(boxes_out), "detections": boxes_out,
            }
    return output


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dataset = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    report = {
        "checkpoints": {"v1": str(V1), "v2": str(V2)},
        "class_names": dataset.get("names"),
        "splits": {}, "complaints": {},
    }
    for version, checkpoint in (("v1", V1), ("v2", V2)):
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        model = YOLO(str(checkpoint))
        print(f"MODEL {version}: {checkpoint} names={model.names} task={model.task}")
        report[version] = {}
        for split in ("val", "test"):
            metrics = model.val(
                data=str(DATA), split=split, imgsz=640, batch=8, device="cpu",
                workers=0, plots=True, save_json=False, verbose=False,
                project=str(OUT), name=f"{version}_{split}", exist_ok=True,
            )
            split_metrics = result_metrics(metrics)
            report[version][split] = split_metrics
            print(f"METRICS {version} {split}: {json.dumps(split_metrics, sort_keys=True)}")
        report["complaints"][version] = image_predictions(model, checkpoint, complaint_images())
        print(f"COMPLAINTS {version}: {json.dumps(report['complaints'][version], sort_keys=True)}")
    result_path = OUT / "comparison.json"
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"REPORT_JSON {result_path}")


if __name__ == "__main__":
    main()

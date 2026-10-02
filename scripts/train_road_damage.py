from pathlib import Path
from ultralytics import YOLO


# Project root
ROOT = Path(__file__).resolve().parents[1]

# Dataset
DATA_YAML = ROOT / "data" / "raw" / "RDD2022_India" / "data" / "data.yaml"

# Pretrained model
MODEL = ROOT / "experiments" / "road_damage_training" / "historical_RDD2022" / "model" / "yolo11n.pt"

# Training output
PROJECT = ROOT / "experiments" / "road_damage_training" / "historical_RDD2022"
RUN_NAME = "road_damage"


def main():
    print("=" * 60)
    print("CivicPriorityAI - Road Damage Model Training")
    print("=" * 60)

    print(f"Dataset : {DATA_YAML}")
    print(f"Model   : {MODEL}")
    print(f"Output  : {PROJECT / RUN_NAME}")
    print()

    if not DATA_YAML.exists():
        raise FileNotFoundError(f"Dataset config not found: {DATA_YAML}")

    if not MODEL.exists():
        raise FileNotFoundError(f"YOLO model not found: {MODEL}")

    model = YOLO(str(MODEL))

    model.train(
        data=str(DATA_YAML),

        # CPU-friendly settings
        epochs=30,
        imgsz=640,
        batch=2,
        workers=0,
        device="cpu",
        cache=False,

        # Training output
        project=str(PROJECT),
        name=RUN_NAME,
        exist_ok=True,

        # Reproducibility
        seed=42,

        # Save best checkpoint
        save=True,
        save_period=5,

        # Validation
        val=True,
        plots=True,
    )

    print()
    print("=" * 60)
    print("Training completed.")
    print(f"Best model: {PROJECT / RUN_NAME / 'weights' / 'best.pt'}")
    print("=" * 60)


if __name__ == "__main__":
    main()

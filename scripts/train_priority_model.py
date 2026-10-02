"""Train/version the prototype priority regressor from existing complaints.

Until numeric repair-outcome labels exist, targets are recalculated deterministic
PriorityEngine scores. Metrics therefore measure baseline reproduction only.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database.database import SessionLocal  # noqa: E402
from backend.app.models.complaint import Complaint  # noqa: E402
from backend.app.services.priority_features import FEATURE_NAMES, build_for_complaint  # noqa: E402


def _pipeline(seed=42):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    try:
        imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    except TypeError:  # compatibility with older supported scikit-learn
        imputer = SimpleImputer(strategy="median", add_indicator=True)
    return Pipeline([("imputer", imputer), ("regressor", RandomForestRegressor(
        n_estimators=200, min_samples_leaf=1, random_state=seed, n_jobs=1))])


def _metrics(actual, predicted):
    errors = [float(p) - float(y) for y, p in zip(actual, predicted)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    mean = sum(actual) / len(actual)
    total = sum((float(y) - mean) ** 2 for y in actual)
    r2 = 1.0 - sum(e * e for e in errors) / total if total else None
    return {"mae": round(mae, 4), "rmse": round(rmse, 4),
            "r2": round(r2, 4) if r2 is not None else None}


def collect_samples():
    db = SessionLocal()
    try:
        complaints = db.query(Complaint).order_by(Complaint.id.asc()).all()
        samples = []
        for complaint in complaints:
            values, context = build_for_complaint(complaint, db)
            if context["baseline"].score is not None:
                samples.append(([values[name] if values[name] is not None else math.nan
                                 for name in FEATURE_NAMES],
                                float(context["baseline"].score)))
        return samples
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-only", action="store_true", help="Recompute CV metrics without writing a model")
    args = parser.parse_args()
    samples = collect_samples()
    if len(samples) < 2:
        raise SystemExit(f"Need at least 2 existing complaint records; found {len(samples)}")
    X = [item[0] for item in samples]
    y = [item[1] for item in samples]

    # Leave-one-out is reproducible and uses all currently available records.
    from sklearn.model_selection import LeaveOneOut, cross_val_predict
    cv_model = _pipeline()
    oof = cross_val_predict(cv_model, X, y, cv=LeaveOneOut())
    metrics = _metrics(y, oof)
    print(f"Training samples: {len(samples)}")
    print(f"Feature count: {len(FEATURE_NAMES)}")
    print("Feature names/order:")
    for index, name in enumerate(FEATURE_NAMES):
        print(f"  {index:02d}: {name}")
    print(f"Evaluation: leave-one-out CV; target=PriorityEngine baseline (not repair success)")
    print(f"MAE: {metrics['mae']}; RMSE: {metrics['rmse']}; R2: {metrics['r2']}")
    if args.metrics_only:
        return

    model_dir = ROOT / "models" / "priority"
    model_dir.mkdir(parents=True, exist_ok=True)
    existing = []
    for manifest in model_dir.glob("priority_model_v*.json"):
        try:
            existing.append(int(manifest.stem.removeprefix("priority_model_v")))
        except ValueError:
            pass
    version_num = max(existing, default=0) + 1
    version = f"priority_model_v{version_num}"
    artifact_name = f"{version}.joblib"
    from joblib import dump
    model = _pipeline()
    model.fit(X, y)
    dump(model, model_dir / artifact_name)
    metadata = {"model_version": version, "artifact": artifact_name,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "target_definition": "Current explainable PriorityEngine score, 0-100",
        "training_type": "baseline-derived prototype",
        "feature_builder_version": "priority_features_v1",
        "feature_names": list(FEATURE_NAMES), "metrics": metrics,
        "evaluation": "Leave-one-out CV; measures baseline reproduction, not real-world repair success",
        "training_sample_count": len(samples), "model_type": "RandomForestRegressor",
        "preprocessing": {"imputer": "SimpleImputer(strategy=median, keep_empty_features=True)",
                          "missing_value": "NaN", "feature_order": list(FEATURE_NAMES)},
        "limitations": ["No sufficient numeric repair-outcome labels are available.",
                        "Ward population is missing without road-to-ward mapping.",
                        "Accident features are district-level context."]}
    manifest_path = model_dir / f"{version}.json"
    manifest_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (model_dir / "current.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Model: {version} ({artifact_name})")
    print(f"Training type: {metadata['training_type']}")


if __name__ == "__main__":
    main()

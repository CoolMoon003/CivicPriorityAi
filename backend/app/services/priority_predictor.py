"""Optional inference for the baseline-derived priority model."""
import json
import logging
from pathlib import Path

from backend.app.scoring.priority_engine import PriorityEngine
from backend.app.services.priority_features import FEATURE_NAMES, build_for_complaint
from backend.ai.detection_policy import DEFAULT_POLICY, POSSIBLE

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[3]
MODEL_DIR = BASE_DIR / "models" / "priority"
MANIFEST_PATH = MODEL_DIR / "current.json"
_LOADED = None
_LOAD_ERROR = None


def _load_model():
    global _LOADED, _LOAD_ERROR
    if _LOADED is not None:
        return _LOADED, None
    if _LOAD_ERROR is not None:
        return None, _LOAD_ERROR
    try:
        with MANIFEST_PATH.open(encoding="utf-8") as stream:
            metadata = json.load(stream)
        if metadata.get("feature_names") != list(FEATURE_NAMES):
            raise ValueError("Model feature metadata does not match the current feature builder")
        artifact = MODEL_DIR / metadata["artifact"]
        import joblib
        _LOADED = (joblib.load(artifact), metadata)
        return _LOADED, None
    except Exception as exc:  # model/dependency failures must never block the baseline
        _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        logger.warning("AI priority prediction unavailable: %s", _LOAD_ERROR)
        return None, _LOAD_ERROR


def predict_values(feature_values, baseline_score):
    """Predict from the shared feature builder output; safe when optional ML is absent."""
    loaded, error = _load_model()
    if not loaded:
        return {"model_status": "unavailable", "predicted_priority_score": None,
                "baseline_priority_score": round(float(baseline_score), 1),
                "baseline_priority_level": PriorityEngine.level_for_score(float(baseline_score)),
                "difference": None, "explanation_status": "unavailable",
                "explanation": "AI prediction unavailable; rule-based baseline remains active.",
                "reason": error}
    model, metadata = loaded
    try:
        vector = [[feature_values.get(name) if feature_values.get(name) is not None else float("nan")
                   for name in FEATURE_NAMES]]
        score = float(model.predict(vector)[0])
        score = max(0.0, min(100.0, score))
        no_yolo_detection = (
            feature_values.get("damage_type_unknown") == 1.0
            and float(feature_values.get("damage_confidence") or 0.0) == 0.0
        )
        confidence = feature_values.get("damage_confidence")
        possible_detection = (
            not no_yolo_detection
            and DEFAULT_POLICY.state_for(confidence) == POSSIBLE
        )
        explanation = (
            "AI prediction is based on the available structured complaint, road and contextual features. "
            "No reliable YOLO damage detection was available for this complaint."
            if no_yolo_detection else
            "Possible YOLO damage evidence is uncertain and its rule-based damage contribution is confidence-discounted; contextual evidence is included."
            if possible_detection else
            "Per-complaint model contributions are unavailable. Rule-based evidence explanations are reported separately."
        )
        return {"model_status": "available", "predicted_priority_score": round(score, 1),
                "predicted_priority_level": PriorityEngine.level_for_score(score),
                "baseline_priority_score": round(float(baseline_score), 1),
                "baseline_priority_level": PriorityEngine.level_for_score(float(baseline_score)),
                "difference": round(score - float(baseline_score), 1),
                "model_version": metadata.get("model_version"),
                "training_type": metadata.get("training_type"),
                "explanation_status": "no_local_contribution",
                "explanation": explanation,
                "feature_values": feature_values}
    except Exception as exc:
        logger.exception("AI priority inference failed")
        return {"model_status": "unavailable", "predicted_priority_score": None,
                "baseline_priority_score": round(float(baseline_score), 1),
                "baseline_priority_level": PriorityEngine.level_for_score(float(baseline_score)),
                "difference": None, "explanation_status": "unavailable",
                "explanation": "AI prediction unavailable; rule-based baseline remains active.",
                "reason": f"{type(exc).__name__}: {exc}"}


def predict_complaint(complaint, db):
    values, context = build_for_complaint(complaint, db)
    return predict_values(values, context["baseline"].score)


def predict_new_complaint(damage_type, severity, confidence, road, recurrence, baseline_score,
                          recent_recurrence=0):
    from backend.app.services.priority_features import build_feature_values
    values = build_feature_values(damage_type, severity, confidence, road,
                                  recurrence=recurrence,
                                  recent_recurrence=recent_recurrence,
                                  baseline_score=baseline_score)
    return predict_values(values, baseline_score)

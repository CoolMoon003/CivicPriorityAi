from io import BytesIO
import hashlib
import logging
import math
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.ai.road_damage_detector import RoadDamageDetector
from backend.app.database.database import get_db
from backend.app.models.complaint import Complaint
from backend.app.models.user import User
from backend.app.scoring.priority_engine import PriorityEngine
from backend.app.services.duplicate_service import DuplicateService
from backend.app.services.annotated_image_service import (
    existing_annotated_path,
    render_annotated_image,
)
from backend.app.services.road_matcher import RoadMatcher
from backend.app.services.priority_predictor import predict_new_complaint
from backend.app.services.priority_features import recent_match_count
from backend.app.services.runtime_paths import (
    PROJECT_ROOT as BASE_DIR,
    UPLOAD_DIR,
    configured_project_path,
    resolve_stored_path,
    stored_path_key,
    upload_relative_path,
)


router = APIRouter(
    prefix="/complaints",
    tags=["Complaints"],
)
logger = logging.getLogger(__name__)


ROAD_GRAPH = (
    configured_project_path(
        "CIVIC_ROAD_GRAPHML",
        BASE_DIR / "data" / "vellore" / "vellore_drive_network.graphml",
    )
)

ROAD_FEATURES = (
    configured_project_path(
        "CIVIC_ROAD_FEATURES_GEOJSON",
        BASE_DIR / "data" / "processed" / "vellore_road_features.geojson",
    )
)


detector = RoadDamageDetector()

road_matcher = RoadMatcher(
    ROAD_GRAPH,
    ROAD_FEATURES,
)

priority_engine = PriorityEngine()

duplicate_service = DuplicateService()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
DUPLICATE_DISTANCE_METERS = float(__import__("os").getenv("DUPLICATE_DISTANCE_METERS", "5"))


@router.post("/")
async def create_complaint(
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: str = Form(""),
    image: UploadFile | None = File(None),
    user_id: int | None = Form(None),
    continue_as_separate: bool = Form(False),
    db: Session = Depends(get_db),
):
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise HTTPException(status_code=422, detail="Latitude must be a finite value between -90 and 90")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise HTTPException(status_code=422, detail="Longitude must be a finite value between -180 and 180")

    citizen = None
    if user_id is not None:
        citizen = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
        if citizen is None or (citizen.role or "").upper() != "CITIZEN":
            raise HTTPException(status_code=400, detail="Invalid citizen profile")
    # --------------------------------------------------
    # 1. Save uploaded image
    # --------------------------------------------------

    image_path = None
    image_sha256 = None
    content = None

    if image is not None:
        extension = Path(image.filename or "").suffix.lower()

        allowed_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image format",
            )

        content = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds the 10 MB upload limit")
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")
        try:
            from PIL import Image

            with Image.open(BytesIO(content)) as decoded:
                if decoded.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image encoding")
                if decoded.width * decoded.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=413, detail="Image dimensions exceed the supported limit")
                decoded.verify()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image: {exc}") from exc

        image_sha256 = hashlib.sha256(content).hexdigest()
        matches = db.query(Complaint).filter(Complaint.image_sha256 == image_sha256).order_by(Complaint.id).all()
        # Older records may not have a stored hash (for example when their image was unavailable at migration time).
        if not matches:
            for prior in db.query(Complaint).filter(Complaint.image_path.is_not(None)).all():
                if prior.image_sha256:
                    continue
                try:
                    prior_path = resolve_stored_path(prior.image_path, upload_dir=UPLOAD_DIR).resolve()
                    prior_path.relative_to(UPLOAD_DIR.resolve())
                    if prior_path.is_file() and hashlib.sha256(prior_path.read_bytes()).hexdigest() == image_sha256:
                        matches.append(prior)
                        prior.image_sha256 = image_sha256
                except (OSError, ValueError):
                    continue
        if matches:
            db.commit()
            existing = matches[0]
            raise HTTPException(status_code=409, detail={
                "type": "exact_image_duplicate", "existing_complaint_id": existing.id,
                "message": f"This image has already been reported as complaint #{existing.id}. No new complaint was created.",
            })

    if not continue_as_separate:
        active_statuses = ("OPEN", "ASSIGNED", "IN_PROGRESS")
        nearby = []
        for prior in db.query(Complaint).filter(Complaint.status.in_(active_statuses)).all():
            distance = duplicate_service.distance_m(latitude, longitude, prior.latitude, prior.longitude)
            if distance <= DUPLICATE_DISTANCE_METERS:
                nearby.append({"complaint_id": prior.id, "distance_m": round(distance, 2), "status": prior.status})
        if nearby:
            return JSONResponse(status_code=200, content={
                "requires_confirmation": True,
                "message": "There is already a report near this location. Is this the same issue?",
                "possible_duplicates": nearby,
            })

    if image is not None:
        # Original user filenames never enter the filesystem path.
        filename = f"{uuid4().hex}{extension}"
        destination = UPLOAD_DIR / filename
        destination.write_bytes(content)

        image_path = stored_path_key(destination, upload_dir=UPLOAD_DIR)

    # --------------------------------------------------
    # 2. AI damage analysis
    # --------------------------------------------------

    detection_error = None
    annotated_image_path = None
    annotation_error = None
    annotation_status = "no_image" if not image_path else "unavailable"
    if image_path:
        try:
            actual_image_path = resolve_stored_path(image_path, upload_dir=UPLOAD_DIR)
            detection = detector.predict(str(actual_image_path))
        except Exception as exc:
            logger.exception("Road-damage inference failed for complaint upload")
            detection_error = "Image analysis unavailable; manual verification is required."
            annotation_error = detection_error
            from backend.ai.road_damage_detector import DamageDetection

            detection = DamageDetection(
                damage_type="unknown", severity="unknown", confidence=0.0,
                description=detection_error,
            )
        else:
            if detection.detections:
                try:
                    annotated_path = render_annotated_image(actual_image_path, detection)
                    if annotated_path is None:
                        raise RuntimeError("Detector returned boxes but no annotation image was saved")
                    annotated_image_path = stored_path_key(annotated_path, upload_dir=UPLOAD_DIR)
                    annotation_status = "generated"
                except Exception:
                    logger.exception("Could not generate detector annotation image")
                    annotation_error = "AI detections are available, but the annotated image could not be generated."
                    annotation_status = "unavailable"
            else:
                annotation_status = "no_reliable_detection"
    else:
        # No image = no model prediction.
        # This keeps text/GPS-only complaints valid.
        from backend.ai.road_damage_detector import DamageDetection

        detection = DamageDetection(
            damage_type="unknown",
            severity="unknown",
            confidence=0.0,
            description="No image provided.",
        )

    # --------------------------------------------------
    # 3. GPS → nearest road
    # --------------------------------------------------

    road = road_matcher.match(
        latitude,
        longitude,
    )

    # --------------------------------------------------
    # 4. Find previous complaints for this location
    # --------------------------------------------------

    duplicates = duplicate_service.find_duplicates(
        db=db,
        latitude=latitude,
        longitude=longitude,
        road_u=road["u"],
        road_v=road["v"],
        road_key=road["key"],
    )

    recurrence_count = len(duplicates)

    # --------------------------------------------------
    # 5. Calculate priority
    # --------------------------------------------------

    priority_result = priority_engine.calculate(
        damage_type=detection.damage_type,
        severity=detection.severity,
        confidence=detection.confidence,
        road=road,
        repeat_reports=recurrence_count,
        detection_state=detection.detection_state,
    )
    ai_prediction = predict_new_complaint(
        detection.damage_type, detection.severity, detection.confidence,
        road, recurrence_count, priority_result.score,
        recent_recurrence=recent_match_count(duplicates),
    )

    # --------------------------------------------------
    # 6. Save complaint
    # --------------------------------------------------

    complaint = Complaint(
        user_id=citizen.id if citizen else None,
        image_path=image_path,
        image_sha256=image_sha256,
        description=description,
        latitude=latitude,
        longitude=longitude,

        road_u=road["u"],
        road_v=road["v"],
        road_key=road["key"],

        road_name=road.get("road_name"),
        road_type=road.get("highway"),

        damage_type=detection.damage_type,
        damage_severity=detection.severity,
        damage_confidence=detection.confidence,

        priority_score=priority_result.score,
        priority=priority_result.priority,
        recommended_action=(
            priority_result.recommended_action
        ),

        status="OPEN",
    )

    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # --------------------------------------------------
    # 7. Response
    # --------------------------------------------------

    return {
        "complaint_id": complaint.id,
        "image_path": complaint.image_path,
        "annotated_image_path": annotated_image_path,
        "annotated_image_url": (
            f"/uploads/{upload_relative_path(resolve_stored_path(annotated_image_path, upload_dir=UPLOAD_DIR), upload_dir=UPLOAD_DIR)}"
            if annotated_image_path else None
        ),
        "annotation_status": annotation_status,
        "annotation_error": annotation_error,

        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },

        "road": {
            "name": road.get("road_name"),
            "type": road.get("highway"),
            "distance_to_match_m": road.get(
                "distance_m"
            ),
        },

        "damage": {
            "type": detection.damage_type,
            "severity": detection.severity,
            "confidence": detection.confidence,
            "detection_state": detection.detection_state,
            "description": detection.description,
            "primary_detection": detection.primary_detection.as_dict() if detection.primary_detection else None,
            "all_relevant_detections": [item.as_dict() for item in detection.all_relevant_detections],
        },

        "detections": [item.as_dict() for item in detection.detections],
        "analysis_status": "unavailable" if detection_error else ("available" if image_path else "no_image"),
        "analysis_error": detection_error,
        "inference": {
            "image_sizes": list(detector.last_inference_sizes),
            "timing_ms": dict(detector.last_timing_ms),
            "confirmed_threshold": detector.confidence_threshold,
            "possible_threshold": detector.possible_threshold,
        },

        "recurrence": {
            "previous_reports": recurrence_count,
            "duplicate_complaints": duplicates,
        },

        "priority": {
            "score": priority_result.score,
            "level": priority_result.priority,
            "overall_score": priority_result.score,
            "priority_band": priority_result.priority,
            "factors": priority_result.factors,
            "components": priority_result.components,
            "damage_component": priority_result.components["damage"],
            "confidence_component": priority_result.components["confidence"],
            "road_component": priority_result.components["road_importance"],
            "facility_component": priority_result.components["facilities"],
            "recurrence_component": priority_result.components["recurrence"],
            "population_component": priority_result.components["population"],
            "district_safety_component": priority_result.components["district_safety"],
            "explanations": priority_result.explanations,
            "recommended_action": (
                priority_result.recommended_action
            ),
        },

        "ai_prediction": ai_prediction,

        "status": complaint.status,
    }

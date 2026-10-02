"""Save an annotation rendered from the detector's real bounding-box output."""
from __future__ import annotations

from pathlib import Path

from backend.ai.road_damage_detector import DamageDetection, Detection
from backend.ai.detection_policy import DEFAULT_POLICY, NO_RELIABLE_DETECTION


CLASS_COLORS = {
    "longitudinal_crack": (40, 190, 255),
    "transverse_crack": (190, 90, 255),
    "alligator_crack": (255, 175, 40),
    "pothole": (255, 70, 70),
}


def annotated_path_for(original_path: str | Path, output_root: str | Path | None = None) -> Path:
    """Return a stable sidecar path; never overwrite the original evidence."""
    original = Path(original_path)
    if output_root is None:
        # data/uploads/<asset> -> data/uploads/annotated/<asset>.annotated.jpg
        upload_root = original.parent
        if original.parent.name == "annotated":
            upload_root = original.parent.parent
        output_root = upload_root / "annotated"
    suffix = original.suffix.lower() if original.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
    return Path(output_root) / f"{original.stem}.annotated{suffix}"


def render_annotated_image(
    original_path: str | Path,
    detection: DamageDetection,
    output_root: str | Path | None = None,
) -> Path | None:
    """Render only detections already accepted by the confidence policy."""
    boxes = [box for box in detection.detections
             if DEFAULT_POLICY.state_for(box.confidence) != NO_RELIABLE_DETECTION]
    source = Path(original_path)
    if not boxes or not source.is_file():
        return None

    from PIL import Image, ImageDraw, ImageFont, ImageOps

    output = annotated_path_for(source, output_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    width, height = image.size
    stroke = max(2, round(min(width, height) / 350))
    drawn = 0

    for box in boxes:
        color = CLASS_COLORS.get(box.damage_type, (255, 230, 40))
        x1 = max(0, min(width - 1, round(box.x1)))
        y1 = max(0, min(height - 1, round(box.y1)))
        x2 = max(0, min(width - 1, round(box.x2)))
        y2 = max(0, min(height - 1, round(box.y2)))
        if x2 <= x1 or y2 <= y1:
            continue
        if box.detection_state == "possible":
            dash = max(8, stroke * 6)
            for offset in range(stroke):
                left, top, right, bottom = x1 + offset, y1 + offset, x2 - offset, y2 - offset
                for start in range(left, right, dash * 2):
                    end = min(start + dash, right)
                    draw.line((start, top, end, top), fill=color, width=stroke)
                    draw.line((start, bottom, end, bottom), fill=color, width=stroke)
                for start in range(top, bottom, dash * 2):
                    end = min(start + dash, bottom)
                    draw.line((left, start, left, end), fill=color, width=stroke)
                    draw.line((right, start, right, end), fill=color, width=stroke)
        else:
            for offset in range(stroke):
                draw.rectangle((x1 + offset, y1 + offset, x2 - offset, y2 - offset), outline=color)
        drawn += 1
        state = "POSSIBLE · AI UNCERTAIN" if box.detection_state == "possible" else "CONFIRMED"
        label = f"{state} | {box.class_name} | {box.confidence:.1%}"
        text_box = draw.textbbox((0, 0), label, font=font)
        label_w, label_h = text_box[2] - text_box[0], text_box[3] - text_box[1]
        label_y = max(0, y1 - label_h - 8)
        draw.rectangle((x1, label_y, min(width - 1, x1 + label_w + 8), label_y + label_h + 6), fill=color)
        draw.text((x1 + 4, label_y + 3), label, fill=(10, 10, 10), font=font)

    if not drawn:
        return None
    if not output.suffix:
        output = output.with_suffix(".jpg")
    image.save(output, quality=92)
    return output


def project_relative_path(path: Path, project_root: Path) -> str:
    return str(path.resolve().relative_to(project_root.resolve()))


def existing_annotated_path(image_path: str | None, project_root: Path) -> str | None:
    if not image_path:
        return None
    original = Path(image_path)
    if not original.is_absolute():
        original = project_root / original
    candidate = annotated_path_for(original)
    try:
        return project_relative_path(candidate, project_root) if candidate.is_file() else None
    except ValueError:
        return None

"""Authorization and conservative file cleanup for admin complaint deletion."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
import re

from backend.app.services.annotated_image_service import annotated_path_for
from backend.app.services.runtime_paths import resolve_stored_path, upload_dir_for


_OWNED_UPLOAD_NAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)


def valid_admin_delete_token(configured: str | None, supplied: str | None) -> bool:
    return bool(configured and supplied and hmac.compare_digest(configured, supplied))


def safe_complaint_uploads_to_remove(
    image_path: str | None,
    project_root: Path,
    shared_reference: bool = False,
) -> list[Path]:
    """Only return UUID-named direct user uploads and their generated sidecars.

    Demo assets, dataset assets, arbitrary paths, symlinks outside uploads, and
    uploads referenced by another complaint are intentionally retained.
    """
    if not image_path or shared_reference:
        return []
    root = upload_dir_for(project_root).resolve()
    candidate = resolve_stored_path(image_path, project_root)
    try:
        resolved = candidate.resolve()
        if resolved.parent != root or not _OWNED_UPLOAD_NAME.fullmatch(resolved.name):
            return []
        sidecar = annotated_path_for(resolved)
        sidecar_resolved = sidecar.resolve()
        if sidecar_resolved.parent != (root / "annotated").resolve():
            return []
    except (OSError, ValueError):
        return []
    return [resolved, sidecar_resolved]

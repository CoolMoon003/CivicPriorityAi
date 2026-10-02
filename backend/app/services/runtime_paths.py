"""Runtime filesystem locations with repository-relative local defaults."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def data_dir_for(project_root: Path = PROJECT_ROOT) -> Path:
    configured = os.getenv("CIVIC_DATA_DIR") if project_root.resolve() == PROJECT_ROOT.resolve() else None
    if configured:
        directory = Path(configured).expanduser()
        if not directory.is_absolute():
            directory = project_root / directory
    else:
        directory = project_root / "data"
    return directory.resolve()


DATA_DIR = data_dir_for()
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def upload_dir_for(project_root: Path = PROJECT_ROOT) -> Path:
    return data_dir_for(project_root) / "uploads"


def configured_project_path(name: str, default: Path) -> Path:
    configured = os.getenv(name)
    path = Path(configured).expanduser() if configured else default
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def resolve_stored_path(
    path: str | Path,
    project_root: Path = PROJECT_ROOT,
    upload_dir: Path | None = None,
) -> Path:
    """Resolve legacy project-relative image keys through the configured data dir."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    normalized = candidate.as_posix().lstrip("/")
    for prefix in ("data/uploads/", "uploads/"):
        if normalized.startswith(prefix):
            return (upload_dir or upload_dir_for(project_root)) / normalized[len(prefix):]
    return project_root / candidate


def stored_path_key(
    path: str | Path,
    project_root: Path = PROJECT_ROOT,
    upload_dir: Path | None = None,
) -> str:
    """Return a stable legacy-compatible key for an image inside upload storage."""
    resolved = Path(path).resolve()
    upload_root = (upload_dir or upload_dir_for(project_root)).resolve()
    try:
        relative = resolved.relative_to(upload_root)
    except ValueError:
        return resolved.relative_to(project_root.resolve()).as_posix()
    return (Path("data") / "uploads" / relative).as_posix()


def upload_relative_path(
    path: str | Path,
    project_root: Path = PROJECT_ROOT,
    upload_dir: Path | None = None,
) -> str:
    """Return a URL-safe relative path for a file under the mounted uploads dir."""
    resolved = Path(path).resolve()
    upload_root = (upload_dir or upload_dir_for(project_root)).resolve()
    return resolved.relative_to(upload_root).as_posix()

from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.app.api.admin import router as admin_router
from backend.app.database.database import init_db
from backend.app.api.complaints import router as complaints_router
from backend.app.api.technician import router as technician_router
from backend.app.api.outcomes import router as outcomes_router
from backend.app.api.citizen import router as citizen_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CivicPriorityAI",
    description="AI-powered civic road-priority system for Vellore",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve citizen-uploaded complaint images (already saved by
# backend/app/api/complaints.py to <project_root>/data/uploads) so the
# admin dashboard can display them. This does not change where or how
# images are stored — it only exposes the existing directory over HTTP.
_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=_UPLOAD_DIR),
    name="uploads",
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(
    complaints_router,
)
app.include_router(
    admin_router,
)
app.include_router(
    technician_router,
)
app.include_router(
    outcomes_router,
)
app.include_router(
    citizen_router,
)


@app.get("/")
def root():
    return {
        "name": "CivicPriorityAI",
        "status": "running",
    }

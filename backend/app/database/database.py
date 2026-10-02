from sqlalchemy import create_engine, inspect, text
import hashlib
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.services.runtime_paths import DATA_DIR, PROJECT_ROOT, resolve_stored_path

BASE_DIR = PROJECT_ROOT

DATABASE_URL = f"sqlite:///{DATA_DIR / 'civic_priority.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.app.models.complaint import Complaint

    Base.metadata.create_all(bind=engine)
    # SQLite create_all does not add columns to an existing database.
    columns = {column["name"] for column in inspect(engine).get_columns("complaints")}
    with engine.begin() as connection:
        if "image_sha256" not in columns:
            connection.execute(text("ALTER TABLE complaints ADD COLUMN image_sha256 VARCHAR(64)"))
        if "duplicate_of_id" not in columns:
            connection.execute(text("ALTER TABLE complaints ADD COLUMN duplicate_of_id INTEGER"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_complaints_image_sha256 ON complaints (image_sha256)"))
    with SessionLocal() as session:
        for complaint in session.query(Complaint).filter(
            Complaint.image_path.is_not(None), Complaint.image_sha256.is_(None)
        ).yield_per(100):
            path = resolve_stored_path(complaint.image_path).resolve()
            try:
                path.relative_to(DATA_DIR.resolve())
                if path.is_file():
                    complaint.image_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, ValueError):
                continue
        session.commit()

"""Database session and engine setup."""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False, "timeout": 30} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


def get_db() -> Session:
    """Yield a database session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all database tables."""
    import app.db.models  # noqa: F401
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(documents);")).fetchall()
                doc_cols = {row[1] for row in res}
                if "warnings" not in doc_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN warnings TEXT;"))
                if "doc_avg_top_prob" not in doc_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN doc_avg_top_prob FLOAT;"))
                if "doc_sbert_dist" not in doc_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN doc_sbert_dist FLOAT;"))
                res_c = conn.execute(text("PRAGMA table_info(clauses);")).fetchall()
                clause_cols = {row[1] for row in res_c}
                if "type_uncertain" not in clause_cols:
                    conn.execute(text("ALTER TABLE clauses ADD COLUMN type_uncertain BOOLEAN DEFAULT 0;"))
                conn.commit()
        except Exception as e:
            logger.warning("Could not auto-migrate SQLite tables: %s", e)
    logger.info("Database tables created.")


"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import create_tables
from app.logging_config import setup_logging
from app.services.classifier import classifier
from app.services.embedder import embedder

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: load models on startup."""
    setup_logging()
    logger.info("Starting ClauseWise backend...")
    
    # Create database tables
    create_tables()
    
    # Load ML models
    try:
        classifier.load(
            backend=settings.classifier_backend,
            model_path=settings.model_path,
            label_map_path=settings.label_map_path,
            baseline_model_path=settings.baseline_model_path,
        )
        logger.info("Classifier model loaded (%s backend).", settings.classifier_backend)
    except Exception as e:
        logger.error("Failed to load classifier: %s", e)
    
    try:
        embedder.load(model_name=settings.sbert_model)
        logger.info("Embedder model loaded.")
    except Exception as e:
        logger.error("Failed to load embedder: %s", e)
    
    logger.info("ClauseWise backend ready.")
    yield
    logger.info("Shutting down ClauseWise backend.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ClauseWise API",
        description="AI-powered contract risk analyzer. Not legal advice.",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    register_exception_handlers(app)
    
    # Routers
    from app.routers import analyze, health, history, insights, redline, search
    
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(analyze.router, prefix="/api/v1", tags=["Analysis"])
    app.include_router(search.router, prefix="/api/v1", tags=["Search"])
    app.include_router(redline.router, prefix="/api/v1", tags=["Redline"])
    app.include_router(history.router, prefix="/api/v1", tags=["History"])
    app.include_router(insights.router, prefix="/api/v1", tags=["Insights"])
    
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    artifacts_path = Path(settings.metrics_path).parent
    if artifacts_path.exists():
        app.mount("/api/v1/static", StaticFiles(directory=str(artifacts_path)), name="static")
    
    return app


app = create_app()

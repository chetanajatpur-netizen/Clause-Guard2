"""Health check endpoint."""
from fastapi import APIRouter

from app.services.classifier import classifier
from app.services.embedder import embedder

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Liveness and readiness check."""
    return {
        "status": "ok",
        "classifier_loaded": classifier.is_loaded,
        "embedder_loaded": embedder.is_loaded,
    }

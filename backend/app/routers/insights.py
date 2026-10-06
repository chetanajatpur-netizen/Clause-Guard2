"""Model insights endpoint."""
import json
import logging
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.schemas.insights import InsightsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/insights", response_model=InsightsResponse)
async def get_insights() -> InsightsResponse:
    """Return model metrics from metrics.json."""
    metrics_path = Path(settings.metrics_path)
    
    if not metrics_path.exists():
        logger.warning("Metrics file not found: %s", metrics_path)
        return InsightsResponse(metrics={})
    
    with open(metrics_path) as f:
        metrics = json.load(f)
    
    return InsightsResponse(metrics=metrics)

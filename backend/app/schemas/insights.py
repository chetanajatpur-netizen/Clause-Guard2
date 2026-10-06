"""Schemas for model insights."""
from typing import Any
from pydantic import BaseModel


class InsightsResponse(BaseModel):
    """Model metrics and insights."""
    metrics: dict[str, Any]

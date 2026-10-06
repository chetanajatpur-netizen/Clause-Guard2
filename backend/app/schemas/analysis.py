"""Schemas for contract analysis."""
from pydantic import BaseModel


class ClauseResponse(BaseModel):
    """Single clause analysis result."""
    id: int
    position: int
    text: str
    label: str
    confidence: float
    risk_level: str | None


class RiskSummary(BaseModel):
    """Overall risk summary for a document."""
    overall_risk: str
    high_count: int
    medium_count: int
    low_count: int
    none_count: int
    total_clauses: int


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    document_id: str
    filename: str
    char_count: int
    risk_summary: RiskSummary
    clauses: list[ClauseResponse]

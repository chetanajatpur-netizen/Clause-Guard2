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
    flagged: bool = False
    risk_tier: str | None = None
    calibrated_probability: float | None = None
    char_start: int | None = None
    char_end: int | None = None
    type_uncertain: bool = False
    # Enhanced risk scoring fields (optional for backward compatibility)
    risk_score: int | None = None
    risk_score_normalized: float | None = None
    uncertainty: float | None = None
    uncertainty_level: str | None = None


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
    warnings: list[str] = []
    doc_avg_top_prob: float | None = None
    doc_sbert_dist: float | None = None

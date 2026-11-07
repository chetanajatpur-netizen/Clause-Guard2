"""Schemas for document history."""
from datetime import datetime
from pydantic import BaseModel
from app.schemas.analysis import ClauseResponse, RiskSummary


class DocumentListItem(BaseModel):
    """Document summary for list view."""
    id: str
    filename: str
    file_type: str
    char_count: int
    overall_risk: str | None
    created_at: datetime


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: list[DocumentListItem]
    total: int


class DocumentDetailResponse(BaseModel):
    """Full document with clauses."""
    id: str
    filename: str
    file_type: str
    char_count: int
    overall_risk: str | None
    created_at: datetime
    risk_summary: RiskSummary
    clauses: list[ClauseResponse]
    warnings: list[str] = []
    doc_avg_top_prob: float | None = None
    doc_sbert_dist: float | None = None

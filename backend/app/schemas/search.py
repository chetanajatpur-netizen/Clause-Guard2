"""Schemas for semantic search."""
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Semantic search request."""
    document_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResultItem(BaseModel):
    """Single search result."""
    clause_id: int
    position: int
    text: str
    label: str
    risk_level: str | None
    similarity: float


class SearchResponse(BaseModel):
    """Search results."""
    query: str
    document_id: str
    results: list[SearchResultItem]

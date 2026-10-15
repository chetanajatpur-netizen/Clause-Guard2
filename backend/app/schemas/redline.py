"""Schemas for redline generation."""
from typing import List, Optional
from pydantic import BaseModel, Field


class DiffSegment(BaseModel):
    """Word-level diff segment."""
    type: str = Field(description="Diff type: 'equal', 'delete', or 'insert'")
    text: str = Field(description="Text chunk")


class RedlineRequest(BaseModel):
    """Request to generate safer redline wording for a clause."""
    clause_text: str = Field(min_length=1, description="Raw clause text")
    clause_label: str = Field(min_length=1, description="Clause type label")


class RedlineResponse(BaseModel):
    """Safer redline response with word diff."""
    diff_segments: List[DiffSegment]
    replacement: str
    rationale: str
    verify_status: str

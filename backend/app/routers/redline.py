"""Redline generation endpoint."""
import logging
from typing import Optional

from fastapi import APIRouter
from app.core.exceptions import ClauseGuardError
from app.schemas.redline import RedlineRequest, RedlineResponse
from app.redline.engine import suggest_redline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/redline", response_model=Optional[RedlineResponse])
async def get_clause_redline(request: RedlineRequest) -> Optional[RedlineResponse]:
    """Generate safer redline wording and word diff for a contract clause."""
    if not request.clause_text or not request.clause_text.strip():
        raise ClauseGuardError(
            code="INVALID_INPUT",
            message="clause_text cannot be empty",
            status_code=400,
        )
    if not request.clause_label or not request.clause_label.strip():
        raise ClauseGuardError(
            code="INVALID_INPUT",
            message="clause_label cannot be empty",
            status_code=400,
        )

    result = suggest_redline(request.clause_label, request.clause_text)
    if result is None:
        return None

    return RedlineResponse(
        diff_segments=result["diff_segments"],
        replacement=result["replacement"],
        rationale=result["rationale"],
        verify_status=result["verify_status"],
    )

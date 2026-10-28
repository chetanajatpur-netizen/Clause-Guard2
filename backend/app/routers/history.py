"""Document history endpoints."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import DocumentNotFoundError
from app.db.models import Clause, Document
from app.db.session import get_db
from app.schemas.analysis import ClauseResponse, RiskSummary
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
)
from app.services.risk import compute_document_risk, compute_enhanced_clause_risk

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List all analyzed documents."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    
    items = [
        DocumentListItem(
            id=str(doc.id),
            filename=doc.filename,
            file_type=doc.file_type,
            char_count=doc.char_count,
            overall_risk=doc.overall_risk,
            created_at=doc.created_at,
        )
        for doc in docs
    ]
    
    return DocumentListResponse(documents=items, total=len(items))


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    """Get a specific document with all clauses."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise DocumentNotFoundError(document_id)
    
    clauses = (
        db.query(Clause)
        .filter(Clause.document_id == document_id)
        .order_by(Clause.position)
        .all()
    )
    
    # Risk summary computed from persisted clause flagged states and tiers
    high_count = sum(1 for c in clauses if c.flagged and (c.risk_tier == "High" or c.risk_level == "High"))
    medium_count = sum(1 for c in clauses if c.flagged and (c.risk_tier == "Medium" or c.risk_level == "Medium"))
    low_count = sum(1 for c in clauses if c.flagged and (c.risk_tier == "Low" or c.risk_level == "Low"))
    none_count = sum(1 for c in clauses if not c.flagged)

    if high_count > 0:
        overall_doc_risk = "High"
    elif medium_count > 0:
        overall_doc_risk = "Medium"
    else:
        overall_doc_risk = "Low"

    risk_data = {
        "overall_risk": doc.overall_risk or overall_doc_risk,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "none_count": none_count,
        "total_clauses": len(clauses),
    }

    clause_responses = []
    for c in clauses:
        enhanced = compute_enhanced_clause_risk(
            label=c.label,
            confidence=c.confidence,
            clause_text=c.text,
        )
        clause_responses.append(
            ClauseResponse(
                id=c.id,
                position=c.position,
                text=c.text,
                label=c.label,
                confidence=c.confidence,
                risk_level=c.risk_level or enhanced["risk_level"],
                flagged=bool(c.flagged),
                risk_tier=c.risk_tier or ("None" if not c.flagged else (c.risk_level or "Low")),
                calibrated_probability=c.calibrated_probability if c.calibrated_probability is not None else c.confidence,
                char_start=c.char_start,
                char_end=c.char_end,
                risk_score=enhanced["risk_score"],
                risk_score_normalized=enhanced["risk_score_normalized"],
                uncertainty=enhanced["uncertainty"],
                uncertainty_level=enhanced["uncertainty_level"],
            )
        )
    
    return DocumentDetailResponse(
        id=str(doc.id),
        filename=doc.filename,
        file_type=doc.file_type,
        char_count=doc.char_count,
        overall_risk=doc.overall_risk,
        created_at=doc.created_at,
        risk_summary=RiskSummary(**risk_data),
        clauses=clause_responses,
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a document and all its clauses."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise DocumentNotFoundError(document_id)
    
    db.delete(doc)
    db.commit()
    
    logger.info("Deleted document %s", document_id)
    return {"status": "deleted", "document_id": document_id}

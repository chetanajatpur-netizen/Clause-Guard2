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
from app.services.risk import compute_document_risk

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
    
    labels = [c.label for c in clauses]
    risk_data = compute_document_risk(labels) if labels else {
        "overall_risk": "Low", "high_count": 0, "medium_count": 0,
        "low_count": 0, "none_count": 0, "total_clauses": 0,
    }
    
    clause_responses = [
        ClauseResponse(
            id=c.id,
            position=c.position,
            text=c.text,
            label=c.label,
            confidence=c.confidence,
            risk_level=c.risk_level,
        )
        for c in clauses
    ]
    
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

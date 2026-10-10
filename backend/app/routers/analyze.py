"""Contract analysis endpoint."""
import logging
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import (
    FileTooLargeError,
    ModelNotLoadedError,
    NoTextExtractedError,
    UnsupportedFileTypeError,
)
from app.db.models import Clause, Document
from app.db.session import get_db
from app.schemas.analysis import AnalysisResponse, ClauseResponse, RiskSummary
from app.services.classifier import classifier
from app.services.embedder import embedder
from app.services.parser import extract_text
from app.services.risk import compute_clause_risk, compute_document_risk, compute_enhanced_clause_risk
from app.services.segmenter import segment_text

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """Upload and analyze a contract file."""
    if not classifier.is_loaded or not embedder.is_loaded:
        raise ModelNotLoadedError()
    
    # Validate file extension
    filename = file.filename or "unknown"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(suffix)
    
    # Read and validate size
    file_bytes = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(settings.max_file_size_mb)
    
    # Extract text
    try:
        text = extract_text(file_bytes, filename)
    except ValueError as e:
        raise NoTextExtractedError() from e
    
    if not text.strip():
        raise NoTextExtractedError()
    
    logger.info("Analyzing '%s' (%d chars)", filename, len(text))
    
    # Segment
    chunks = segment_text(text)
    if not chunks:
        raise NoTextExtractedError()
    
    # Classify
    predictions = classifier.predict(chunks)
    
    # Compute risk
    labels = [p["label"] for p in predictions]
    risk_summary_data = compute_document_risk(labels)
    
    # Generate embeddings
    embeddings = embedder.encode(chunks)
    
    # Save to database
    doc = Document(
        filename=filename,
        file_type=suffix.lstrip("."),
        char_count=len(text),
        overall_risk=risk_summary_data["overall_risk"],
    )
    db.add(doc)
    db.flush()

    clause_responses: list[ClauseResponse] = []
    for i, (chunk, pred) in enumerate(zip(chunks, predictions)):
        # Compute enhanced risk score
        enhanced_risk = compute_enhanced_clause_risk(
            label=pred["label"],
            confidence=pred["confidence"],
            clause_text=chunk
        )
        risk = enhanced_risk["risk_level"]
        emb_bytes = embeddings[i].tobytes()

        clause = Clause(
            document_id=doc.id,
            position=i,
            text=chunk,
            label=pred["label"],
            confidence=pred["confidence"],
            risk_level=risk,
            embedding=emb_bytes,
        )
        db.add(clause)
        db.flush()

        clause_responses.append(ClauseResponse(
            id=clause.id,
            position=i,
            text=chunk,
            label=pred["label"],
            confidence=pred["confidence"],
            risk_level=risk,
            risk_score=enhanced_risk["risk_score"],
            risk_score_normalized=enhanced_risk["risk_score_normalized"],
            uncertainty=enhanced_risk["uncertainty"],
            uncertainty_level=enhanced_risk["uncertainty_level"],
        ))
    
    db.commit()
    logger.info("Analysis saved: doc_id=%s, %d clauses", doc.id, len(chunks))
    
    return AnalysisResponse(
        document_id=str(doc.id),
        filename=filename,
        char_count=len(text),
        risk_summary=RiskSummary(**risk_summary_data),
        clauses=clause_responses,
    )

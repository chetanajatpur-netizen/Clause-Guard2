"""Contract analysis endpoint."""
import json
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Query, UploadFile
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
from app.services.risk import compute_document_risk, compute_enhanced_clause_risk
from app.services.segmenter import resegment_contract, segment_text

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    sensitivity: str = Query("balanced", description="Sensitivity preset: strict (3 FA/c), balanced (8 FA/c), thorough (12 FA/c)"),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """Upload and analyze a contract file using calibrated operating point thresholding."""
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
    
    logger.info("Analyzing '%s' (%d chars, sensitivity=%s)", filename, len(text), sensitivity)
    
    # Slice-based resegmentation guaranteeing exact context offsets
    units = resegment_contract(text)
    if not units:
        fallback_chunks = segment_text(text)
        if not fallback_chunks:
            raise NoTextExtractedError()
        units = [{"text": c, "text_raw": c, "char_start": None, "char_end": None} for c in fallback_chunks]

    chunk_texts = [u["text"] for u in units]
    
    # Classify with chosen operating point preset
    predictions = classifier.predict(chunk_texts, sensitivity=sensitivity)
    
    # Risk calculation based on flagged clauses
    flagged_tiers = [p.get("risk_tier", "None") for p in predictions if p.get("flagged", p.get("label", "No Clause") != "No Clause")]
    if any(t == "High" for t in flagged_tiers):
        overall_doc_risk = "High"
    elif any(t == "Medium" for t in flagged_tiers):
        overall_doc_risk = "Medium"
    else:
        overall_doc_risk = "Low"

    high_count = sum(1 for p in predictions if p.get("flagged", p.get("label", "No Clause") != "No Clause") and p.get("risk_tier") == "High")
    medium_count = sum(1 for p in predictions if p.get("flagged", p.get("label", "No Clause") != "No Clause") and p.get("risk_tier") == "Medium")
    low_count = sum(1 for p in predictions if p.get("flagged", p.get("label", "No Clause") != "No Clause") and p.get("risk_tier") == "Low")
    none_count = sum(1 for p in predictions if not p.get("flagged", p.get("label", "No Clause") != "No Clause"))

    risk_summary_data = {
        "overall_risk": overall_doc_risk,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "none_count": none_count,
        "total_clauses": len(units),
    }
    
    # Generate embeddings and compute document-level domain metrics
    embeddings = embedder.encode(chunk_texts)
    doc_sbert_dist = round(embedder.compute_document_distance(embeddings), 4)

    # Average top-class calibrated probability across clauses
    top_probs = [float(p.get("calibrated_probability", p.get("confidence", 0.0))) for p in predictions]
    doc_avg_top_prob = round(float(np.mean(top_probs)), 4) if top_probs else 1.0

    # Document-level warning condition:
    # Average top-class probability below 0.70 OR SBERT distance exceeds 0.3757
    doc_warnings: list[str] = []
    if doc_avg_top_prob < 0.70 or doc_sbert_dist > 0.3757:
        doc_warnings.append(
            "This document looks unlike the contracts the model was trained on. Treat the results with extra caution."
        )

    # Save to database
    doc = Document(
        filename=filename,
        file_type=suffix.lstrip("."),
        char_count=len(text),
        overall_risk=overall_doc_risk,
        warnings=json.dumps(doc_warnings) if doc_warnings else None,
        doc_avg_top_prob=doc_avg_top_prob,
        doc_sbert_dist=doc_sbert_dist,
    )
    db.add(doc)
    db.flush()

    clause_responses: list[ClauseResponse] = []
    for i, (unit, pred) in enumerate(zip(units, predictions)):
        chunk_text = unit["text"]
        pred_label = pred.get("label", "No Clause")
        cal_prob = float(pred.get("calibrated_probability", pred.get("confidence", 0.0)))
        flagged = bool(pred.get("flagged", pred_label != "No Clause"))
        risk_tier = pred.get("risk_tier", "None")
        risk = risk_tier if risk_tier != "None" else None
        type_uncertain = bool(pred.get("type_uncertain", (flagged and cal_prob < 0.65)))

        enhanced_risk = compute_enhanced_clause_risk(
            label=pred_label,
            confidence=cal_prob,
            clause_text=chunk_text,
        )
        emb_bytes = embeddings[i].tobytes()

        clause = Clause(
            document_id=doc.id,
            position=i,
            text=chunk_text,
            label=pred_label,
            confidence=cal_prob,
            risk_level=risk,
            flagged=flagged,
            calibrated_probability=cal_prob,
            risk_tier=risk_tier,
            char_start=unit.get("char_start"),
            char_end=unit.get("char_end"),
            type_uncertain=type_uncertain,
            embedding=emb_bytes,
        )
        db.add(clause)
        db.flush()

        clause_responses.append(ClauseResponse(
            id=clause.id,
            position=i,
            text=chunk_text,
            label=pred_label,
            confidence=cal_prob,
            risk_level=risk,
            flagged=flagged,
            risk_tier=risk_tier,
            calibrated_probability=cal_prob,
            char_start=unit.get("char_start"),
            char_end=unit.get("char_end"),
            type_uncertain=type_uncertain,
            risk_score=enhanced_risk["risk_score"],
            risk_score_normalized=enhanced_risk["risk_score_normalized"],
            uncertainty=enhanced_risk["uncertainty"],
            uncertainty_level=enhanced_risk["uncertainty_level"],
        ))
    
    db.commit()
    logger.info("Analysis saved: doc_id=%s, %d clauses (%d flagged, %d uncertain)", doc.id, len(units), len(flagged_tiers), sum(1 for c in clause_responses if c.type_uncertain))
    
    return AnalysisResponse(
        document_id=str(doc.id),
        filename=filename,
        char_count=len(text),
        risk_summary=RiskSummary(**risk_summary_data),
        clauses=clause_responses,
        warnings=doc_warnings,
        doc_avg_top_prob=doc_avg_top_prob,
        doc_sbert_dist=doc_sbert_dist,
    )

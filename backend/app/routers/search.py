"""Semantic search endpoint."""
import logging

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import DocumentNotFoundError, ModelNotLoadedError
from app.db.models import Clause, Document, SearchQuery
from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.embedder import embedder
from app.services.risk import compute_enhanced_clause_risk

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Search within a document using natural language."""
    if not embedder.is_loaded:
        raise ModelNotLoadedError()
    
    # Verify document exists
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise DocumentNotFoundError(request.document_id)
    
    # Get clauses with embeddings
    clauses = (
        db.query(Clause)
        .filter(Clause.document_id == request.document_id)
        .order_by(Clause.position)
        .all()
    )
    
    if not clauses:
        return SearchResponse(
            query=request.query,
            document_id=request.document_id,
            results=[],
        )
    
    # Reconstruct embeddings
    clause_texts = [c.text for c in clauses]
    clause_embeddings = np.array([
        np.frombuffer(c.embedding, dtype=np.float32) for c in clauses
    ])
    
    # Search
    search_results = embedder.search(
        query=request.query,
        clause_texts=clause_texts,
        clause_embeddings=clause_embeddings,
        top_k=request.top_k,
    )
    
    # Build response
    results = []
    top_clause_id = None
    for sr in search_results:
        idx = sr["index"]
        clause = clauses[idx]
        if top_clause_id is None:
            top_clause_id = clause.id
        enhanced = compute_enhanced_clause_risk(
            label=clause.label,
            confidence=clause.confidence,
            clause_text=clause.text,
        )
        results.append(SearchResultItem(
            clause_id=clause.id,
            position=clause.position,
            text=clause.text,
            label=clause.label,
            risk_level=clause.risk_level or enhanced["risk_level"],
            similarity=sr["similarity"],
            risk_score=enhanced["risk_score"],
            risk_score_normalized=enhanced["risk_score_normalized"],
            uncertainty=enhanced["uncertainty"],
            uncertainty_level=enhanced["uncertainty_level"],
        ))
    
    # Log search query
    sq = SearchQuery(
        document_id=request.document_id,
        query=request.query,
        top_result_clause_id=top_clause_id,
    )
    db.add(sq)
    db.commit()
    
    logger.info("Search for '%s' in doc %s: %d results", request.query[:50], request.document_id, len(results))
    
    return SearchResponse(
        query=request.query,
        document_id=request.document_id,
        results=results,
    )

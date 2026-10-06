"""Risk level computation for clauses."""
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Import risk map from ML module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "ml" / "src"))
from risk_map import RISK_MAP, get_overall_risk, get_risk_level


def compute_clause_risk(label: str) -> Optional[str]:
    """Get risk level for a single clause label.
    
    Args:
        label: Clause type label from classifier.
    
    Returns:
        'High', 'Medium', 'Low', or None for 'No Clause'.
    """
    return get_risk_level(label)


def compute_document_risk(clause_labels: list[str]) -> dict:
    """Compute overall document risk summary.
    
    Args:
        clause_labels: List of clause type labels.
    
    Returns:
        Dict with overall_risk and counts per risk level.
    """
    risks = [get_risk_level(label) for label in clause_labels]
    overall = get_overall_risk(risks)
    
    high = sum(1 for r in risks if r == "High")
    medium = sum(1 for r in risks if r == "Medium")
    low = sum(1 for r in risks if r == "Low")
    none_count = sum(1 for r in risks if r is None)
    
    summary = {
        "overall_risk": overall,
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
        "none_count": none_count,
        "total_clauses": len(clause_labels),
    }
    
    logger.info(
        "Document risk: %s (H=%d, M=%d, L=%d, None=%d)",
        overall, high, medium, low, none_count,
    )
    return summary

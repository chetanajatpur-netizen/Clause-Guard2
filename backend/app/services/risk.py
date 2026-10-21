"""Risk level computation for clauses."""
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import math
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from app.core.risk_map import get_overall_risk, get_risk_level
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "ml" / "src"))
    from risk_map import get_overall_risk, get_risk_level


def compute_clause_risk(label: str) -> Optional[str]:
    """Get risk level for a single clause label.

    Args:
        label: Clause type label from classifier.

    Returns:
        'High', 'Medium', 'Low', or None for 'No Clause'.
    """
    return get_risk_level(label)


@lru_cache(maxsize=1024)
def _compute_enhanced_clause_risk_cached(label: str, confidence: float, clause_text: str) -> Dict[str, Any]:
    """Cached version of enhanced risk score computation.

    Args:
        label: Clause type label from classifier.
        confidence: Classification confidence score (0-1).
        clause_text: The actual clause text for linguistic analysis.

    Returns:
        Dict with risk_level, risk_score, uncertainty, and components.
    """
    # Base risk weights for each category (0.0 to 1.0 scale)
    base_risk_weights = {
        "Non-Compete": 0.9,
        "Exclusivity": 0.85,
        "Uncapped Liability": 0.95,
        "Liquidated Damages": 0.8,
        "Termination for Convenience": 0.6,
        "Anti-Assignment": 0.6,
        "Change of Control": 0.65,
        "IP Ownership Assignment": 0.7,
        "Cap on Liability": 0.3,
        "Audit Rights": 0.4,
        "No Clause": 0.0,
    }

    # Get base risk weight
    base_weight = base_risk_weights.get(label, 0.5)

    # Apply confidence weighting
    confidence_weighted = base_weight * confidence

    # Linguistic risk factors (simple heuristics based on clause text)
    linguistic_risk = 0.0
    if clause_text:
        text_lower = clause_text.lower()
        words = text_lower.split()
        word_count = len(words)

        # Amplifiers that increase risk
        risk_amplifiers = [
            'unlimited', 'unconditionally', 'irreversible', 'perpetual',
            'waive', 'forfeit', 'indemnify', 'hold harmless', 'liquidated damages',
            'consequential damages', 'punitive', 'sole discretion', 'shall',
            'must', 'will not', 'prohibited', 'forbidden'
        ]

        # Reducers that decrease risk
        risk_reducers = [
            'reasonable', 'mutual', 'both parties', 'negotiable',
            'subject to', 'provided that', 'unless', 'except',
            'cap', 'limitation', 'maximum', 'not to exceed',
            'may', 'can', 'could', 'should'
        ]

        amplifier_count = sum(1 for amp in risk_amplifiers if amp in text_lower)
        reducer_count = sum(1 for red in risk_reducers if red in text_lower)

        # Calculate linguistic factor with length normalization
        # Prevents very short or very long texts from having disproportionate influence
        length_factor = min(1.0, math.log(max(1, word_count)) / math.log(20))  # Normalize around 20 words
        if amplifier_count > 0 or reducer_count > 0:
            linguistic_factor = (amplifier_count * 0.04) - (reducer_count * 0.025)
            linguistic_risk = max(-0.15, min(0.25, linguistic_factor * length_factor))

    # Combine factors: base weight * confidence + linguistic adjustment
    raw_score = confidence_weighted + linguistic_risk

    # Normalize to 0-1 range
    normalized_score = max(0.0, min(1.0, raw_score))

    # Uncertainty quantification
    # Higher uncertainty when:
    # 1. Classifier confidence is low
    # 2. Score is near decision boundaries (0.4 and 0.7 thresholds)
    # 3. Text is very short or very long (less reliable linguistic analysis)
    uncertainty = 0.0

    # Classifier uncertainty (inverse of confidence)
    classifier_uncertainty = 1.0 - confidence

    # Boundary uncertainty - higher when score is near decision thresholds (0.4 and 0.7)
    boundary_distance = min(
        abs(normalized_score - 0.4),  # Distance to low/medium boundary
        abs(normalized_score - 0.7)   # Distance to medium/high boundary
    )
    # Scale: closer than 0.15 to a boundary produces uncertainty
    boundary_uncertainty = max(0.0, min(1.0, 1.0 - (boundary_distance / 0.15)))

    # Text length uncertainty - very short or very long texts are less reliable
    if clause_text:
        word_count = len(clause_text.split())
        if word_count < 3:  # Very short
            length_uncertainty = 0.3
        elif word_count > 50:  # Very long
            length_uncertainty = 0.2
        else:
            length_uncertainty = 0.0
    else:
        length_uncertainty = 0.4  # No text analysis possible

    # Combine uncertainty factors (weighted average)
    uncertainty = (
        classifier_uncertainty * 0.5 +
        boundary_uncertainty * 0.3 +
        length_uncertainty * 0.2
    )
    uncertainty = max(0.0, min(0.8, uncertainty))  # Cap uncertainty

    # Adjust score based on uncertainty (conservative approach: push uncertain scores toward middle)
    # This means high uncertainty scores get adjusted toward 0.5 (medium risk)
    if uncertainty > 0.15:
        adjustment_factor = min(0.35, (uncertainty - 0.15) * 0.8)  # Scale adjustment
        pull_toward_middle = 0.5  # Pull toward medium risk
        normalized_score = (
            normalized_score * (1 - adjustment_factor) +
            pull_toward_middle * adjustment_factor
        )
        # Renormalize after adjustment
        normalized_score = max(0.0, min(1.0, normalized_score))

    # Convert to 0-100 score
    risk_score_0_100 = int(normalized_score * 100)

    # Determine categorical risk level (maintain backward compatibility)
    if normalized_score >= 0.7:
        risk_level = "High"
    elif normalized_score >= 0.4:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Special case for No Clause
    if label == "No Clause":
        risk_level = None
        risk_score_0_100 = 0
        normalized_score = 0.0
        uncertainty = 0.1  # Low uncertainty for clear "no clause" cases

    return {
        "risk_level": risk_level,
        "risk_score": risk_score_0_100,
        "risk_score_normalized": normalized_score,
        "uncertainty": uncertainty,
        "uncertainty_level": "High" if uncertainty > 0.5 else "Medium" if uncertainty > 0.2 else "Low",
        "components": {
            "base_weight": base_weight,
            "confidence": confidence,
            "confidence_weighted": confidence_weighted,
            "linguistic_adjustment": linguistic_risk,
            "raw_score": raw_score,
            "normalized_score_before_uncertainty_adjustment": max(0.0, min(1.0, confidence_weighted + linguistic_risk)),
            "uncertainty": uncertainty,
            "classifier_uncertainty": classifier_uncertainty,
            "boundary_uncertainty": boundary_uncertainty,
            "length_uncertainty": length_uncertainty if 'length_uncertainty' in locals() else 0.0,
            "final_normalized_score": normalized_score
        }
    }


def compute_enhanced_clause_risk(label: str, confidence: float = 1.0, clause_text: str = "") -> Dict[str, Any]:
    """Compute enhanced risk score for a clause combining base risk, confidence, linguistic features, and uncertainty quantification.

    Args:
        label: Clause type label from classifier.
        confidence: Classification confidence score (0-1).
        clause_text: The actual clause text for linguistic analysis.

    Returns:
        Dict with risk_level (High/Medium/Low), risk_score (0-100), uncertainty estimate, and components.
    """
    # Use the cached version for performance
    return _compute_enhanced_clause_risk_cached(label, confidence, clause_text)


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

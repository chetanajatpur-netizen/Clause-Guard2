"""Language and script detection service for multilingual legal documents.

Supports:
- Script-based detection for Devanagari (Hindi), Kannada, Telugu, Latin (English), etc.
- Mixed-script detection and script distribution analysis.
- Machine-learning calibrated segment classification when model artifact is present.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Unicode Codepoint Ranges for Indian Scripts & Latin
SCRIPT_RANGES = {
    "Devanagari": (0x0900, 0x097F),
    "Kannada": (0x0C80, 0x0CFF),
    "Telugu": (0x0C00, 0x0C7F),
    "Tamil": (0x0B80, 0x0BFF),
    "Malayalam": (0x0D00, 0x0D7F),
    "Bengali": (0x0980, 0x09FF),
    "Gujarati": (0x0A80, 0x0AFF),
    "Latin": (0x0041, 0x007A),  # Includes uppercase/lowercase ASCII; checked with isalpha()
}

# Mapping dominant script to primary ISO/name language code
SCRIPT_TO_LANGUAGE = {
    "Devanagari": "hindi",
    "Kannada": "kannada",
    "Telugu": "telugu",
    "Tamil": "tamil",
    "Malayalam": "malayalam",
    "Bengali": "bengali",
    "Gujarati": "gujarati",
    "Latin": "english",
}

# Cache for loaded ML pipeline
_CLASSIFIER_PIPELINE: Any = None
_CLASSIFIER_LOADED: bool = False


class LanguageDetectionResult(BaseModel):
    """Result of language and script identification."""

    language: str = Field(..., description="Detected language: 'hindi', 'kannada', 'english', 'telugu', etc.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    script: str = Field(..., description="Primary Unicode script: 'Devanagari', 'Kannada', 'Latin', etc.")
    is_mixed: bool = Field(False, description="True if document contains significant multi-script content")
    dominant_script_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of dominant script")
    script_distribution: Dict[str, float] = Field(
        default_factory=dict, description="Script frequency breakdown (percentage)"
    )


def _get_classifier() -> Optional[Any]:
    """Lazy load calibrated ML classifier pipeline if available."""
    global _CLASSIFIER_PIPELINE, _CLASSIFIER_LOADED
    if _CLASSIFIER_LOADED:
        return _CLASSIFIER_PIPELINE

    _CLASSIFIER_LOADED = True
    model_path = Path(__file__).resolve().parents[3] / "ml" / "multilingual" / "artifacts" / "language_classifier.joblib"
    if model_path.exists():
        try:
            import joblib
            _CLASSIFIER_PIPELINE = joblib.load(model_path)
            logger.info("Loaded multilingual classifier from %s", model_path)
        except Exception as e:
            logger.warning("Failed to load language classifier from %s: %s", model_path, e)
            _CLASSIFIER_PIPELINE = None
    return _CLASSIFIER_PIPELINE


def analyze_scripts(text: str) -> Dict[str, int]:
    """Count occurrences of characters in known Unicode script ranges."""
    counts: Dict[str, int] = {s: 0 for s in SCRIPT_RANGES}
    counts["Other"] = 0

    for char in text:
        if not char.strip() or char.isdigit() or not char.isalpha():
            continue
        cp = ord(char)
        matched = False
        for script, (start, end) in SCRIPT_RANGES.items():
            if script == "Latin":
                if ("A" <= char <= "Z") or ("a" <= char <= "z"):
                    counts["Latin"] += 1
                    matched = True
                    break
            elif start <= cp <= end:
                counts[script] += 1
                matched = True
                break
        if not matched:
            counts["Other"] += 1

    return counts


def detect_language(text: str, use_ml_if_available: bool = True) -> LanguageDetectionResult:
    """Detect the dominant language and script of a given text.

    Args:
        text: Input string (clause or document excerpt).
        use_ml_if_available: Whether to query the calibrated classifier for supported classes.

    Returns:
        LanguageDetectionResult containing language code, script, confidence, and distribution.
    """
    if not text or not text.strip():
        return LanguageDetectionResult(
            language="unknown",
            confidence=0.0,
            script="None",
            is_mixed=False,
            dominant_script_percentage=0.0,
            script_distribution={},
        )

    counts = analyze_scripts(text)
    total_alpha = sum(counts.values())

    if total_alpha == 0:
        return LanguageDetectionResult(
            language="unknown",
            confidence=0.0,
            script="None",
            is_mixed=False,
            dominant_script_percentage=0.0,
            script_distribution={},
        )

    # Compute percentage distribution
    dist = {k: round((v / total_alpha) * 100.0, 2) for k, v in counts.items() if v > 0}
    sorted_scripts = sorted(dist.items(), key=lambda x: x[1], reverse=True)

    top_script, top_pct = sorted_scripts[0]
    dominant_lang = SCRIPT_TO_LANGUAGE.get(top_script, "unknown")

    # Mixed-script threshold: secondary script has at least 15% presence
    is_mixed = False
    if len(sorted_scripts) > 1 and sorted_scripts[1][1] >= 15.0:
        is_mixed = True

    confidence = round(top_pct / 100.0, 4)

    # If ML classifier is available and language is among trained classes (hindi, kannada, english),
    # combine script heuristic with calibrated model posterior
    if use_ml_if_available:
        clf = _get_classifier()
        if clf is not None and len(text.strip()) >= 20:
            try:
                probs = clf.predict_proba([text])[0]
                classes = clf.classes_
                best_idx = probs.argmax()
                ml_lang = str(classes[best_idx])
                ml_conf = float(probs[best_idx])

                # If pure script is strongly identified (>80%), keep script lang with max confidence
                if top_pct >= 80.0:
                    confidence = max(confidence, ml_conf)
                else:
                    # In mixed or low-margin segments, trust calibrated ML model
                    dominant_lang = ml_lang
                    confidence = round(ml_conf, 4)
            except Exception as e:
                logger.debug("Classifier inference error: %s", e)

    return LanguageDetectionResult(
        language=dominant_lang,
        confidence=confidence,
        script=top_script,
        is_mixed=is_mixed,
        dominant_script_percentage=top_pct,
        script_distribution=dist,
    )

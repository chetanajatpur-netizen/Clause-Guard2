"""Sentence segmentation for Indic and multilingual legal texts.

Splits legal texts by:
- Danda (।) [U+0964] and Double Danda (॥) [U+0965]
- Western sentence terminators (., ?, !)
- Clause/paragraph boundaries

Protects:
- Decimal numbers (e.g., 12.11.2026, 3.14)
- List enumeration markers (e.g., 1., 2., १., २., ೧., ೨.)
- Legal abbreviations (e.g., D.H.C., R.C., v., vs., Sec., Art., No., सं., पृ.)
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Known abbreviation patterns that should not trigger sentence splits
ABBREVIATIONS = [
    r"D\.H\.C",
    r"S\.C",
    r"H\.C",
    r"R\.C",
    r"RDPR",
    r"Govt",
    r"v",
    r"vs",
    r"Sec",
    r"Art",
    r"No",
    r"Shri",
    r"Smt",
    r"Dr",
    r"Adv",
    r"Hon'ble",
    r"Hon",
    r"p\.m",
    r"a\.m",
    r"e\.g",
    r"i\.e",
    r"सं",
    r"नं",
    r"पृ",
    r"मू",
    r"अ",
    r"ͧस\.अ",
    r"ͧस\.मू",
]

# Compile negative lookbehind / replacement placeholders
ABBR_REGEX = re.compile(
    r"\b(" + "|".join(ABBREVIATIONS) + r")\.",
    re.IGNORECASE,
)
DECIMAL_REGEX = re.compile(r"(\d+)\.(\d+)")
ENUM_REGEX = re.compile(r"(?:^|[\n\s])([0-9\u0966-\u096F\u0CE6-\u0CEF]+)\.\s+")

# Sentence split boundary pattern:
# 1. Danda (।) or Double Danda (॥) followed by whitespace, newline, or end-of-string
# 2. Period/Exclamation/Question followed by whitespace or quote and capital/indic letter
SPLIT_PATTERN = re.compile(
    r"(?<=[।॥])\s+|(?<=[.!?])\s+(?=[A-Z\u0900-\u097F\u0C80-\u0CFF\u0C00-\u0C7F0-9\(\[\"\'\-\—])|(?:\n\s*\n+)"
)


def split_indic_sentences(text: str, min_chars: int = 15) -> List[str]:
    """Split Indic legal text into discrete sentences or clauses.

    Args:
        text: Multilingual or Indic input text.
        min_chars: Minimum character length to retain as a standalone sentence.

    Returns:
        List of clean sentence strings.
    """
    if not text or not text.strip():
        return []

    # Preserve decimals by masking dot with a temporary token
    masked = DECIMAL_REGEX.sub(r"\1<DOT>\2", text)

    # Protect list enumerations at beginning of line or whitespace (e.g., '1. ' -> '1<DOT> ')
    def mask_enum(match: re.Match) -> str:
        s = match.group(0)
        return s.replace(".", "<DOT>")

    masked = ENUM_REGEX.sub(mask_enum, masked)

    # Protect known abbreviations (e.g. 'D.H.C.' or 'No.')
    def mask_abbr(match: re.Match) -> str:
        return match.group(0).replace(".", "<DOT>")

    masked = ABBR_REGEX.sub(mask_abbr, masked)

    # Perform boundary splitting
    raw_parts = SPLIT_PATTERN.split(masked)

    sentences = []
    for part in raw_parts:
        restored = part.replace("<DOT>", ".").strip()
        # Clean redundant internal whitespaces
        restored = re.sub(r"[ \t]+", " ", restored)
        if len(restored) >= min_chars:
            sentences.append(restored)

    return sentences


def split_indic_sentences_with_spans(text: str, min_chars: int = 15) -> List[Dict[str, Any]]:
    """Split text into sentences while tracking exact character spans in the input text.

    Args:
        text: Multilingual or Indic input text.
        min_chars: Minimum character length to retain as a standalone sentence.

    Returns:
        List of dicts with 'text', 'start', and 'end' character offsets.
    """
    sentences = split_indic_sentences(text, min_chars=min_chars)
    spans: List[Dict[str, Any]] = []
    last_end = 0

    for sent in sentences:
        # Find position of sent (or first 30 chars if whitespace normalized) in text
        search_key = sent[:min(30, len(sent))]
        idx = text.find(search_key, last_end)
        if idx != -1:
            end_idx = idx + len(sent)
            # Find end in case whitespace differed slightly
            spans.append({
                "text": sent,
                "start": idx,
                "end": end_idx,
            })
            last_end = end_idx
        else:
            # Fallback if exact substring not found due to whitespace normalization
            spans.append({
                "text": sent,
                "start": last_end,
                "end": last_end + len(sent),
            })
            last_end += len(sent)

    return spans

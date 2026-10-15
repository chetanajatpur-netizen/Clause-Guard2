"""Deterministic redline generator engine using regex templates and difflib."""
from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).resolve().parent / "templates.json"

_TEMPLATES_CACHE: Optional[Dict[str, List[Dict[str, Any]]]] = None


def load_templates() -> Dict[str, List[Dict[str, Any]]]:
    """Load redline templates from templates.json."""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None:
        if not TEMPLATES_PATH.exists():
            logger.warning("Redline templates file not found: %s", TEMPLATES_PATH)
            return {}
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            _TEMPLATES_CACHE = json.load(f)
    return _TEMPLATES_CACHE


def _tokenize_for_diff(text: str) -> List[str]:
    """Tokenize string into words and whitespace/punctuation chunks for exact diffing."""
    if not text:
        return []
    return re.findall(r"\S+|\s+", text)


def compute_word_diff(original_text: str, replacement_text: str) -> List[Dict[str, str]]:
    """Compute word-level diff segments between original and replacement text."""
    orig_tokens = _tokenize_for_diff(original_text)
    repl_tokens = _tokenize_for_diff(replacement_text)

    matcher = difflib.SequenceMatcher(None, orig_tokens, repl_tokens)
    segments: List[Dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            text = "".join(orig_tokens[i1:i2])
            if text:
                segments.append({"type": "equal", "text": text})
        elif tag == "delete":
            text = "".join(orig_tokens[i1:i2])
            if text:
                segments.append({"type": "delete", "text": text})
        elif tag == "insert":
            text = "".join(repl_tokens[j1:j2])
            if text:
                segments.append({"type": "insert", "text": text})
        elif tag == "replace":
            del_text = "".join(orig_tokens[i1:i2])
            ins_text = "".join(repl_tokens[j1:j2])
            if del_text:
                segments.append({"type": "delete", "text": del_text})
            if ins_text:
                segments.append({"type": "insert", "text": ins_text})

    return segments


def suggest_redline(label: str, text: str) -> Optional[Dict[str, Any]]:
    """Suggest safer redline wording for a given clause text and label.

    Args:
        label: Clause classification label (e.g. 'Termination for Convenience').
        text: Raw clause text.

    Returns:
        Dict with keys:
            - diff_segments: list of {'type': 'equal'|'delete'|'insert', 'text': str}
            - replacement: full replacement text string
            - rationale: negotiation/safety explanation
            - verify_status: 'seed_unreviewed'
        or None if no template matches.
    """
    if not text or not text.strip() or not label:
        return None

    templates_by_label = load_templates()
    templates = templates_by_label.get(label, [])
    if not templates:
        return None

    for template in templates:
        pattern = template.get("match", "")
        if not pattern:
            continue

        try:
            match = re.search(pattern, text)
        except re.error as e:
            logger.error("Regex error in redline template %s: %s", template.get("id"), e)
            continue

        if match:
            # Extract named groups
            groups = {k: v for k, v in match.groupdict().items() if v}
            defaults = {
                "party": "Contractor",
                "client": "Client",
                "notice": "thirty (30) days",
                "rate": "0.5%",
                "cap": "10%",
                "duration": "six (6) months",
            }
            replacements = {**defaults, **groups}

            # Fill placeholders in replace_with
            replace_with = template["replace_with"]
            for key, val in replacements.items():
                replace_with = replace_with.replace(f"{{{key}}}", str(val))
            # Clean up any remaining unpopulated {placeholder} tags
            replace_with = re.sub(r"\{[a-zA-Z0-9_]+\}", "", replace_with)

            # Splice replacement into the original text
            start, end = match.span()
            suffix = text[end:]
            if replace_with.endswith(".") and suffix.startswith("."):
                suffix = suffix[1:]
            full_replacement = text[:start] + replace_with + suffix

            # Compute diff
            diff_segments = compute_word_diff(text, full_replacement)

            return {
                "diff_segments": diff_segments,
                "replacement": full_replacement,
                "rationale": template.get("rationale", "Safer wording based on standard market practice."),
                "verify_status": template.get("verify_status", "seed_unreviewed"),
            }

    return None

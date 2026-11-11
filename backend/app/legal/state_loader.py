"""State-law module loader, state detection, and statutory disclaimer generator."""
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

STATES_DIR = Path(__file__).resolve().parent / "states"

VERIFY_STATUS_UNREVIEWED = {"empty", "seed_unreviewed"}
LAWYER_REVIEW_WARNING = "Not reviewed by a lawyer"


def _normalize_key(name: str) -> str:
    """Normalize state name to file slug."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return clean


def list_state_slugs() -> list[str]:
    """List available state configuration slugs (excluding templates)."""
    if not STATES_DIR.exists():
        return []
    slugs = []
    for p in sorted(STATES_DIR.glob("*.json")):
        if p.name.upper() == "TEMPLATE.JSON" or p.stem.upper() == "TEMPLATE":
            continue
        slugs.append(p.stem)
    return slugs


def load_state_module(
    state_identifier: str, sanitize: bool = True
) -> Optional[dict[str, Any]]:
    """Load a state JSON module by state name or slug.
    
    Rule: A field with citation_url null must never be shown to the user.
    If the module is empty or seed_unreviewed, it is flagged with a review warning.
    
    Args:
        state_identifier: State name (e.g. 'Karnataka') or slug ('karnataka').
        sanitize: If True, strip fields without valid citations and attach review warnings.
        
    Returns:
        State dictionary or None if not found.
    """
    if not state_identifier or not STATES_DIR.exists():
        return None

    slug = _normalize_key(state_identifier)
    target_path = STATES_DIR / f"{slug}.json"

    # Fallback search by state field inside files if slug does not match directly
    if not target_path.exists():
        for p in STATES_DIR.glob("*.json"):
            if p.name.upper() == "TEMPLATE.JSON":
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("state") and data["state"].strip().lower() == state_identifier.strip().lower():
                    target_path = p
                    break
            except Exception:
                continue

    if not target_path.exists():
        return None

    try:
        with open(target_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Failed to parse state file %s: %s", target_path, e)
        return None

    if sanitize:
        return sanitize_state_module(data)
    return data


def sanitize_state_module(raw_module: dict[str, Any]) -> dict[str, Any]:
    """Filter out legal fields lacking citation_url and attach verification warning.
    
    Rule: A field with citation_url null must never be shown to the user.
    """
    data = json.loads(json.dumps(raw_module))  # deep copy
    status = data.get("verify_status", "empty")

    # Attach UI review warning if not reviewed by a qualified lawyer
    if status in VERIFY_STATUS_UNREVIEWED:
        data["review_warning"] = LAWYER_REVIEW_WARNING
        data["is_reviewed"] = False
    else:
        data["review_warning"] = None
        data["is_reviewed"] = True

    rental = data.get("rental") or {}
    sanitized_rental: dict[str, Any] = {}

    # Governing acts: only keep acts with valid non-empty citation_url
    governing_acts = rental.get("governing_acts") or []
    valid_acts = []
    for act in governing_acts:
        if isinstance(act, dict) and act.get("citation_url"):
            valid_acts.append(act)
    sanitized_rental["governing_acts"] = valid_acts

    # Specific rule objects: hide field completely if citation_url is null
    rule_keys = [
        "registration_requirement",
        "stamp_duty",
        "security_deposit_rule",
        "notice_and_eviction",
        "rent_authority_or_tribunal",
    ]
    for rk in rule_keys:
        rule_val = rental.get(rk)
        if isinstance(rule_val, dict) and rule_val.get("citation_url"):
            sanitized_rental[rk] = rule_val
        else:
            sanitized_rental[rk] = None

    data["rental"] = sanitized_rental
    return data


def detect_state(text: str) -> Optional[str]:
    """Detect Indian state from contract text using detection_keywords.
    
    Args:
        text: Input agreement text.
        
    Returns:
        Canonical state name (e.g. 'Karnataka') or None if not found.
    """
    if not text or not str(text).strip():
        return None

    norm_text = str(text)
    slugs = list_state_slugs()
    scores: dict[str, int] = {}
    canonical_names: dict[str, str] = {}

    for slug in slugs:
        module = load_state_module(slug, sanitize=False)
        if not module:
            continue

        state_name = module.get("state") or slug.replace("_", " ").title()
        canonical_names[slug] = state_name
        keywords = module.get("detection_keywords") or {}
        score = 0

        # High priority: exact state names and high courts
        for kw in keywords.get("states", []):
            if _match_keyword(kw, norm_text):
                score += 5
        for kw in keywords.get("courts", []):
            if _match_keyword(kw, norm_text):
                score += 5

        # Moderate priority: districts
        for kw in keywords.get("districts", []):
            if _match_keyword(kw, norm_text):
                score += 2

        if score > 0:
            scores[slug] = score

    if not scores:
        return None

    best_slug = max(scores, key=lambda s: scores[s])
    return canonical_names[best_slug]


def _match_keyword(keyword: str, text: str) -> bool:
    """Case-insensitive word match for Latin, substring for non-Latin."""
    if not keyword:
        return False
    # If purely ASCII, enforce word boundaries
    if keyword.isascii():
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))
    # For Indic scripts, use exact unicode substring match
    return keyword in text


def generate_state_notes(state_module: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate neutral statutory disclaimer notes for a sanitized state module.
    
    Rule:
    Show a note only as 'May differ under <Act name> (<state>). Check with a local lawyer.'
    with the citation link and review date; never a verdict.
    Empty modules or fields without citation_url return no note.
    """
    if not state_module or state_module.get("verify_status") == "empty":
        return []

    state_name = state_module.get("state") or "Local Jurisdiction"
    review_date = state_module.get("last_reviewed")
    review_warning = state_module.get("review_warning")
    rental = state_module.get("rental") or {}

    notes: list[dict[str, Any]] = []

    # Notes for governing acts
    for act in rental.get("governing_acts", []):
        act_name = act.get("name")
        citation_url = act.get("citation_url")
        if act_name and citation_url:
            notes.append({
                "note": f"May differ under {act_name} ({state_name}). Check with a local lawyer.",
                "citation_url": citation_url,
                "review_date": review_date,
                "state": state_name,
                "act_name": act_name,
                "review_warning": review_warning,
            })

    # Notes for other verified statutory topics
    topic_labels = {
        "registration_requirement": "Mandatory Registration Rules",
        "stamp_duty": "Stamp Duty Regulations",
        "security_deposit_rule": "Security Deposit Limitations",
        "notice_and_eviction": "Eviction Notice Statutory Procedure",
        "rent_authority_or_tribunal": "Rent Tribunal Jurisdiction",
    }
    for field_key, label in topic_labels.items():
        field_val = rental.get(field_key)
        if isinstance(field_val, dict) and field_val.get("citation_url"):
            citation_url = field_val["citation_url"]
            notes.append({
                "note": f"May differ under {label} ({state_name}). Check with a local lawyer.",
                "citation_url": citation_url,
                "review_date": review_date,
                "state": state_name,
                "act_name": label,
                "review_warning": review_warning,
            })

    return notes

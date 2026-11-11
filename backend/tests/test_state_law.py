"""Unit tests for the state-law module framework:
1. Unknown state returns None
2. Empty module returns no note
3. Field without citation is hidden
4. Detection across English and regional scripts (Kannada, Telugu, Devanagari)
5. Unreviewed states flagged with 'Not reviewed by a lawyer'
6. Note format strictly follows 'May differ under <Act name> (<state>). Check with a local lawyer.'
"""
import pytest
from app.legal.state_loader import (
    detect_state,
    generate_state_notes,
    list_state_slugs,
    load_state_module,
    sanitize_state_module,
    LAWYER_REVIEW_WARNING,
)


def test_unknown_state_returns_none():
    """Text with no matching Indian state keywords returns None."""
    assert detect_state("") is None
    assert detect_state("   ") is None
    assert detect_state("This contract is executed in Manhattan, New York under Delaware law.") is None
    assert detect_state("Standard NDA between Company X and Vendor Y without territorial reference.") is None


def test_empty_module_returns_no_note():
    """An empty or unverified state module returns zero notes."""
    for slug in ["karnataka", "andhra_pradesh", "telangana", "uttar_pradesh", "delhi"]:
        module = load_state_module(slug)
        assert module is not None
        assert module["verify_status"] == "empty"
        notes = generate_state_notes(module)
        assert notes == [], f"Expected 0 notes for empty module {slug}, got {len(notes)}"


def test_field_without_citation_is_hidden():
    """Rule: A field with citation_url null must never be shown to the user."""
    mock_raw = {
        "state": "Sample State",
        "verify_status": "seed_unreviewed",
        "last_reviewed": "2026-11-11",
        "rental": {
            "governing_acts": [
                {
                    "name": "Uncited Act",
                    "year": 2020,
                    "citation_url": None,  # No citation -> MUST BE HIDDEN
                },
                {
                    "name": "Official Tenancy Act",
                    "year": 2021,
                    "citation_url": "https://indiacode.nic.in/handle/123456789/test",
                },
            ],
            "stamp_duty": {
                "summary": "1% of total annual rent",
                "citation_url": None,  # No citation -> MUST BE HIDDEN
                "as_of": "2026-01-01",
            },
            "registration_requirement": {
                "summary": "Registration compulsory above 11 months",
                "citation_url": "https://example.gov.in/registration",
            },
            "security_deposit_rule": {
                "summary": "Cap of 2 months rent",
                "citation_url": None,  # No citation -> MUST BE HIDDEN
            },
        },
    }

    sanitized = sanitize_state_module(mock_raw)

    # 1. Uncited act is removed from governing_acts
    acts = sanitized["rental"]["governing_acts"]
    assert len(acts) == 1
    assert acts[0]["name"] == "Official Tenancy Act"

    # 2. Uncited rule fields are set to None (hidden)
    assert sanitized["rental"]["stamp_duty"] is None
    assert sanitized["rental"]["security_deposit_rule"] is None

    # 3. Cited rule field is retained
    assert sanitized["rental"]["registration_requirement"] is not None
    assert sanitized["rental"]["registration_requirement"]["citation_url"] == "https://example.gov.in/registration"

    # 4. Notes are only generated for cited entries
    notes = generate_state_notes(sanitized)
    assert len(notes) == 2
    for note_obj in notes:
        assert note_obj["citation_url"] is not None
        assert note_obj["note"].startswith("May differ under ")
        assert "Check with a local lawyer." in note_obj["note"]
        # Ensure no verdict language
        assert "illegal" not in note_obj["note"].lower()
        assert "void" not in note_obj["note"].lower()


def test_unreviewed_state_flags_lawyer_warning():
    """If a module is empty or seed_unreviewed, UI shows 'Not reviewed by a lawyer'."""
    karnataka = load_state_module("karnataka")
    assert karnataka["review_warning"] == LAWYER_REVIEW_WARNING
    assert karnataka["is_reviewed"] is False

    mock_seed = {
        "state": "Test State",
        "verify_status": "seed_unreviewed",
        "rental": {},
    }
    sanitized_seed = sanitize_state_module(mock_seed)
    assert sanitized_seed["review_warning"] == LAWYER_REVIEW_WARNING
    assert sanitized_seed["is_reviewed"] is False

    mock_reviewed = {
        "state": "Test State",
        "verify_status": "reviewed",
        "rental": {},
    }
    sanitized_reviewed = sanitize_state_module(mock_reviewed)
    assert sanitized_reviewed["review_warning"] is None
    assert sanitized_reviewed["is_reviewed"] is True


def test_detect_state_english_and_indic_scripts():
    """Detect state correctly across English, Kannada, Telugu, and Devanagari text."""
    # Karnataka (English & Kannada)
    assert detect_state("The premises are located in Bengaluru, Karnataka.") == "Karnataka"
    assert detect_state("ಈ ಬಾಡಿಗೆ ಒಪ್ಪಂದವು ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಜಾರಿಗೆ ಬರುತ್ತದೆ.") == "Karnataka"

    # Telangana (English & Telugu)
    assert detect_state("Disputes shall be settled by courts in Hyderabad, Telangana.") == "Telangana"
    assert detect_state("తెలంగాణ రాష్ట్రంలోని హైదరాబాద్ నగరంలో కుదుర్చుకున్న ఒప్పందం.") == "Telangana"

    # Andhra Pradesh (English & Telugu)
    assert detect_state("Commercial property situated in Visakhapatnam, Andhra Pradesh.") == "Andhra Pradesh"
    assert detect_state("విశాఖపట్నం జిల్లా ఆంధ్రప్రదేశ్ పరిధిలోని ఆస్తి.") == "Andhra Pradesh"

    # Uttar Pradesh (English & Hindi)
    assert detect_state("Governed by jurisdiction of courts in Lucknow, Uttar Pradesh.") == "Uttar Pradesh"
    assert detect_state("यह अनुबंध लखनऊ, उत्तर प्रदेश में निष्पादित किया गया है।") == "Uttar Pradesh"

    # Delhi (English & Hindi)
    assert detect_state("Registered office located at Connaught Place, New Delhi.") == "Delhi"
    assert detect_state("नई दिल्ली साकेत जिला न्यायालय के अधिकार क्षेत्र में।") == "Delhi"


def test_state_slugs_list():
    """All 5 required state modules exist."""
    slugs = list_state_slugs()
    for required in ["karnataka", "andhra_pradesh", "telangana", "uttar_pradesh", "delhi"]:
        assert required in slugs, f"Missing required state module: {required}"

"""Unit and API tests for redline generator (Feature 1, Phase 4)."""
import re
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.redline.engine import suggest_redline
from app.services.segmenter import segment_text

client = TestClient(app)

TESTKIT_DIR = Path(__file__).resolve().parent.parent.parent / "clauseguard-testkit" / "contracts"


def test_redline_match_returns_diff():
    """Test that a matching clause returns a full diff structure."""
    text = (
        "Client may terminate this Agreement at any time, for any reason or for no reason, "
        "by giving Contractor twenty-four (24) hours' written notice. Contractor may not terminate "
        "this Agreement before completion of all milestones without Client's written consent."
    )
    result = suggest_redline("Termination for Convenience", text)
    assert result is not None
    assert "diff_segments" in result
    assert "replacement" in result
    assert "rationale" in result
    assert result["verify_status"] == "seed_unreviewed"
    assert len(result["diff_segments"]) > 0

    # Ensure segments have valid types
    types = {s["type"] for s in result["diff_segments"]}
    assert "delete" in types
    assert "insert" in types

    # Reconstructed text from deletes and equals equals original text
    orig_reconstructed = "".join(s["text"] for s in result["diff_segments"] if s["type"] in ("equal", "delete"))
    assert orig_reconstructed == text

    # Reconstructed text from inserts and equals equals replacement text
    repl_reconstructed = "".join(s["text"] for s in result["diff_segments"] if s["type"] in ("equal", "insert"))
    assert repl_reconstructed == result["replacement"]


def test_redline_no_match_returns_none():
    """Test that a clause without a matching pattern returns None."""
    benign_text = "This Agreement shall be governed by the laws of California."
    result = suggest_redline("No Clause", benign_text)
    assert result is None

    # Even with a known label, non-matching benign wording returns None
    result2 = suggest_redline("Termination for Convenience", "This Agreement expires on December 31, 2026.")
    assert result2 is None


def test_redline_placeholders_are_filled():
    """Test that all placeholders in the template are filled with no leftover {brackets}."""
    text = (
        "Contractor shall be liable for, and shall indemnify Client against, all losses, damages, "
        "costs and expenses of any kind arising out of the Services, and Contractor's liability "
        "under this Agreement shall not be subject to any limit or cap."
    )
    result = suggest_redline("Uncapped Liability", text)
    assert result is not None
    # No curly bracket placeholders remaining
    assert not re.search(r"\{[a-zA-Z0-9_]+\}", result["replacement"])
    assert "Contractor" in result["replacement"]
    assert "Client" in result["replacement"]


def test_doc06_trap_clauses_return_none():
    """Verify that none of the benign clauses in DOC-06 produce redlines."""
    doc06_path = TESTKIT_DIR / "DOC-06_benign_terms.txt"
    assert doc06_path.exists(), f"DOC-06 file missing at {doc06_path}"
    doc06_text = doc06_path.read_text(encoding="utf-8")
    chunks = segment_text(doc06_text)
    assert len(chunks) > 0

    # Test all 10 PRD labels against every chunk in DOC-06
    from app.core.risk_map import RISK_MAP
    prd_labels = list(RISK_MAP.keys())

    for chunk in chunks:
        for label in prd_labels:
            redline = suggest_redline(label, chunk)
            assert redline is None, f"Unexpected redline for benign DOC-06 chunk under {label}: {chunk}"


def test_doc01_termination_produces_redline():
    """Verify DOC-01 Clause 7 (Termination) produces a redline."""
    doc01_path = TESTKIT_DIR / "DOC-01_freelance_agreement.txt"
    assert doc01_path.exists()
    doc01_text = doc01_path.read_text(encoding="utf-8")
    chunks = segment_text(doc01_text)

    # Clause 7 contains termination
    term_chunk = next((c for c in chunks if "Client may terminate this Agreement at any time" in c), None)
    assert term_chunk is not None, "Clause 7 not found in DOC-01"

    result = suggest_redline("Termination for Convenience", term_chunk)
    assert result is not None
    assert "thirty (30) days" in result["replacement"]
    assert result["verify_status"] == "seed_unreviewed"
    assert any(s["type"] == "delete" and "twenty-four" in s["text"] for s in result["diff_segments"])


def test_doc01_liability_produces_redline():
    """Verify DOC-01 Clause 8 (Uncapped Liability) produces a redline."""
    doc01_path = TESTKIT_DIR / "DOC-01_freelance_agreement.txt"
    assert doc01_path.exists()
    doc01_text = doc01_path.read_text(encoding="utf-8")
    chunks = segment_text(doc01_text)

    # Clause 8 contains uncapped liability
    liab_chunk = next((c for c in chunks if "shall not be subject to any limit or cap" in c), None)
    assert liab_chunk is not None, "Clause 8 not found in DOC-01"

    result = suggest_redline("Uncapped Liability", liab_chunk)
    assert result is not None
    assert "capped" in result["replacement"]
    assert result["verify_status"] == "seed_unreviewed"
    deleted_text = " ".join(s["text"] for s in result["diff_segments"] if s["type"] == "delete")
    assert "limit" in deleted_text and "cap" in deleted_text


def test_api_redline_endpoint_success():
    """Test POST /api/v1/redline returns 200 with full diff schema."""
    payload = {
        "clause_label": "Termination for Convenience",
        "clause_text": (
            "7. Termination. Client may terminate this Agreement at any time, for any reason or for no reason, "
            "by giving Contractor twenty-four (24) hours' written notice."
        ),
    }
    response = client.post("/api/v1/redline", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert "diff_segments" in data
    assert "replacement" in data
    assert "rationale" in data
    assert data["verify_status"] == "seed_unreviewed"
    assert len(data["diff_segments"]) > 0


def test_api_redline_endpoint_no_match():
    """Test POST /api/v1/redline returns 200 with null when no template matches."""
    payload = {
        "clause_label": "No Clause",
        "clause_text": "This Agreement shall be governed by California law.",
    }
    response = client.post("/api/v1/redline", json=payload)
    assert response.status_code == 200
    assert response.json() is None


def test_api_redline_endpoint_bad_input():
    """Test POST /api/v1/redline with empty input returns standard 400 error envelope."""
    # Empty clause_text
    response = client.post("/api/v1/redline", json={"clause_label": "Non-Compete", "clause_text": "   "})
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "clause_text cannot be empty" in data["error"]["message"]

    # Empty clause_label
    response2 = client.post("/api/v1/redline", json={"clause_label": "", "clause_text": "Valid text"})
    # Pydantic validation (min_length=1) will catch empty string as 422 or 400
    assert response2.status_code in (400, 422)
    data2 = response2.json()
    assert "error" in data2

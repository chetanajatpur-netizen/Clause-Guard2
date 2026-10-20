"""Adversarial and edge-case stress tests for ClauseGuard."""
from __future__ import annotations

import io
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

from fastapi.testclient import TestClient

from app.main import app
from app.redline.engine import compute_word_diff, suggest_redline
from app.services.parser import extract_text
from app.services.risk import compute_enhanced_clause_risk
from app.services.segmenter import segment_text

logger = logging.getLogger("stress_adversarial")


def run_adversarial_stress_tests() -> Dict[str, Any]:
    """Execute all adversarial and edge-case input stress tests."""
    results: Dict[str, Any] = {}

    # Test 1: Mega unpunctuated text (25k characters)
    t0 = time.time()
    unpunctuated = "contractor obligation liability term " * 5000
    chunks = segment_text(unpunctuated, max_len=2000)
    max_chunk_len = max((len(c) for c in chunks), default=0)
    results["mega_unpunctuated"] = {
        "passed": max_chunk_len <= 4000,
        "input_len": len(unpunctuated),
        "chunk_count": len(chunks),
        "max_chunk_len": max_chunk_len,
        "duration_sec": round(time.time() - t0, 4),
    }

    # Test 2: Massive synthetic contract (500 clauses, ~35k words)
    t0 = time.time()
    paragraphs = [
        f"{i}. Clause {i}. The Contractor shall perform software delivery and indemnify Client against losses."
        for i in range(1, 501)
    ]
    giant_contract = "\n\n".join(paragraphs)
    giant_chunks = segment_text(giant_contract)
    results["massive_contract_volume"] = {
        "passed": len(giant_chunks) >= 400,
        "input_chars": len(giant_contract),
        "chunk_count": len(giant_chunks),
        "duration_sec": round(time.time() - t0, 4),
    }

    # Test 3: Adversarial unicode and script injections
    t0 = time.time()
    adversarial_payloads = [
        "Normal text with \x00 null bytes and \u200b zero-width spaces.",
        "🔥 " * 500 + "Emojis explosion and unicode astral planes 🚀⚖️📜",
        "Arabic RTL text: يجب على المقاول تقديم خدمات البرمجيات بدون تأخير",
        "Hebrew RTL text: הקבלן מתחייב לספק שירותי תוכנה בזמן",
        "'; DROP TABLE clauses; DROP TABLE documents; -- SQL injection",
        "<script>alert('xss');</script><iframe src='javascript:void(0)'>",
        "JSON Injection: {\"override_risk\": \"Zero\", \"isAdmin\": true}",
    ]
    unicode_ok = True
    for payload in adversarial_payloads:
        try:
            chunks = segment_text(payload)
            for c in chunks:
                risk_res = compute_enhanced_clause_risk("Termination for Convenience", 0.85, c)
                if not (0 <= risk_res["risk_score"] <= 100):
                    unicode_ok = False
        except Exception as exc:  # noqa: BLE001
            logger.error("Unicode stress failure on payload: %s", exc)
            unicode_ok = False

    results["adversarial_unicode"] = {
        "passed": unicode_ok,
        "tested_payloads": len(adversarial_payloads),
        "duration_sec": round(time.time() - t0, 4),
    }

    # Test 4: Risk engine numerical boundaries & NaN / Inf stability
    t0 = time.time()
    extremes = [-10.0, -1.0, 0.0, 0.5, 1.0, 2.0, 100.0, float("nan"), float("inf"), float("-inf")]
    risk_extremes_ok = True
    for conf in extremes:
        try:
            res = compute_enhanced_clause_risk("Uncapped Liability", conf, "unlimited liability shall apply")
            score = res.get("risk_score")
            norm = res.get("risk_score_normalized")
            if score is None or not (0 <= score <= 100) or norm is None or not (0.0 <= norm <= 1.0):
                risk_extremes_ok = False
        except Exception as exc:  # noqa: BLE001
            logger.error("Risk boundary failure on conf=%s: %s", conf, exc)
            risk_extremes_ok = False

    results["risk_engine_extremes"] = {
        "passed": risk_extremes_ok,
        "extremes_tested": len(extremes),
        "duration_sec": round(time.time() - t0, 4),
    }

    # Test 5: Redline engine ReDoS and formatting bracket attack
    t0 = time.time()
    redline_ok = True
    try:
        # Catastrophic backtracking attempt
        redos_text = "Either party " + ("may terminate " * 300) + "upon twenty-four (24) hours' written notice."
        res = suggest_redline("Termination for Convenience", redos_text)
        # Template injection attempt
        bracket_text = "Contractor's liability shall not be subject to any limit {__class__} {{payload}} {0}"
        res2 = suggest_redline("Uncapped Liability", bracket_text)
        # Giant word diff (1000 tokens)
        diff = compute_word_diff("term clause " * 500, "amended provision " * 500)
        redline_ok = len(diff) > 0 and (res2 is not None or res is not None)
    except Exception as exc:  # noqa: BLE001
        logger.error("Redline stress failure: %s", exc)
        redline_ok = False

    results["redline_engine_stress"] = {
        "passed": redline_ok,
        "duration_sec": round(time.time() - t0, 4),
    }

    # Test 6: Corrupted and edge-case file uploads via API test client
    t0 = time.time()
    corrupted_cases = [
        ("empty.txt", b"", 422, "NO_TEXT_EXTRACTED"),
        ("whitespace.txt", b"   \n\n\t\t\n   ", 422, "NO_TEXT_EXTRACTED"),
        ("fake.pdf", b"%PDF-1.4\ncorrupted binary stream \x00\xff\xfe garbage", 422, "NO_TEXT_EXTRACTED"),
        ("fake.docx", b"PK\x03\x04 corrupt zip payload not real docx", 422, "NO_TEXT_EXTRACTED"),
        ("bad_ext.exe", b"MZ binary executable code", 400, "UNSUPPORTED_FILE_TYPE"),
        ("oversized.txt", b"A" * (11 * 1024 * 1024), 413, "FILE_TOO_LARGE"),
    ]
    api_errors_ok = True
    with TestClient(app) as client:
        for fname, payload, exp_status, exp_code in corrupted_cases:
            resp = client.post(
                "/api/v1/analyze",
                files={"file": (fname, io.BytesIO(payload), "application/octet-stream")},
            )
            if resp.status_code != exp_status:
                logger.error("Expected %d for %s, got %d", exp_status, fname, resp.status_code)
                api_errors_ok = False
            data = resp.json()
            if "error" not in data or data["error"].get("code") != exp_code:
                logger.error("Expected error code %s for %s, got %s", exp_code, fname, data)
                api_errors_ok = False

    results["corrupted_uploads_api"] = {
        "passed": api_errors_ok,
        "cases_tested": len(corrupted_cases),
        "duration_sec": round(time.time() - t0, 4),
    }

    return results

"""Segmenter parity test:
Asserts that backend segmenter output equals the training segmentation on a fixed sample contract.
"""
from pathlib import Path
import pytest
from app.services.segmenter import resegment_contract as backend_resegment
from ml.src.resegment_and_audit import resegment_contract as training_resegment
from transformers import AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CONTRACT_PATH = PROJECT_ROOT / "clauseguard-testkit" / "contracts" / "DOC-01_freelance_agreement.txt"


def test_segmenter_parity_on_sample_contract():
    """Verify backend segmenter exactly matches training segmentation on DOC-01."""
    assert SAMPLE_CONTRACT_PATH.exists(), f"Sample contract not found at {SAMPLE_CONTRACT_PATH}"
    with open(SAMPLE_CONTRACT_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    
    backend_units = backend_resegment(text, tokenizer=tokenizer, max_tokens=256)
    training_units = training_resegment(text, tokenizer=tokenizer, max_tokens=256)
    
    assert len(backend_units) == len(training_units), (
        f"Unit count mismatch: backend {len(backend_units)} vs training {len(training_units)}"
    )
    
    for i, (b, t) in enumerate(zip(backend_units, training_units)):
        assert b["char_start"] == t["char_start"], f"Unit {i} char_start mismatch: {b['char_start']} vs {t['char_start']}"
        assert b["char_end"] == t["char_end"], f"Unit {i} char_end mismatch: {b['char_end']} vs {t['char_end']}"
        assert b["text_raw"] == t["text_raw"], f"Unit {i} text_raw mismatch"
        assert b["text"] == t["text"], f"Unit {i} text mismatch"

"""Unit test asserting dataset offset integrity:
For every unit in train.csv, val.csv, val_natural.csv, and test_natural.csv,
the raw CUAD context text at [char_start:char_end] (with blanked headers/footers)
must equal the unit raw text.
Skips cleanly if CUAD raw data or processed data files are absent.
"""
import json
from pathlib import Path
import pytest
import pandas as pd
try:
    from app.services.segmenter import strip_headers_footers_offset_preserving
except ModuleNotFoundError:
    from backend.app.services.segmenter import strip_headers_footers_offset_preserving

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
RAW_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"


@pytest.fixture(scope="module")
def cuad_raw_contexts():
    if not RAW_PATH.exists():
        pytest.skip(f"CUAD raw dataset not found at {RAW_PATH}")
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        cuad_data = json.load(f)["data"]
    return {entry.get("title"): entry["paragraphs"][0]["context"] for entry in cuad_data}


def check_file_offsets(file_path: Path, cuad_raw: dict[str, str]) -> list[dict]:
    if not file_path.exists():
        pytest.skip(f"Data file not found at {file_path}")
    df = pd.read_csv(file_path)
    mismatches = []
    for idx, row in df.iterrows():
        contract = row["contract"]
        c_s = int(row["char_start"])
        c_e = int(row["char_end"])
        unit_text = str(row["text_raw"]) if ("text_raw" in row and pd.notna(row["text_raw"])) else str(row["text"])
        
        raw_ctx = cuad_raw.get(contract)
        if raw_ctx is None:
            mismatches.append({"row": idx, "contract": contract, "error": "contract not found"})
            continue
            
        clean_ctx = strip_headers_footers_offset_preserving(raw_ctx)
        if c_s < 0 or c_e > len(clean_ctx) or c_s >= c_e:
            mismatches.append({
                "row": idx,
                "contract": contract,
                "char_start": c_s,
                "char_end": c_e,
                "error": "invalid bounds",
                "text": unit_text[:50],
            })
            continue
            
        if clean_ctx[c_s:c_e] != unit_text:
            mismatches.append({
                "row": idx,
                "contract": contract,
                "char_start": c_s,
                "char_end": c_e,
                "error": "text mismatch",
                "text": unit_text[:50],
            })
    return mismatches


def test_positive_units_non_negative_offsets(cuad_raw_contexts):
    """Assert that all validly-indexed units match exact text at offsets."""
    train_path = PROCESSED_DIR / "train.csv"
    if not train_path.exists():
        pytest.skip(f"train.csv not found at {train_path}")
    train_df = pd.read_csv(train_path)
    valid_train = train_df[train_df["char_start"] >= 0]
    for _, row in valid_train.iterrows():
        raw_ctx = cuad_raw_contexts[row["contract"]]
        clean_ctx = strip_headers_footers_offset_preserving(raw_ctx)
        s, e = int(row["char_start"]), int(row["char_end"])
        unit_text = str(row["text_raw"]) if ("text_raw" in row and pd.notna(row["text_raw"])) else str(row["text"])
        assert clean_ctx[s:e] == unit_text


def test_dataset_offset_integrity(cuad_raw_contexts):
    """Assert zero offset mismatches across all processed splits."""
    for fname in ["train.csv", "val.csv", "val_natural.csv", "test_natural.csv"]:
        fpath = PROCESSED_DIR / fname
        mismatches = check_file_offsets(fpath, cuad_raw_contexts)
        assert len(mismatches) == 0, f"{fname} has {len(mismatches)} offset mismatches: {mismatches[:3]}"

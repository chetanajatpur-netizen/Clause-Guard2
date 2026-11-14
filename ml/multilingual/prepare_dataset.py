"""Multilingual Dataset Preparation Pipeline for ClauseGuard / ClauseWise.

Extracts legal paragraphs/segments from:
1. Kannada Dataset: Karnataka State Gazette statutory notifications
2. Hindi Dataset: Delhi High Court commercial judgments & rent control orders
3. English Dataset: Commercial contracts from CUAD

Enforces strict DOCUMENT-LEVEL split (70% train, 15% val, 15% test) with seed 42:
- Zero document overlap across splits
- Preserves document IDs, language labels, character lengths, and source metadata
- Outputs git-ignored JSONL files:
  - ml/multilingual/data/train.jsonl
  - ml/multilingual/data/val.jsonl
  - ml/multilingual/data/test.jsonl
  - ml/multilingual/data/split_metadata.json
"""
import argparse
import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import pypdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_dataset")

RANDOM_SEED = 42

DEFAULT_KANNADA_DIR = "/Users/chetanajatpur/Documents/Kannada dataset"
DEFAULT_HINDI_DIR = "/Users/chetanajatpur/Documents/HINDI dataset"
DEFAULT_ENGLISH_DIR = "/Users/chetanajatpur/Desktop/clauseguard/ml/data/processed"
DEFAULT_OUTPUT_DIR = "/Users/chetanajatpur/Desktop/clauseguard/ml/multilingual/data"


def clean_text(text: str) -> str:
    """Normalize whitespace and strip extraneous controls."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_segments(pdf_path: str, doc_id: str, language: str) -> List[Dict[str, Any]]:
    """Extract clause-sized segments (50 to 2000 chars) from a PDF file."""
    reader = pypdf.PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        page_text = page.extract_text() or ""
        full_text += "\n" + page_text

    full_text = clean_text(full_text)
    # Split paragraphs by blank lines
    raw_paras = re.split(r"\n\s*\n+", full_text)
    segments = []
    seg_idx = 0

    for p in raw_paras:
        p_clean = p.strip()
        # Filter out trivial fragments, page numbers, or single words
        if len(p_clean) < 50:
            continue
        
        # If segment is very long (> 2000 chars), split by line boundaries
        if len(p_clean) > 2000:
            sub_chunks = []
            curr_chunk = []
            curr_len = 0
            for line in p_clean.split("\n"):
                line_len = len(line)
                if curr_len + line_len > 1500 and curr_chunk:
                    sub_chunks.append("\n".join(curr_chunk))
                    curr_chunk = [line]
                    curr_len = line_len
                else:
                    curr_chunk.append(line)
                    curr_len += line_len + 1
            if curr_chunk:
                sub_chunks.append("\n".join(curr_chunk))
            
            for sc in sub_chunks:
                sc_str = sc.strip()
                if len(sc_str) >= 50:
                    segments.append({
                        "id": f"{doc_id}_seg_{seg_idx}",
                        "doc_id": doc_id,
                        "language": language,
                        "text": sc_str,
                        "char_length": len(sc_str),
                    })
                    seg_idx += 1
        else:
            segments.append({
                "id": f"{doc_id}_seg_{seg_idx}",
                "doc_id": doc_id,
                "language": language,
                "text": p_clean,
                "char_length": len(p_clean),
            })
            seg_idx += 1

    return segments


def split_document_ids(doc_ids: List[str], train_ratio: float = 0.70, val_ratio: float = 0.15, seed: int = RANDOM_SEED) -> Tuple[List[str], List[str], List[str]]:
    """Deterministically partition document IDs into train, val, test."""
    rng = random.Random(seed)
    shuffled = sorted(doc_ids)  # Sort first for deterministic shuffling
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = max(1, int(round(n * train_ratio)))
    n_val = max(1, int(round(n * val_ratio)))
    
    # Adjust to ensure test gets at least 1 document if n >= 3
    if n >= 3 and (n - n_train - n_val) < 1:
        if n_train > 1:
            n_train -= 1
        else:
            n_val -= 1
            
    train_docs = shuffled[:n_train]
    val_docs = shuffled[n_train:n_train + n_val]
    test_docs = shuffled[n_train + n_val:]
    return train_docs, val_docs, test_docs


def prepare_datasets(
    kannada_dir: str = DEFAULT_KANNADA_DIR,
    hindi_dir: str = DEFAULT_HINDI_DIR,
    english_dir: str = DEFAULT_ENGLISH_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    """Execute end-to-end dataset preparation and write split JSONLs."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Kannada Documents
    k_files = [f for f in sorted(os.listdir(kannada_dir)) if f.endswith(".pdf")]
    logger.info(f"Loaded {len(k_files)} Kannada PDF documents from {kannada_dir}")
    k_train_docs, k_val_docs, k_test_docs = split_document_ids(k_files, seed=RANDOM_SEED)

    # 2. Hindi Documents (only unique Hindi judgments document_with_logo*)
    h_files = [f for f in sorted(os.listdir(hindi_dir)) if f.startswith("document_with_logo") and f.endswith(".pdf")]
    logger.info(f"Loaded {len(h_files)} Hindi PDF documents from {hindi_dir}")
    h_train_docs, h_val_docs, h_test_docs = split_document_ids(h_files, seed=RANDOM_SEED)

    # Extract Segments per document
    k_doc_segs = {}
    for f in k_files:
        k_doc_segs[f] = extract_pdf_segments(os.path.join(kannada_dir, f), f, "kannada")

    h_doc_segs = {}
    for f in h_files:
        h_doc_segs[f] = extract_pdf_segments(os.path.join(hindi_dir, f), f, "hindi")

    # 3. English Segments (Sample from existing train.csv, val.csv, test.csv)
    en_train_df = pd.read_csv(os.path.join(english_dir, "train.csv"))
    en_val_df = pd.read_csv(os.path.join(english_dir, "val.csv"))
    en_test_df = pd.read_csv(os.path.join(english_dir, "test.csv"))

    # Sample balanced counts matching Kannada & Hindi (~300 train, ~50 val, ~60 test)
    rng = random.Random(RANDOM_SEED)
    
    en_train_contracts = sorted(en_train_df["contract"].unique())
    en_val_contracts = sorted(en_val_df["contract"].unique())
    en_test_contracts = sorted(en_test_df["contract"].unique())

    # Sample distinct contracts
    rng.shuffle(en_train_contracts)
    rng.shuffle(en_val_contracts)
    rng.shuffle(en_test_contracts)

    selected_en_train_contracts = en_train_contracts[:25]
    selected_en_val_contracts = en_val_contracts[:6]
    selected_en_test_contracts = en_test_contracts[:6]

    en_train_segs = []
    for _, row in en_train_df[en_train_df["contract"].isin(selected_en_train_contracts)].iterrows():
        t = str(row["text"]).strip()
        if len(t) >= 50:
            en_train_segs.append({
                "id": f"en_train_{len(en_train_segs)}",
                "doc_id": row["contract"],
                "language": "english",
                "text": t,
                "char_length": len(t),
            })

    en_val_segs = []
    for _, row in en_val_df[en_val_df["contract"].isin(selected_en_val_contracts)].iterrows():
        t = str(row["text"]).strip()
        if len(t) >= 50:
            en_val_segs.append({
                "id": f"en_val_{len(en_val_segs)}",
                "doc_id": row["contract"],
                "language": "english",
                "text": t,
                "char_length": len(t),
            })

    en_test_segs = []
    for _, row in en_test_df[en_test_df["contract"].isin(selected_en_test_contracts)].iterrows():
        t = str(row["text"]).strip()
        if len(t) >= 50:
            en_test_segs.append({
                "id": f"en_test_{len(en_test_segs)}",
                "doc_id": row["contract"],
                "language": "english",
                "text": t,
                "char_length": len(t),
            })

    # Assemble Splits
    train_data = []
    val_data = []
    test_data = []

    # Kannada
    for d in k_train_docs:
        train_data.extend(k_doc_segs[d])
    for d in k_val_docs:
        val_data.extend(k_doc_segs[d])
    for d in k_test_docs:
        test_data.extend(k_doc_segs[d])

    # Hindi
    for d in h_train_docs:
        train_data.extend(h_doc_segs[d])
    for d in h_val_docs:
        val_data.extend(h_doc_segs[d])
    for d in h_test_docs:
        test_data.extend(h_doc_segs[d])

    # English
    train_data.extend(en_train_segs[:len(train_data) // 2])  # Balanced proportion
    val_data.extend(en_val_segs[:len(val_data) // 2])
    test_data.extend(en_test_segs[:len(test_data) // 2])

    # Shuffle each split deterministically
    rng.shuffle(train_data)
    rng.shuffle(val_data)
    rng.shuffle(test_data)

    # Write JSONLs
    for split_name, dataset in [("train", train_data), ("val", val_data), ("test", test_data)]:
        split_file = out_path / f"{split_name}.jsonl"
        with open(split_file, "w", encoding="utf-8") as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Wrote {len(dataset)} items to {split_file}")

    metadata = {
        "random_seed": RANDOM_SEED,
        "kannada": {
            "total_documents": len(k_files),
            "train_documents": k_train_docs,
            "val_documents": k_val_docs,
            "test_documents": k_test_docs,
            "total_segments": sum(len(s) for s in k_doc_segs.values()),
        },
        "hindi": {
            "total_documents": len(h_files),
            "train_documents": h_train_docs,
            "val_documents": h_val_docs,
            "test_documents": h_test_docs,
            "total_segments": sum(len(s) for s in h_doc_segs.values()),
        },
        "english": {
            "train_contracts": selected_en_train_contracts,
            "val_contracts": selected_en_val_contracts,
            "test_contracts": selected_en_test_contracts,
            "total_segments": len(en_train_segs) + len(en_val_segs) + len(en_test_segs),
        },
        "splits": {
            "train": {
                "total": len(train_data),
                "kannada": sum(1 for x in train_data if x["language"] == "kannada"),
                "hindi": sum(1 for x in train_data if x["language"] == "hindi"),
                "english": sum(1 for x in train_data if x["language"] == "english"),
            },
            "val": {
                "total": len(val_data),
                "kannada": sum(1 for x in val_data if x["language"] == "kannada"),
                "hindi": sum(1 for x in val_data if x["language"] == "hindi"),
                "english": sum(1 for x in val_data if x["language"] == "english"),
            },
            "test": {
                "total": len(test_data),
                "kannada": sum(1 for x in test_data if x["language"] == "kannada"),
                "hindi": sum(1 for x in test_data if x["language"] == "hindi"),
                "english": sum(1 for x in test_data if x["language"] == "english"),
            },
        },
    }

    meta_file = out_path / "split_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved split metadata to {meta_file}")

    return metadata


if __name__ == "__main__":
    meta = prepare_datasets()
    print("\n=== DATASET SPLIT COMPLETE ===")
    print(json.dumps(meta["splits"], indent=2))

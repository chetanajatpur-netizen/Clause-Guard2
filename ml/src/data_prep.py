"""CUAD dataset preparation for ClauseGuard.

Loads the CUAD_v1.json dataset, maps to the 10 target clause types,
segments contracts into clause-sized chunks, labels them with ground-truth spans,
downsamples 'No Clause', and splits by contract (70/15/15, seed 42) to prevent data leakage.
"""
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

CUAD_TO_CLAUSE_TYPE: dict[str, str] = {
    "Non-Compete": "Non-Compete",
    "Exclusivity": "Exclusivity",
    "Termination For Convenience": "Termination for Convenience",
    "Anti-Assignment": "Anti-Assignment",
    "Uncapped Liability": "Uncapped Liability",
    "Cap On Liability": "Cap on Liability",
    "Liquidated Damages": "Liquidated Damages",
    "Audit Rights": "Audit Rights",
    "Change Of Control": "Change of Control",
    "Ip Ownership Assignment": "IP Ownership Assignment",
}


def load_cuad_raw() -> dict[str, Any]:
    """Load local CUAD_v1.json file."""
    print(f"Loading CUAD from {RAW_PATH}...")
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data['data'])} contracts from CUAD.")
    return data


def extract_category_from_question(question: str) -> str | None:
    """Extract quoted category name from CUAD question."""
    match = re.search(r'"([^"]+)"', question)
    if match:
        return match.group(1)
    return None


def segment_contract_with_spans(
    text: str,
    min_len: int = 50,
    max_len: int = 2000,
) -> list[tuple[str, int, int]]:
    """Segment contract text into chunks and retain [start, end] char offsets."""
    pattern = re.compile(
        r'\n\s*\n|\n(?=[A-Z][A-Z\s]{3,})|\n(?=\d+\.\s)|\n(?=Section\s+\d)|\n(?=ARTICLE\s+)',
        re.MULTILINE,
    )
    
    # Find all paragraph boundary split points
    splits = [0]
    for m in pattern.finditer(text):
        splits.append(m.start())
        splits.append(m.end())
    splits.append(len(text))
    
    # Gather raw slices
    raw_spans = []
    for i in range(0, len(splits) - 1, 2):
        s, e = splits[i], splits[i+1]
        chunk_str = text[s:e].strip()
        if chunk_str:
            # find actual trimmed boundaries
            actual_start = text.find(chunk_str, s)
            actual_end = actual_start + len(chunk_str)
            raw_spans.append((chunk_str, actual_start, actual_end))
    
    # Merge tiny chunks (< min_len)
    merged: list[tuple[str, int, int]] = []
    buffer_text = ""
    buf_start = -1
    buf_end = -1
    
    for c_text, s, e in raw_spans:
        if len(buffer_text) + len(c_text) < min_len:
            if not buffer_text:
                buffer_text = c_text
                buf_start = s
                buf_end = e
            else:
                buffer_text = buffer_text + " " + c_text
                buf_end = e
        else:
            if buffer_text:
                merged.append((buffer_text, buf_start, buf_end))
            buffer_text = c_text
            buf_start = s
            buf_end = e
            
    if buffer_text:
        merged.append((buffer_text, buf_start, buf_end))
        
    # Split huge chunks (> max_len)
    final_chunks: list[tuple[str, int, int]] = []
    for c_text, s, e in merged:
        if len(c_text) <= max_len:
            final_chunks.append((c_text, s, e))
        else:
            sentences = re.split(r'(?<=[.!?])\s+', c_text)
            curr = ""
            c_start = s
            for sent in sentences:
                if len(curr) + len(sent) > max_len and curr:
                    final_chunks.append((curr.strip(), c_start, c_start + len(curr.strip())))
                    c_start += len(curr) + 1
                    curr = sent
                else:
                    curr = (curr + " " + sent).strip()
            if curr:
                final_chunks.append((curr.strip(), c_start, c_start + len(curr.strip())))
                
    return [(t, s, e) for t, s, e in final_chunks if len(t) >= 20]


def process_cuad_dataset(data: dict[str, Any]) -> pd.DataFrame:
    """Parse CUAD contracts, extract answers, segment, and label."""
    records = []
    
    for doc in data["data"]:
        contract_title = doc.get("title", "Unknown")
        for para in doc["paragraphs"]:
            context = para["context"]
            
            # Extract answer spans for our 10 clause categories
            spans_by_type: dict[str, list[tuple[int, int]]] = defaultdict(list)
            for qa in para["qas"]:
                cat = extract_category_from_question(qa["question"])
                if cat and cat in CUAD_TO_CLAUSE_TYPE:
                    clause_type = CUAD_TO_CLAUSE_TYPE[cat]
                    for ans in qa.get("answers", []):
                        a_start = ans["answer_start"]
                        a_end = a_start + len(ans["text"])
                        if a_end > a_start:
                            spans_by_type[clause_type].append((a_start, a_end))
            
            # Segment the contract
            chunks = segment_contract_with_spans(context)
            
            for chunk_text, c_start, c_end in chunks:
                best_label = "No Clause"
                best_overlap = 0
                
                # Check overlap against all target spans
                for clause_type, span_list in spans_by_type.items():
                    for s_start, s_end in span_list:
                        overlap = min(c_end, s_end) - max(c_start, s_start)
                        if overlap > 15 and overlap > best_overlap:
                            best_overlap = overlap
                            best_label = clause_type
                
                records.append({
                    "contract_id": contract_title,
                    "text": chunk_text,
                    "label": best_label,
                })
                
    df = pd.DataFrame(records)
    print(f"Total extracted segments: {len(df)}")
    print("Initial label counts:")
    print(df["label"].value_counts().to_string())
    return df


def downsample_no_clause(df: pd.DataFrame, max_ratio: float = 3.0) -> pd.DataFrame:
    """Downsample 'No Clause' to max_ratio * average size of other classes."""
    label_counts = df["label"].value_counts()
    other_counts = label_counts.drop("No Clause", errors="ignore")
    
    avg_other = int(other_counts.mean())
    max_no_clause = int(avg_other * max_ratio)
    
    no_clause_df = df[df["label"] == "No Clause"]
    other_df = df[df["label"] != "No Clause"]
    
    if len(no_clause_df) > max_no_clause:
        print(f"\nDownsampling 'No Clause' from {len(no_clause_df)} to {max_no_clause} (avg other={avg_other})")
        no_clause_df = no_clause_df.sample(n=max_no_clause, random_state=SEED)
        
    result = pd.concat([other_df, no_clause_df], ignore_index=True)
    return result.sample(frac=1, random_state=SEED).reset_index(drop=True)


def split_by_contract(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split dataset BY CONTRACT (70/15/15) to guarantee zero data leakage."""
    contracts = sorted(df["contract_id"].unique().tolist())
    rng = random.Random(SEED)
    rng.shuffle(contracts)
    
    n = len(contracts)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    
    train_contracts = set(contracts[:n_train])
    val_contracts = set(contracts[n_train:n_train + n_val])
    test_contracts = set(contracts[n_train + n_val:])
    
    # Assert zero contract overlap across splits
    assert len(train_contracts & val_contracts) == 0, "Train and Val contract overlap!"
    assert len(train_contracts & test_contracts) == 0, "Train and Test contract overlap!"
    assert len(val_contracts & test_contracts) == 0, "Val and Test contract overlap!"
    
    train_df = df[df["contract_id"].isin(train_contracts)].copy().reset_index(drop=True)
    val_df = df[df["contract_id"].isin(val_contracts)].copy().reset_index(drop=True)
    test_df = df[df["contract_id"].isin(test_contracts)].copy().reset_index(drop=True)
    
    print(f"\nSplit by contract ({n} contracts total):")
    print(f"  Train: {len(train_df)} samples ({len(train_contracts)} contracts)")
    print(f"  Val:   {len(val_df)} samples ({len(val_contracts)} contracts)")
    print(f"  Test:  {len(test_df)} samples ({len(test_contracts)} contracts)")
    
    return train_df, val_df, test_df


def save_eda_plots(df: pd.DataFrame) -> None:
    """Save class distribution and text length histogram visualizations."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Class distribution plot
    fig, ax = plt.subplots(figsize=(12, 6))
    counts = df["label"].value_counts()
    counts.plot(kind="bar", ax=ax, color="#4F46E5", edgecolor="white")
    ax.set_title("Clause Type Distribution", fontsize=15, fontweight="bold")
    ax.set_xlabel("Clause Type", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "class_distribution.png", dpi=150)
    plt.close(fig)
    print(f"Saved class distribution plot to {ARTIFACTS_DIR / 'class_distribution.png'}")
    
    # Text length histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    lengths = df["text"].str.len()
    ax.hist(lengths, bins=50, color="#4F46E5", edgecolor="white", alpha=0.85)
    median_len = lengths.median()
    ax.axvline(x=median_len, color="#DC2626", linestyle="--", label=f"Median: {median_len:.0f}")
    ax.set_title("Clause Text Length Distribution", fontsize=15, fontweight="bold")
    ax.set_xlabel("Character Count", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.legend()
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "text_length_histogram.png", dpi=150)
    plt.close(fig)
    print(f"Saved text length histogram to {ARTIFACTS_DIR / 'text_length_histogram.png'}")


def main() -> None:
    """Execute complete data preparation pipeline."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Load raw data
    cuad_data = load_cuad_raw()
    
    # 2. Process and label segments
    df = process_cuad_dataset(cuad_data)
    
    # 3. Downsample 'No Clause'
    df = downsample_no_clause(df, max_ratio=3.0)
    
    # 4. Generate EDA plots
    save_eda_plots(df)
    
    # 5. Split by contract
    train_df, val_df, test_df = split_by_contract(df)
    
    # 6. Verify all 11 classes exist in train
    all_classes = set(CUAD_TO_CLAUSE_TYPE.values()) | {"No Clause"}
    train_classes = set(train_df["label"].unique())
    print(f"\nUnique classes in train: {len(train_classes)} / {len(all_classes)}")
    assert len(train_classes) == 11, f"Missing classes in train split: {all_classes - train_classes}"
    
    print("\nTrain class distribution:")
    print(train_df["label"].value_counts().to_string())
    print("\nVal class distribution:")
    print(val_df["label"].value_counts().to_string())
    print("\nTest class distribution:")
    print(test_df["label"].value_counts().to_string())
    
    # 7. Save processed CSVs
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)
    print(f"\nSaved processed datasets to {PROCESSED_DIR}/")
    
    # 8. Save dataset statistics
    stats = {
        "source": "theatticusproject/cuad (CUAD_v1.json)",
        "total_contracts": cuad_data["data"].__len__(),
        "total_segments_after_downsampling": len(df),
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "class_counts_train": train_df["label"].value_counts().to_dict(),
        "class_counts_val": val_df["label"].value_counts().to_dict(),
        "class_counts_test": test_df["label"].value_counts().to_dict(),
    }
    with open(ARTIFACTS_DIR / "dataset_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Saved dataset stats to {ARTIFACTS_DIR / 'dataset_stats.json'}")


if __name__ == "__main__":
    main()

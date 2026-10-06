"""CUAD dataset preparation for ClauseGuard.

Loads the CUAD dataset from HuggingFace, maps to our 10 clause types,
segments contracts into clause-sized chunks, labels them, downsamples
'No Clause', and splits by contract.
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datasets import load_dataset

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

# Our 10 clause types mapped from CUAD category questions.
# CUAD has 41 question categories. Each question text contains the category name.
# We map the relevant ones to our simplified names.
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


def load_cuad() -> Any:
    """Load CUAD dataset from HuggingFace and inspect format."""
    print("Loading CUAD dataset from HuggingFace...")
    ds = load_dataset("theatticusproject/cuad-qa", trust_remote_code=True)
    print(f"Dataset splits: {list(ds.keys())}")
    print(f"Features: {ds['train'].features}")
    print(f"Number of examples: {len(ds['train'])}")
    
    # Print a sample to understand the format
    sample = ds['train'][0]
    print(f"\nSample keys: {list(sample.keys())}")
    print(f"Question: {sample.get('question', 'N/A')[:100]}")
    print(f"Context length: {len(sample.get('context', ''))}")
    if 'answers' in sample:
        print(f"Answers: {sample['answers']}")
    
    return ds


def extract_category_from_question(question: str) -> str | None:
    """Extract CUAD category name from the question text.
    
    CUAD questions are like 'Highlight the parts (if any) of this contract
    related to "Non-Compete" that should be reviewed by a lawyer.'
    """
    # Try to extract quoted category name
    import re
    match = re.search(r'"([^"]+)"', question)
    if match:
        return match.group(1)
    return None


def get_cuad_categories(ds: Any) -> list[str]:
    """Get all unique category names from CUAD questions."""
    categories = set()
    for example in ds['train']:
        cat = extract_category_from_question(example['question'])
        if cat:
            categories.add(cat)
    cats = sorted(categories)
    print(f"\nFound {len(cats)} CUAD categories:")
    for c in cats:
        print(f"  - {c}")
    return cats


def segment_text(text: str, min_len: int = 50, max_len: int = 2000) -> list[str]:
    """Split contract text into clause-sized chunks.
    
    Strategy: split on double newlines (paragraph boundaries),
    merge tiny chunks, split huge chunks at sentence boundaries.
    """
    # Split on double newlines or section-like patterns
    import re
    raw_chunks = re.split(r'\n\s*\n|\n(?=[A-Z][A-Z\s]{3,})|\n(?=\d+\.\s)', text)
    
    chunks: list[str] = []
    buffer = ""
    
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        
        if len(buffer) + len(chunk) < min_len:
            buffer = (buffer + " " + chunk).strip()
            continue
        
        if buffer:
            chunks.append(buffer)
            buffer = ""
        
        if len(chunk) > max_len:
            # Split at sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', chunk)
            sub_buffer = ""
            for sent in sentences:
                if len(sub_buffer) + len(sent) > max_len and sub_buffer:
                    chunks.append(sub_buffer.strip())
                    sub_buffer = sent
                else:
                    sub_buffer = (sub_buffer + " " + sent).strip()
            if sub_buffer:
                chunks.append(sub_buffer.strip())
        else:
            chunks.append(chunk)
    
    if buffer:
        chunks.append(buffer)
    
    # Filter out very tiny chunks
    return [c for c in chunks if len(c) >= 20]


def label_chunks(
    chunks: list[str],
    annotations: dict[str, list[str]],
) -> list[tuple[str, str]]:
    """Label each chunk with a clause type based on annotation overlap.
    
    Args:
        chunks: List of text chunks from segmentation.
        annotations: Dict mapping our clause type names to lists of
                     annotated answer spans for that type.
    
    Returns:
        List of (chunk_text, label) tuples.
    """
    labeled: list[tuple[str, str]] = []
    
    for chunk in chunks:
        chunk_lower = chunk.lower()
        best_label = "No Clause"
        best_overlap = 0
        
        for clause_type, spans in annotations.items():
            for span in spans:
                span_lower = span.lower().strip()
                if not span_lower:
                    continue
                # Check if span overlaps with chunk
                if span_lower in chunk_lower or chunk_lower in span_lower:
                    overlap = min(len(span_lower), len(chunk_lower))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_label = clause_type
        
        labeled.append((chunk, best_label))
    
    return labeled


def build_dataset(ds: Any) -> pd.DataFrame:
    """Process CUAD into a labeled clause dataset."""
    print("\nBuilding clause-level dataset...")
    
    # Group by context (contract) to get all annotations per contract
    contracts: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "context": "",
        "annotations": defaultdict(list)
    })
    
    for example in ds['train']:
        context = example['context']
        question = example['question']
        answers = example['answers']
        
        # Use first 200 chars as contract ID (context is the full contract)
        contract_id = context[:200]
        contracts[contract_id]["context"] = context
        
        # Extract category and map to our types
        cuad_cat = extract_category_from_question(question)
        if cuad_cat and cuad_cat in CUAD_TO_CLAUSE_TYPE:
            our_type = CUAD_TO_CLAUSE_TYPE[cuad_cat]
            if 'text' in answers and answers['text']:
                for ans_text in answers['text']:
                    if ans_text.strip():
                        contracts[contract_id]["annotations"][our_type].append(ans_text)
    
    print(f"Found {len(contracts)} unique contracts")
    
    # Segment and label
    all_rows: list[dict[str, Any]] = []
    
    for contract_id, contract_data in contracts.items():
        context = contract_data["context"]
        annotations = dict(contract_data["annotations"])
        
        chunks = segment_text(context)
        labeled = label_chunks(chunks, annotations)
        
        for chunk_text, label in labeled:
            all_rows.append({
                "contract_id": contract_id,
                "text": chunk_text,
                "label": label,
            })
    
    df = pd.DataFrame(all_rows)
    print(f"Total labeled chunks: {len(df)}")
    print(f"\nLabel distribution:")
    print(df['label'].value_counts().to_string())
    
    return df


def downsample_no_clause(df: pd.DataFrame, max_ratio: float = 3.0) -> pd.DataFrame:
    """Downsample 'No Clause' to at most max_ratio * avg other class size."""
    label_counts = df['label'].value_counts()
    other_counts = label_counts.drop("No Clause", errors="ignore")
    
    if len(other_counts) == 0:
        return df
    
    avg_other = int(other_counts.mean())
    max_no_clause = int(avg_other * max_ratio)
    
    no_clause_df = df[df['label'] == "No Clause"]
    other_df = df[df['label'] != "No Clause"]
    
    if len(no_clause_df) > max_no_clause:
        print(f"\nDownsampling 'No Clause' from {len(no_clause_df)} to {max_no_clause}")
        no_clause_df = no_clause_df.sample(n=max_no_clause, random_state=SEED)
    
    result = pd.concat([other_df, no_clause_df], ignore_index=True)
    return result.sample(frac=1, random_state=SEED).reset_index(drop=True)


def split_by_contract(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split dataset by contract to avoid data leakage.
    
    Same contract never appears in multiple splits.
    """
    contracts = df['contract_id'].unique().tolist()
    random.shuffle(contracts)
    
    n = len(contracts)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    
    train_contracts = set(contracts[:n_train])
    val_contracts = set(contracts[n_train:n_train + n_val])
    test_contracts = set(contracts[n_train + n_val:])
    
    # Verify no overlap
    assert len(train_contracts & val_contracts) == 0, "Train/val overlap!"
    assert len(train_contracts & test_contracts) == 0, "Train/test overlap!"
    assert len(val_contracts & test_contracts) == 0, "Val/test overlap!"
    
    train_df = df[df['contract_id'].isin(train_contracts)].copy()
    val_df = df[df['contract_id'].isin(val_contracts)].copy()
    test_df = df[df['contract_id'].isin(test_contracts)].copy()
    
    print(f"\nSplit by contract ({len(contracts)} contracts):")
    print(f"  Train: {len(train_df)} samples ({len(train_contracts)} contracts)")
    print(f"  Val:   {len(val_df)} samples ({len(val_contracts)} contracts)")
    print(f"  Test:  {len(test_df)} samples ({len(test_contracts)} contracts)")
    
    return train_df, val_df, test_df


def save_eda_plots(df: pd.DataFrame) -> None:
    """Save EDA visualizations to artifacts directory."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Class distribution
    fig, ax = plt.subplots(figsize=(12, 6))
    counts = df['label'].value_counts()
    counts.plot(kind='bar', ax=ax, color='#4F46E5', edgecolor='white')
    ax.set_title('Clause Type Distribution', fontsize=16, fontweight='bold')
    ax.set_xlabel('Clause Type', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / 'class_distribution.png', dpi=150)
    plt.close(fig)
    print(f"Saved class distribution plot to {ARTIFACTS_DIR / 'class_distribution.png'}")
    
    # Text length histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    df['text_length'] = df['text'].str.len()
    ax.hist(df['text_length'], bins=50, color='#4F46E5', edgecolor='white', alpha=0.8)
    ax.set_title('Text Length Distribution', fontsize=16, fontweight='bold')
    ax.set_xlabel('Character Length', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.axvline(x=df['text_length'].median(), color='#DC2626', linestyle='--', label=f"Median: {df['text_length'].median():.0f}")
    ax.legend()
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / 'text_length_histogram.png', dpi=150)
    plt.close(fig)
    print(f"Saved text length histogram to {ARTIFACTS_DIR / 'text_length_histogram.png'}")


def main() -> None:
    """Main data preparation pipeline."""
    # Create directories
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load and inspect CUAD
    ds = load_cuad()
    
    # Get and verify categories
    categories = get_cuad_categories(ds)
    
    # Verify our mapping against real categories
    print("\nVerifying clause type mapping:")
    for cuad_name, our_name in CUAD_TO_CLAUSE_TYPE.items():
        found = cuad_name in categories
        status = "✓" if found else "✗ NOT FOUND"
        print(f"  {cuad_name:35s} -> {our_name:30s} [{status}]")
    
    # Build dataset
    df = build_dataset(ds)
    
    # Downsample
    df = downsample_no_clause(df)
    
    print(f"\nAfter downsampling:")
    print(df['label'].value_counts().to_string())
    
    # Save EDA plots
    save_eda_plots(df)
    
    # Split by contract
    train_df, val_df, test_df = split_by_contract(df)
    
    # Print class counts per split
    for name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        print(f"\n{name} class distribution:")
        print(split_df['label'].value_counts().to_string())
    
    # Save CSVs
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)
    print(f"\nSaved processed CSVs to {PROCESSED_DIR}/")
    
    # Save dataset stats
    stats = {
        "total_samples": len(df),
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "num_contracts": df['contract_id'].nunique(),
        "class_counts": df['label'].value_counts().to_dict(),
    }
    with open(ARTIFACTS_DIR / "dataset_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Saved dataset stats to {ARTIFACTS_DIR / 'dataset_stats.json'}")


if __name__ == "__main__":
    main()

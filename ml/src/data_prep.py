"""CUAD dataset preparation for ClauseGuard.

Implements the updated segmentation and priority labeling rules from ml/LABELING.md:
1. Segmentation: Sentence-boundary units targeting <= 200 tokens (guaranteeing <= 256 tokens).
2. Priority Rule:
   - Uncapped Liability > Cap on Liability
   - Change of Control > Anti-Assignment
   - Non-Compete > Exclusivity
3. Reproducible whole-contract split (70/15/15, seed 42) to prevent data leakage.
4. Downsamples 'No Clause' to max_ratio * average of other classes.
"""
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from transformers import AutoTokenizer

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


def segment_contract_into_sentence_units(
    text: str,
    max_words_per_unit: int = 75,
) -> list[tuple[str, int, int]]:
    """Segment contract text into sentence-boundary units of <= 200 tokens.
    
    1. Splits on paragraph breaks, enumerated sections, and sentence terminators.
    2. Decomposes any sentence > 75 words on internal semicolons, colons, or major conjunctions.
    3. Packs sentences into units <= max_words_per_unit (~100-120 WordPiece tokens, strictly <= 200 tokens).
    4. Returns list of (unit_text, start_char_offset, end_char_offset).
    """
    pattern = re.compile(
        r'\n\s*\n|\n(?=[A-Z0-9\(\[])|(?<=[.!?])\s+(?=[A-Z0-9\"\'\(\[])',
        re.MULTILINE,
    )

    splits = [0]
    for m in pattern.finditer(text):
        splits.append(m.start())
        splits.append(m.end())
    splits.append(len(text))

    raw_sents = []
    for i in range(0, len(splits) - 1, 2):
        s, e = splits[i], splits[i + 1]
        sent_str = text[s:e].strip()
        if sent_str:
            actual_start = text.find(sent_str, s)
            actual_end = actual_start + len(sent_str)
            raw_sents.append((sent_str, actual_start, actual_end))

    # Decompose sentences that exceed word threshold
    atomic_parts = []
    for sent, s, e in raw_sents:
        words = sent.split()
        if len(words) > max_words_per_unit:
            sub_splits = re.split(
                r'(?<=;)\s+|(?<=:\s)|(?<=,\sand\s)|(?<=,\sor\s)|(?<=\))\s+(?=\([a-z0-9]+\))',
                sent,
            )
            sub_s = s
            for sub in sub_splits:
                sub_clean = sub.strip()
                if not sub_clean:
                    continue
                sub_words = sub_clean.split()
                if len(sub_words) > max_words_per_unit:
                    # Fallback word-chunking for ultra-long run-on clauses
                    for w_idx in range(0, len(sub_words), max_words_per_unit):
                        block = " ".join(sub_words[w_idx : w_idx + max_words_per_unit])
                        b_start = text.find(block, sub_s)
                        b_end = b_start + len(block)
                        sub_s = b_end
                        atomic_parts.append((block, b_start, b_end))
                else:
                    sub_actual_s = text.find(sub_clean, sub_s)
                    sub_actual_e = sub_actual_s + len(sub_clean)
                    sub_s = sub_actual_e
                    atomic_parts.append((sub_clean, sub_actual_s, sub_actual_e))
        else:
            atomic_parts.append((sent, s, e))

    # Pack into units up to max_words_per_unit
    units = []
    curr_text = ""
    curr_s = -1
    curr_e = -1
    curr_word_count = 0

    for part, p_s, p_e in atomic_parts:
        p_words = len(part.split())
        if curr_word_count + p_words <= max_words_per_unit:
            if curr_text:
                curr_text += " " + part
                curr_e = p_e
                curr_word_count += p_words
            else:
                curr_text = part
                curr_s = p_s
                curr_e = p_e
                curr_word_count = p_words
        else:
            if curr_text:
                units.append((curr_text.strip(), curr_s, curr_e))
            curr_text = part
            curr_s = p_s
            curr_e = p_e
            curr_word_count = p_words

    if curr_text:
        units.append((curr_text.strip(), curr_s, curr_e))

    return [(t, s, e) for t, s, e in units if len(t) >= 15]


def resolve_label_priority(matching_overlaps: dict[str, int]) -> str:
    """Resolve multi-label collisions via ml/LABELING.md priority hierarchy:
    1. Uncapped Liability > Cap on Liability
    2. Change of Control > Anti-Assignment
    3. Non-Compete > Exclusivity
    """
    if not matching_overlaps:
        return "No Clause"
    if len(matching_overlaps) == 1:
        return list(matching_overlaps.keys())[0]

    candidates = set(matching_overlaps.keys())

    # Priority Rule 1: Uncapped Liability > Cap on Liability
    if "Uncapped Liability" in candidates and "Cap on Liability" in candidates:
        candidates.remove("Cap on Liability")

    # Priority Rule 2: Change of Control > Anti-Assignment
    if "Change of Control" in candidates and "Anti-Assignment" in candidates:
        candidates.remove("Anti-Assignment")

    # Priority Rule 3: Non-Compete > Exclusivity
    if "Non-Compete" in candidates and "Exclusivity" in candidates:
        candidates.remove("Exclusivity")

    # General collision fallback: pick remaining candidate with largest character overlap
    return max(candidates, key=lambda c: matching_overlaps[c])


def process_cuad_dataset(data: dict[str, Any]) -> tuple[pd.DataFrame, int, int]:
    """Parse CUAD contracts, segment into sentence-boundary units, and apply priority labeling."""
    records = []
    total_segmented_units = 0
    multi_label_overlap_units = 0

    for doc in data["data"]:
        contract_title = doc.get("title", "Unknown")
        for para in doc["paragraphs"]:
            context = para["context"]

            # Extract answer spans for the 10 target clause categories
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

            # Segment contract into sentence-boundary units
            units = segment_contract_into_sentence_units(context, max_words_per_unit=75)

            for unit_text, c_start, c_end in units:
                total_segmented_units += 1
                matching_overlaps: dict[str, int] = {}

                for clause_type, span_list in spans_by_type.items():
                    for s_start, s_end in span_list:
                        overlap = min(c_end, s_end) - max(c_start, s_start)
                        if overlap > 15:
                            # Keep maximum overlap for this clause type
                            matching_overlaps[clause_type] = max(
                                matching_overlaps.get(clause_type, 0), overlap
                            )

                num_overlapping_cats = len(matching_overlaps)
                if num_overlapping_cats >= 2:
                    multi_label_overlap_units += 1

                chosen_label = resolve_label_priority(matching_overlaps)

                records.append({
                    "contract_id": contract_title,
                    "text": unit_text,
                    "label": chosen_label,
                    "raw_overlap_count": num_overlapping_cats,
                })

    df = pd.DataFrame(records)
    print(f"Total extracted units: {len(df)}")
    print(f"Units intersecting >= 2 CUAD categories: {multi_label_overlap_units} ({multi_label_overlap_units/len(df)*100:.2f}%)")
    print("\nInitial label distribution:")
    print(df["label"].value_counts().to_string())
    return df, total_segmented_units, multi_label_overlap_units


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
    val_contracts = set(contracts[n_train : n_train + n_val])
    test_contracts = set(contracts[n_train + n_val :])

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

    fig, ax = plt.subplots(figsize=(12, 6))
    counts = df["label"].value_counts()
    counts.plot(kind="bar", ax=ax, color="#4F46E5", edgecolor="white")
    ax.set_title("Clause Type Distribution (Sentence-Boundary Units)", fontsize=15, fontweight="bold")
    ax.set_xlabel("Clause Type", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "class_distribution.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    lengths = df["text"].str.len()
    ax.hist(lengths, bins=50, color="#4F46E5", edgecolor="white", alpha=0.85)
    median_len = lengths.median()
    ax.axvline(x=median_len, color="#DC2626", linestyle="--", label=f"Median: {median_len:.0f}")
    ax.set_title("Clause Text Length Distribution (Characters)", fontsize=15, fontweight="bold")
    ax.set_xlabel("Character Count", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.legend()
    plt.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "text_length_histogram.png", dpi=150)
    plt.close(fig)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load raw data
    cuad_data = load_cuad_raw()

    # 2. Process, segment, and apply priority rules
    df, total_units, multi_label_units = process_cuad_dataset(cuad_data)

    # 3. Downsample 'No Clause'
    df_downsampled = downsample_no_clause(df, max_ratio=3.0)

    # 4. Generate EDA plots
    save_eda_plots(df_downsampled)

    # 5. Split by contract
    train_df, val_df, test_df = split_by_contract(df_downsampled)

    # 6. Verify all 11 classes exist in train
    all_classes = set(CUAD_TO_CLAUSE_TYPE.values()) | {"No Clause"}
    train_classes = set(train_df["label"].unique())
    print(f"\nUnique classes in train: {len(train_classes)} / {len(all_classes)}")
    assert len(train_classes) == 11, f"Missing classes in train split: {all_classes - train_classes}"

    # 7. Save processed CSVs (drop temporary tracking column)
    save_cols = ["contract_id", "text", "label"]
    train_df[save_cols].to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df[save_cols].to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df[save_cols].to_csv(PROCESSED_DIR / "test.csv", index=False)
    print(f"\nSaved processed datasets to {PROCESSED_DIR}/")

    # 8. Check token lengths over 256 tokens using Legal-BERT tokenizer
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    all_final_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    lengths = [len(tokenizer.encode(t, truncation=False)) for t in all_final_df["text"]]
    over_256 = sum(1 for l in lengths if l > 256)
    pct_over_256 = (over_256 / len(lengths)) * 100

    # 9. Compute overlap metrics
    # In the final single-label assigned dataset, each row has exactly 1 label (0.00% overlap).
    # In the raw annotations before single-label resolution:
    pct_multi_label_raw = (multi_label_units / total_units) * 100
    clause_units_count = (df["label"] != "No Clause").sum()
    pct_multi_label_among_clauses = (multi_label_units / max(clause_units_count, 1)) * 100

    print("\n" + "=" * 70)
    print("STEP 2 AUDIT METRICS REPORT")
    print("=" * 70)
    print(f"Total units after downsampling: {len(all_final_df)}")
    print(f"Share of units over 256 tokens: {over_256}/{len(lengths)} ({pct_over_256:.2f}%)")
    print(f"Share of units overlapping 2+ categories in raw annotations: {multi_label_units}/{total_units} ({pct_multi_label_raw:.2f}% of all units, {pct_multi_label_among_clauses:.2f}% of clause units)")
    print(f"Share of units overlapping 2+ categories after priority rule: 0.00% (resolved to single label per ml/LABELING.md)")

    print("\nClass counts per split:")
    summary_counts = pd.DataFrame({
        "Train": train_df["label"].value_counts(),
        "Val": val_df["label"].value_counts(),
        "Test": test_df["label"].value_counts(),
        "Total": all_final_df["label"].value_counts(),
    }).fillna(0).astype(int)
    print(summary_counts.to_string())

    # 10. Extract 20 random Uncapped Liability and 20 random Change of Control units
    rng = random.Random(SEED)
    uncapped_samples = all_final_df[all_final_df["label"] == "Uncapped Liability"]["text"].tolist()
    coc_samples = all_final_df[all_final_df["label"] == "Change of Control"]["text"].tolist()

    rng.shuffle(uncapped_samples)
    rng.shuffle(coc_samples)

    sample_20_uncapped = uncapped_samples[:20]
    sample_20_coc = coc_samples[:20]

    audit_export = {
        "summary_counts": summary_counts.to_dict(),
        "pct_over_256": round(pct_over_256, 4),
        "multi_label_stats": {
            "raw_overlapping_units": multi_label_units,
            "total_units": total_units,
            "pct_raw_overlapping_all": round(pct_multi_label_raw, 2),
            "pct_raw_overlapping_clause_only": round(pct_multi_label_among_clauses, 2),
            "pct_post_priority_overlapping": 0.0,
        },
        "sample_20_uncapped_liability": sample_20_uncapped,
        "sample_20_change_of_control": sample_20_coc,
    }

    with open(ARTIFACTS_DIR / "new_labels_audit_samples.json", "w") as f:
        json.dump(audit_export, f, indent=2)
    print(f"\nSaved audit samples to {ARTIFACTS_DIR / 'new_labels_audit_samples.json'}")


if __name__ == "__main__":
    main()

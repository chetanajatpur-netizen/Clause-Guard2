import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from transformers import AutoTokenizer

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

RAW_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
BASELINE_PATH = ARTIFACTS_DIR / "baseline_model.joblib"

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

PRIORITY_PAIRS = [
    ("Uncapped Liability", "Cap on Liability"),
    ("Change of Control", "Anti-Assignment"),
    ("Non-Compete", "Exclusivity"),
]

ALL_CLASSES = sorted(list(set(CUAD_TO_CLAUSE_TYPE.values()))) + ["No Clause"]


def extract_category_from_question(question: str) -> str | None:
    match = re.search(r'"([^"]+)"', question)
    if match:
        return match.group(1)
    return None


# ==============================================================================
# STEP 1: ALIGNMENT AUDIT ON CURRENT SEGMENTATION
# ==============================================================================
def run_alignment_audit(cuad_data: list[dict[str, Any]]) -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("STEP 1: ALIGNMENT AUDIT ON CURRENT SEGMENTATION")
    print("=" * 70)
    
    from ml.src.data_prep import segment_contract_into_sentence_units
    
    results = []
    by_class = defaultdict(lambda: {"span_in_unit": [], "unit_in_span": []})
    
    for entry in cuad_data:
        contract_title = entry.get("title", "")
        for para in entry["paragraphs"]:
            context = para["context"]
            annotations = []
            for qa in para["qas"]:
                cat = extract_category_from_question(qa["question"])
                if not cat or cat not in CUAD_TO_CLAUSE_TYPE:
                    continue
                canonical_cat = CUAD_TO_CLAUSE_TYPE[cat]
                for ans in qa["answers"]:
                    txt = ans["text"]
                    if len(txt) < 20:
                        continue
                    s = ans["answer_start"]
                    e = s + len(txt)
                    annotations.append((canonical_cat, s, e, txt))
            
            units = segment_contract_into_sentence_units(context, max_words_per_unit=75)
            for u_text, u_s, u_e in units:
                matched_overlaps = []
                for cat, a_s, a_e, a_txt in annotations:
                    ov_s = max(u_s, a_s)
                    ov_e = min(u_e, a_e)
                    if ov_e > ov_s:
                        ov_len = ov_e - ov_s
                        span_len = a_e - a_s
                        unit_len = u_e - u_s
                        span_in_u = ov_len / span_len
                        unit_in_span = ov_len / unit_len
                        matched_overlaps.append({
                            "category": cat,
                            "u_text": u_text,
                            "a_text": a_txt,
                            "ov_len": ov_len,
                            "span_in_u": span_in_u,
                            "unit_in_span": unit_in_span,
                            "contract": contract_title,
                        })
                if matched_overlaps:
                    matched_overlaps.sort(key=lambda x: x["ov_len"], reverse=True)
                    top = matched_overlaps[0]
                    results.append(top)
                    by_class[top["category"]]["span_in_unit"].append(top["span_in_u"])
                    by_class[top["category"]]["unit_in_span"].append(top["unit_in_span"])
                    
    print(f"Total positive units analyzed: {len(results)}")
    
    hist_summary = {}
    for cat in sorted(by_class.keys()):
        spans = np.array(by_class[cat]["span_in_unit"])
        units = np.array(by_class[cat]["unit_in_span"])
        s_b = np.histogram(spans, bins=[0, 0.25, 0.50, 0.75, 1.0001])[0].tolist()
        u_b = np.histogram(units, bins=[0, 0.25, 0.50, 0.75, 1.0001])[0].tolist()
        hist_summary[cat] = {
            "count": len(spans),
            "span_in_unit": {
                "mean": float(spans.mean()),
                "median": float(np.median(spans)),
                "bins_0_25_50_75_100": s_b,
            },
            "unit_in_span": {
                "mean": float(units.mean()),
                "median": float(np.median(units)),
                "bins_0_25_50_75_100": u_b,
            },
        }
        print(f"\n-- {cat} (N={len(spans)}) --")
        print(f"  Span in Unit: Mean={spans.mean():.2%}, Median={np.median(spans):.2%} | Bins [0-25%, 25-50%, 50-75%, 75-100%]: {s_b}")
        print(f"  Unit in Span: Mean={units.mean():.2%}, Median={np.median(units):.2%} | Bins [0-25%, 25-50%, 50-75%, 75-100%]: {u_b}")
        
    random.seed(42)
    mismatches = [r for r in results if r["span_in_u"] < 0.50 or r["unit_in_span"] < 0.50]
    sample_mismatches = random.sample(mismatches, 10)
    
    return {
        "hist_summary": hist_summary,
        "sample_mismatches": sample_mismatches,
        "total_positive_units": len(results),
        "total_mismatches_under_50": len(mismatches),
    }


# ==============================================================================
# STEP 2 & 3: RE-SEGMENTATION & NEW 50% LABELLING RULE
# ==============================================================================
from backend.app.services.segmenter import (
    strip_headers_footers_offset_preserving,
    is_placeholder_or_table,
    resegment_contract,
)


def label_units_50pct_rule(
    units: list[dict[str, Any]],
    annotations: list[tuple[str, int, int, str]],
) -> list[dict[str, Any]]:
    """Assign label only if overlap covers >= 50% of annotated span OR >= 50% of unit.
    Ignores annotation spans shorter than 20 characters.
    Then applies priority rule. Keeps overlapping labels in secondary_labels.
    """
    labeled = []
    # Drop annotations shorter than 20 characters per labelling rule
    valid_annots = [a for a in annotations if len(a[3]) >= 20]

    for u in units:
        u_text = u["text"]
        u_text_raw = u["text_raw"]
        u_s = u["char_start"]
        u_e = u["char_end"]
        u_len = u_e - u_s
        qualifying = []
        for cat, a_s, a_e, a_txt in valid_annots:
            ov_s = max(u_s, a_s)
            ov_e = min(u_e, a_e)
            if ov_e > ov_s:
                ov_len = ov_e - ov_s
                span_len = a_e - a_s
                span_cov = ov_len / span_len
                unit_cov = ov_len / u_len if u_len > 0 else 0
                if span_cov >= 0.50 or unit_cov >= 0.50:
                    qualifying.append({
                        "category": cat,
                        "ov_len": ov_len,
                        "span_cov": span_cov,
                        "unit_cov": unit_cov,
                    })
        if not qualifying:
            labeled.append({
                "text": u_text,
                "text_raw": u_text_raw,
                "label": "No Clause",
                "secondary_labels": [],
                "char_start": u_s,
                "char_end": u_e,
            })
        else:
            # Sort and apply priority rule
            cats_set = {x["category"] for x in qualifying}
            for high, low in PRIORITY_PAIRS:
                if high in cats_set and low in cats_set:
                    cats_set.remove(low)
            remaining = [x for x in qualifying if x["category"] in cats_set]
            remaining.sort(key=lambda x: x["ov_len"], reverse=True)
            primary = remaining[0]["category"]
            secondary = sorted(list({x["category"] for x in qualifying if x["category"] != primary}))
            labeled.append({
                "text": u_text,
                "text_raw": u_text_raw,
                "label": primary,
                "secondary_labels": secondary,
                "char_start": u_s,
                "char_end": u_e,
            })
    return labeled



def process_all_contracts(cuad_data: list[dict[str, Any]], tokenizer: Any) -> list[dict[str, Any]]:
    print("\n" + "=" * 70)
    print("STEP 2 & 3: RE-SEGMENTING AND LABELLING ALL CONTRACTS")
    print("=" * 70)
    
    all_records = []
    contracts_count = len(cuad_data)
    zero_risky_contracts = 0
    
    for c_idx, entry in enumerate(cuad_data):
        contract_title = entry.get("title", f"contract_{c_idx}")
        for para in entry["paragraphs"]:
            context = para["context"]
            annotations = []
            for qa in para["qas"]:
                cat = extract_category_from_question(qa["question"])
                if not cat or cat not in CUAD_TO_CLAUSE_TYPE:
                    continue
                canonical_cat = CUAD_TO_CLAUSE_TYPE[cat]
                for ans in qa["answers"]:
                    txt = ans["text"]
                    if len(txt) < 20:
                        continue
                    s = ans["answer_start"]
                    e = s + len(txt)
                    annotations.append((canonical_cat, s, e, txt))
            
            if not annotations:
                zero_risky_contracts += 1
                
            units = resegment_contract(context, tokenizer, max_tokens=256)
            labeled_units = label_units_50pct_rule(units, annotations)
            
            for u in labeled_units:
                u["contract"] = contract_title
                all_records.append(u)
                
    print(f"Ingested {contracts_count} contracts ({zero_risky_contracts} contracts with 0 risky annotations).")
    print(f"Total extracted re-segmented units: {len(all_records)}")
    return all_records


# ==============================================================================
# STEP 5: SPLIT CONTRACTS & BUILD NATURAL-PREVALENCE SETS + HARD NEGATIVES
# ==============================================================================
def create_dataset_splits(
    records: list[dict[str, Any]],
    baseline_model_path: Path,
    downsample_ratio: float = 3.0,
    hard_negatives_count: int = 500,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("\n" + "=" * 70)
    print("STEP 5: CREATING CONTRACT SPLITS, NATURAL PREVALENCE SETS & HARD NEGATIVES")
    print("=" * 70)
    
    df = pd.DataFrame(records)
    
    # Contract level splitting (same seed 42)
    unique_contracts = sorted(df["contract"].unique().tolist())
    random.seed(SEED)
    random.shuffle(unique_contracts)
    
    n = len(unique_contracts)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    
    train_contracts = set(unique_contracts[:n_train])
    val_contracts = set(unique_contracts[n_train:n_train + n_val])
    test_contracts = set(unique_contracts[n_train + n_val:])
    
    print(f"Split {len(unique_contracts)} contracts into:")
    print(f"  Train contracts: {len(train_contracts)}")
    print(f"  Val contracts:   {len(val_contracts)}")
    print(f"  Test contracts:  {len(test_contracts)}")
    
    df_train_all = df[df["contract"].isin(train_contracts)].copy()
    df_val_natural = df[df["contract"].isin(val_contracts)].copy()
    df_test_natural = df[df["contract"].isin(test_contracts)].copy()
    
    print(f"\nNatural prevalence unit counts:")
    print(f"  Train natural: {len(df_train_all)} units")
    print(f"  Val natural:   {len(df_val_natural)} units")
    print(f"  Test natural:  {len(df_test_natural)} units")
    
    # Positive units in train
    train_pos = df_train_all[df_train_all["label"] != "No Clause"].copy()
    train_neg = df_train_all[df_train_all["label"] == "No Clause"].copy()
    
    # Target downsample size for No Clause
    avg_pos_per_class = int(len(train_pos) / 10)
    target_neg_count = int(avg_pos_per_class * downsample_ratio)
    
    # For clean train.csv: keep train_pos + 142 random harmless negatives (no contaminated hard negatives)
    random_negs = train_neg.sample(n=min(142, len(train_neg)), random_state=SEED)
    df_train_balanced = pd.concat([train_pos, random_negs], ignore_index=True)
    df_train_balanced = df_train_balanced.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    
    # Also downsampled val/test for standard training validation
    val_pos = df_val_natural[df_val_natural["label"] != "No Clause"].copy()
    val_neg = df_val_natural[df_val_natural["label"] == "No Clause"].copy()
    val_neg_down = val_neg.sample(n=min(len(val_neg), int(len(val_pos) / 10 * downsample_ratio)), random_state=SEED)
    df_val_balanced = pd.concat([val_pos, val_neg_down], ignore_index=True).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    
    test_pos = df_test_natural[df_test_natural["label"] != "No Clause"].copy()
    test_neg = df_test_natural[df_test_natural["label"] == "No Clause"].copy()
    test_neg_down = test_neg.sample(n=min(len(test_neg), int(len(test_pos) / 10 * downsample_ratio)), random_state=SEED)
    df_test_balanced = pd.concat([test_pos, test_neg_down], ignore_index=True).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    
    # Save CSVs
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Natural prevalence train, val and test
    df_train_all.to_csv(PROCESSED_DIR / "train_natural.csv", index=False)
    df_val_natural.to_csv(PROCESSED_DIR / "val_natural.csv", index=False)
    df_test_natural.to_csv(PROCESSED_DIR / "test_natural.csv", index=False)

    # Balanced train, val, and test
    df_train_balanced.to_csv(PROCESSED_DIR / "train.csv", index=False)
    df_val_balanced.to_csv(PROCESSED_DIR / "val.csv", index=False)
    df_test_balanced.to_csv(PROCESSED_DIR / "test.csv", index=False)
    
    print("\nSaved files to ml/data/processed/:")
    print(f"  train_natural.csv: {len(df_train_all)} rows (Pos: {len(train_pos)}, Harmless: {len(train_neg)})")
    print(f"  train.csv:         {len(df_train_balanced)} rows (Pos: {len(train_pos)}, Random Negs: {len(random_negs)})")
    print(f"  val.csv:           {len(df_val_balanced)} rows")
    print(f"  test.csv:          {len(df_test_balanced)} rows")
    print(f"  val_natural.csv:   {len(df_val_natural)} rows")
    print(f"  test_natural.csv:  {len(df_test_natural)} rows")
    
    return df_train_balanced, df_val_balanced, df_test_balanced, df_val_natural, df_test_natural



# ==============================================================================
# STEP 6: BASELINE TF-IDF EVALUATION AT NATURAL PREVALENCE ON VALIDATION
# ==============================================================================
def evaluate_tfidf_natural_prevalence(df_val_natural: pd.DataFrame, baseline_model_path: Path) -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("STEP 6: TF-IDF BASELINE EVALUATION AT NATURAL PREVALENCE (VALIDATION CONTRACTS)")
    print("=" * 70)
    
    if not baseline_model_path.exists():
        print(f"Baseline model not found at {baseline_model_path}!")
        return {}
        
    bm = joblib.load(baseline_model_path)
    vectorizer = bm["vectorizer"]
    classifier = bm["classifier"]
    
    y_true = df_val_natural["label"].tolist()
    texts = df_val_natural["text"].tolist()
    contracts = df_val_natural["contract"].tolist()
    
    X_val = vectorizer.transform(texts)
    y_pred = classifier.predict(X_val)
    
    num_contracts = len(set(contracts))
    total_units = len(y_true)
    
    # Flags: predicted != "No Clause"
    predicted_clause = np.array([yp != "No Clause" for yp in y_pred])
    actual_clause = np.array([yt != "No Clause" for yt in y_true])
    actual_no_clause = np.array([yt == "No Clause" for yt in y_true])
    
    # False alarms: actual "No Clause" but predicted as a clause
    false_alarms = (actual_no_clause & predicted_clause)
    total_false_alarms = int(false_alarms.sum())
    false_alarms_per_contract = total_false_alarms / num_contracts
    
    # Flag Precision & Recall
    true_positives = (actual_clause & predicted_clause).sum()
    total_flags = predicted_clause.sum()
    total_actual_clauses = actual_clause.sum()
    
    flag_precision = float(true_positives / total_flags) if total_flags > 0 else 0.0
    flag_recall = float(true_positives / total_actual_clauses) if total_actual_clauses > 0 else 0.0
    
    print(f"Validation Contracts:           {num_contracts}")
    print(f"Total Natural Units:            {total_units}")
    print(f"Actual Risky Clauses:           {total_actual_clauses} ({total_actual_clauses/total_units:.2%})")
    print(f"Actual 'No Clause' Units:       {actual_no_clause.sum()} ({actual_no_clause.sum()/total_units:.2%})")
    print(f"\n--- TF-IDF NATURAL PREVALENCE METRICS ---")
    print(f"Total Flags Raised:             {total_flags}")
    print(f"True Positive Flags:            {true_positives}")
    print(f"Total False Alarms:             {total_false_alarms}")
    print(f"False Alarms per Contract:      {false_alarms_per_contract:.2f}")
    print(f"Flag Precision:                 {flag_precision:.2%}")
    print(f"Flag Recall:                    {flag_recall:.2%}")
    
    # Per-class metrics
    from sklearn.metrics import classification_report
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    print("\nPer-Class Breakdown at Natural Prevalence:")
    print(f"{'Class':<30} {'Prec':<10} {'Recall':<10} {'F1':<10} {'Support':<10}")
    print("-" * 70)
    for c in sorted(ALL_CLASSES):
        if c in report:
            p = report[c]["precision"]
            r = report[c]["recall"]
            f = report[c]["f1-score"]
            s = report[c]["support"]
            print(f"{c:<30} {p:<10.2%} {r:<10.2%} {f:<10.2%} {s:<10}")
            
    return {
        "num_contracts": num_contracts,
        "total_units": total_units,
        "total_actual_clauses": int(total_actual_clauses),
        "total_flags": int(total_flags),
        "true_positives": int(true_positives),
        "total_false_alarms": total_false_alarms,
        "false_alarms_per_contract": false_alarms_per_contract,
        "flag_precision": flag_precision,
        "flag_recall": flag_recall,
        "classification_report": report,
    }


# ==============================================================================
# STEP 4: LABEL QUALITY CHECK (30 SAMPLES PER CLASS)
# ==============================================================================
def sample_30_per_class(df_all: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    print("\n" + "=" * 70)
    print("STEP 4: EXTRACTING 30 RANDOM UNITS PER CLASS FOR QUALITY CHECK")
    print("=" * 70)
    
    samples_per_class = {}
    random.seed(SEED)
    
    for cls_name in sorted(ALL_CLASSES):
        subset = df_all[df_all["label"] == cls_name]
        n_available = len(subset)
        sample_n = min(30, n_available)
        sampled = subset.sample(n=sample_n, random_state=SEED)
        samples_list = []
        for _, row in sampled.iterrows():
            samples_list.append({
                "label": row["label"],
                "secondary_labels": row["secondary_labels"],
                "contract": row["contract"],
                "text": row["text"],
            })
        samples_per_class[cls_name] = samples_list
        print(f"Class '{cls_name}': sampled {len(samples_list)} / {n_available} units")
        
    # Save to artifacts for inspection
    out_file = ARTIFACTS_DIR / "label_quality_audit_30_per_class.json"
    with open(out_file, "w") as f:
        json.dump(samples_per_class, f, indent=2)
    print(f"\nSaved 30 samples per class to {out_file}")
    return samples_per_class


if __name__ == "__main__":
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        cuad_data = json.load(f)["data"]
        
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    
    # 1. Alignment Audit on Current Segmentation
    audit_res = run_alignment_audit(cuad_data)
    
    # 2 & 3. Re-segment and Label with 50% Rule
    resegmented_records = process_all_contracts(cuad_data, tokenizer)
    df_resegmented = pd.DataFrame(resegmented_records)
    
    # Check token lengths
    tok_lens = [len(tokenizer(t, truncation=False, add_special_tokens=False)["input_ids"]) for t in df_resegmented["text"]]
    over_256 = sum(1 for tl in tok_lens if tl > 256)
    print(f"\nRe-segmented units exceeding 256 tokens: {over_256} / {len(tok_lens)} ({over_256/len(tok_lens):.2%})")
    
    # Multi-label overlap check
    with_secondary = sum(1 for r in resegmented_records if r["secondary_labels"])
    print(f"Units with secondary (overlapping) labels: {with_secondary} / {len(resegmented_records)} ({with_secondary/len(resegmented_records):.2%})")
    
    # 5. Create Natural Prevalence Evaluation Sets + Hard Negatives
    train_df, val_df, test_df, val_nat_df, test_nat_df = create_dataset_splits(
        resegmented_records,
        BASELINE_PATH,
        downsample_ratio=3.0,
        hard_negatives_count=500,
    )
    
    # 6. Evaluate Baseline TF-IDF on Validation at Natural Prevalence
    tfidf_nat_metrics = evaluate_tfidf_natural_prevalence(val_nat_df, BASELINE_PATH)
    
    # 4. Extract 30 samples per class
    samples_30 = sample_30_per_class(pd.concat([train_df, val_nat_df], ignore_index=True))
    
    # Save complete audit summary to artifacts
    summary_data = {
        "step1_alignment_audit": {
            "total_positive_units": audit_res["total_positive_units"],
            "total_mismatches_under_50": audit_res["total_mismatches_under_50"],
            "hist_summary": audit_res["hist_summary"],
            "sample_10_mismatches": audit_res["sample_mismatches"],
        },
        "step2_and_3_resegmentation": {
            "total_units": len(resegmented_records),
            "units_over_256": over_256,
            "pct_over_256": float(over_256 / len(tok_lens)),
            "units_with_secondary": with_secondary,
            "pct_with_secondary": float(with_secondary / len(resegmented_records)),
        },
        "step5_splits": {
            "train_size": len(train_df),
            "val_balanced_size": len(val_df),
            "test_balanced_size": len(test_df),
            "val_natural_size": len(val_nat_df),
            "test_natural_size": len(test_nat_df),
        },
        "step6_tfidf_natural_prevalence": tfidf_nat_metrics,
    }
    with open(ARTIFACTS_DIR / "resegment_audit_summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nAll steps complete! Summary saved to {ARTIFACTS_DIR / 'resegment_audit_summary.json'}")

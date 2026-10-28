import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

RAW_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
BASELINE_PATH = ARTIFACTS_DIR / "baseline_model.joblib"
LEGAL_BERT_PATH = ARTIFACTS_DIR / "legal_bert"

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

ALL_CLASSES = sorted(list(set(CUAD_TO_CLAUSE_TYPE.values()))) + ["No Clause"]


class TextDataset(Dataset):
    def __init__(self, texts: list[str], tokenizer: Any, max_len: int = 256):
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
        }


def extract_category_from_question(question: str) -> str | None:
    match = re.search(r'"([^"]+)"', question)
    if match:
        return match.group(1)
    return None


# ==============================================================================
# PART 1: CLASS COUNTS & NEW UNIT ALIGNMENT HISTOGRAM
# ==============================================================================
def run_part1() -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("PART 1: CLASS COUNTS PER SPLIT & NEW UNIT ALIGNMENT HISTOGRAM")
    print("=" * 70)

    # 1. Class counts per split
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    test_df = pd.read_csv(PROCESSED_DIR / "test.csv")
    val_nat_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
    test_nat_df = pd.read_csv(PROCESSED_DIR / "test_natural.csv")

    splits = {
        "train": train_df,
        "val_balanced": val_df,
        "test_balanced": test_df,
        "val_natural": val_nat_df,
        "test_natural": test_nat_df,
    }

    count_table = pd.DataFrame(index=sorted(ALL_CLASSES))
    for s_name, s_df in splits.items():
        vc = s_df["label"].value_counts()
        count_table[s_name] = [vc.get(c, 0) for c in count_table.index]

    print("\nClass Counts Per Split:")
    print(count_table.to_string())

    # 2. Alignment audit on NEW units
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        cuad_data = json.load(f)["data"]

    # Combine all re-segmented units from train, val_natural, test_natural
    all_units_df = pd.concat([train_df[train_df["label"] != "No Clause"], val_nat_df, test_nat_df], ignore_index=True)
    pos_units_df = all_units_df[all_units_df["label"] != "No Clause"].drop_duplicates(subset=["text", "contract", "label"])

    # Load annotations map per contract
    annotations_by_contract = defaultdict(list)
    for entry in cuad_data:
        c_title = entry.get("title", "")
        for para in entry["paragraphs"]:
            for qa in para["qas"]:
                cat = extract_category_from_question(qa["question"])
                if cat and cat in CUAD_TO_CLAUSE_TYPE:
                    c_cat = CUAD_TO_CLAUSE_TYPE[cat]
                    for ans in qa["answers"]:
                        s = ans["answer_start"]
                        txt = ans["text"]
                        e = s + len(txt)
                        annotations_by_contract[c_title].append((c_cat, s, e, txt))

    by_class = defaultdict(lambda: {"span_in_unit": [], "unit_in_span": []})
    for _, row in pos_units_df.iterrows():
        c_title = row["contract"]
        c_label = row["label"]
        u_s = row["char_start"]
        u_e = row["char_end"]
        u_len = u_e - u_s

        matching_annos = [
            a for a in annotations_by_contract[c_title]
            if a[0] == c_label and min(u_e, a[2]) > max(u_s, a[1])
        ]
        if matching_annos:
            # Pick best overlap
            best_ov = 0
            best_s_cov = 0.0
            best_u_cov = 0.0
            for _, a_s, a_e, _ in matching_annos:
                ov_len = min(u_e, a_e) - max(u_s, a_s)
                s_len = a_e - a_s
                if ov_len > best_ov:
                    best_ov = ov_len
                    best_s_cov = ov_len / s_len
                    best_u_cov = ov_len / u_len
            by_class[c_label]["span_in_unit"].append(best_s_cov)
            by_class[c_label]["unit_in_span"].append(best_u_cov)

    print("\nAlignment Histogram for NEW Re-Segmented Positive Units:")
    print(f"{'Class':<28} {'N':<6} {'Span in Unit Mean (Median)':<28} {'Span Bins [0-25, 25-50, 50-75, 75-100]':<35} {'Unit in Span Mean (Median)':<28} {'Unit Bins'}")
    print("-" * 155)
    hist_results = {}
    for cat in sorted(by_class.keys()):
        s_arr = np.array(by_class[cat]["span_in_unit"])
        u_arr = np.array(by_class[cat]["unit_in_span"])
        s_bins = [int(x) for x in np.histogram(s_arr, bins=[0, 0.25, 0.50, 0.75, 1.0001])[0]]
        u_bins = [int(x) for x in np.histogram(u_arr, bins=[0, 0.25, 0.50, 0.75, 1.0001])[0]]
        hist_results[cat] = {
            "count": len(s_arr),
            "span_mean": float(s_arr.mean()),
            "span_median": float(np.median(s_arr)),
            "span_bins": s_bins,
            "unit_mean": float(u_arr.mean()),
            "unit_median": float(np.median(u_arr)),
            "unit_bins": u_bins,
        }
        s_str = f"{s_arr.mean():.2%} ({np.median(s_arr):.2%})"
        u_str = f"{u_arr.mean():.2%} ({np.median(u_arr):.2%})"
        print(f"{cat:<28} {len(s_arr):<6} {s_str:<28} {str(s_bins):<35} {u_str:<28} {str(u_bins)}")

    return {"count_table": count_table.to_dict(), "hist_results": hist_results}


# ==============================================================================
# PART 2: MEASURE TODAY'S NUMBERS ON VAL_NATURAL AT DEFAULT ARGMAX
# ==============================================================================
def run_part2() -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("PART 2: MEASURE TODAY'S NUMBERS ON VAL_NATURAL (LEGAL-BERT & OLD TF-IDF)")
    print("=" * 70)

    val_nat_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
    y_true = val_nat_df["label"].tolist()
    texts = val_nat_df["text"].tolist()
    contracts = val_nat_df["contract"].tolist()
    num_contracts = len(set(contracts))
    total_units = len(y_true)

    actual_clause = np.array([y != "No Clause" for y in y_true])
    actual_no_clause = np.array([y == "No Clause" for y in y_true])
    total_actual_clauses = int(actual_clause.sum())

    # --- 1. Old TF-IDF Evaluation ---
    print("\nEvaluating Old TF-IDF on val_natural at argmax...")
    bm = joblib.load(BASELINE_PATH)
    vec = bm["vectorizer"]
    clf = bm["classifier"]
    X_val = vec.transform(texts)
    tfidf_preds = clf.predict(X_val)

    tfidf_flags = np.array([p != "No Clause" for p in tfidf_preds])
    tfidf_tp = int((actual_clause & tfidf_flags).sum())
    tfidf_fa = int((actual_no_clause & tfidf_flags).sum())
    tfidf_prec = float(tfidf_tp / tfidf_flags.sum()) if tfidf_flags.sum() > 0 else 0.0
    tfidf_rec = float(tfidf_tp / total_actual_clauses) if total_actual_clauses > 0 else 0.0
    tfidf_fa_per_contract = tfidf_fa / num_contracts

    # --- 2. Deployed Legal-BERT Evaluation ---
    print("Evaluating Deployed Legal-BERT on val_natural at argmax...")
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")

    tok = AutoTokenizer.from_pretrained(LEGAL_BERT_PATH)
    model = AutoModelForSequenceClassification.from_pretrained(LEGAL_BERT_PATH).to(device)
    model.eval()

    ds = TextDataset(texts, tok, max_len=256)
    loader = DataLoader(ds, batch_size=32, shuffle=False)

    all_logits = []
    with torch.no_grad():
        for b_idx, batch in enumerate(loader):
            b_ids = batch["input_ids"].to(device)
            b_mask = batch["attention_mask"].to(device)
            out = model(input_ids=b_ids, attention_mask=b_mask)
            all_logits.append(out.logits.cpu().numpy())

    bert_logits = np.concatenate(all_logits, axis=0)
    bert_pred_indices = np.argmax(bert_logits, axis=1)
    id2label = model.config.id2label
    bert_preds = [id2label[idx] for idx in bert_pred_indices]

    bert_flags = np.array([p != "No Clause" for p in bert_preds])
    bert_tp = int((actual_clause & bert_flags).sum())
    bert_fa = int((actual_no_clause & bert_flags).sum())
    bert_prec = float(bert_tp / bert_flags.sum()) if bert_flags.sum() > 0 else 0.0
    bert_rec = float(bert_tp / total_actual_clauses) if total_actual_clauses > 0 else 0.0
    bert_fa_per_contract = bert_fa / num_contracts

    print("\n" + "=" * 70)
    print("TODAY'S COMPARISON ON VAL_NATURAL (76 CONTRACTS, 10,270 UNITS, 478 CLAUSES)")
    print("=" * 70)
    print(f"{'Metric':<30} {'Old TF-IDF':<20} {'Deployed Legal-BERT'}")
    print("-" * 70)
    print(f"{'Total Flags Raised':<30} {tfidf_flags.sum():<20} {bert_flags.sum()}")
    print(f"{'True Positive Flags':<30} {tfidf_tp:<20} {bert_tp}")
    print(f"{'Total False Alarms':<30} {tfidf_fa:<20} {bert_fa}")
    print(f"{'False Alarms / Contract':<30} {tfidf_fa_per_contract:<20.2f} {bert_fa_per_contract:.2f}")
    print(f"{'Flag Precision':<30} {tfidf_prec:<20.2%} {bert_prec:.2%}")
    print(f"{'Flag Recall':<30} {tfidf_rec:<20.2%} {bert_rec:.2%}")

    # Per-class reports
    tfidf_report = classification_report(y_true, tfidf_preds, output_dict=True, zero_division=0)
    bert_report = classification_report(y_true, bert_preds, output_dict=True, zero_division=0)

    print("\nPer-Class Detailed Comparison:")
    print(f"{'Class':<28} {'TF-IDF P / R / F1':<30} {'Legal-BERT P / R / F1':<30} {'Support'}")
    print("-" * 95)
    for c in sorted(ALL_CLASSES):
        t_p, t_r, t_f = tfidf_report.get(c, {}).get("precision", 0), tfidf_report.get(c, {}).get("recall", 0), tfidf_report.get(c, {}).get("f1-score", 0)
        b_p, b_r, b_f = bert_report.get(c, {}).get("precision", 0), bert_report.get(c, {}).get("recall", 0), bert_report.get(c, {}).get("f1-score", 0)
        sup = tfidf_report.get(c, {}).get("support", 0)
        t_str = f"{t_p:.1%} / {t_r:.1%} / {t_f:.1%}"
        b_str = f"{b_p:.1%} / {b_r:.1%} / {b_f:.1%}"
        print(f"{c:<28} {t_str:<30} {b_str:<30} {sup}")

    # Save bert logits for reuse in step 5
    np.save(ARTIFACTS_DIR / "deployed_legal_bert_val_logits.npy", bert_logits)

    return {
        "tfidf": {
            "flags": int(tfidf_flags.sum()),
            "tp": tfidf_tp,
            "fa": tfidf_fa,
            "fa_per_contract": tfidf_fa_per_contract,
            "precision": tfidf_prec,
            "recall": tfidf_rec,
            "report": tfidf_report,
        },
        "legal_bert": {
            "flags": int(bert_flags.sum()),
            "tp": bert_tp,
            "fa": bert_fa,
            "fa_per_contract": bert_fa_per_contract,
            "precision": bert_prec,
            "recall": bert_rec,
            "report": bert_report,
        },
    }


# ==============================================================================
# PART 3: HARD-NEGATIVE CHECK (TOP 30 & RANKS 500-530)
# ==============================================================================
def run_part3() -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("PART 3: HARD-NEGATIVE CHECK (TOP 30 & RANKS 500-530)")
    print("=" * 70)

    # Load all training harmless units
    train_nat_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    # Actually we load from all training contracts to get the exact pool of harmless units
    # Load raw CUAD to extract all units of training contracts
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        cuad_data = json.load(f)["data"]

    from ml.src.resegment_and_audit import resegment_contract, label_units_50pct_rule, strip_headers_footers_offset_preserving
    tok = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")

    # Get training contracts
    unique_contracts = sorted(list({entry.get("title", "") for entry in cuad_data if entry.get("title")}))
    random.seed(SEED)
    random.shuffle(unique_contracts)
    n_train = int(len(unique_contracts) * 0.70)
    train_contracts = set(unique_contracts[:n_train])

    train_harmless_records = []
    for entry in cuad_data:
        c_title = entry.get("title", "")
        if c_title not in train_contracts:
            continue
        for para in entry["paragraphs"]:
            ctx = para["context"]
            annotations = []
            for qa in para["qas"]:
                cat = extract_category_from_question(qa["question"])
                if cat and cat in CUAD_TO_CLAUSE_TYPE:
                    c_cat = CUAD_TO_CLAUSE_TYPE[cat]
                    for ans in qa["answers"]:
                        s = ans["answer_start"]
                        txt = ans["text"]
                        e = s + len(txt)
                        annotations.append((c_cat, s, e, txt))
            units = resegment_contract(ctx, tok, max_tokens=256)
            labeled = label_units_50pct_rule(units, annotations)
            for u in labeled:
                if u["label"] == "No Clause":
                    u["contract"] = c_title
                    train_harmless_records.append(u)

    print(f"Total training harmless ('No Clause') units: {len(train_harmless_records)}")

    # Score with TF-IDF
    bm = joblib.load(BASELINE_PATH)
    vec = bm["vectorizer"]
    clf = bm["classifier"]
    classes = list(clf.classes_)

    texts = [r["text"] for r in train_harmless_records]
    X_train_neg = vec.transform(texts)
    probs = clf.predict_proba(X_train_neg)

    no_clause_idx = classes.index("No Clause") if "No Clause" in classes else -1
    clause_indices = [i for i in range(len(classes)) if i != no_clause_idx]
    max_risk_probs = probs[:, clause_indices].max(axis=1)
    pred_risk_classes = [classes[clause_indices[np.argmax(probs[i, clause_indices])]] for i in range(len(texts))]

    for i in range(len(train_harmless_records)):
        train_harmless_records[i]["risk_score"] = float(max_risk_probs[i])
        train_harmless_records[i]["predicted_risk_class"] = pred_risk_classes[i]

    # Sort descending
    train_harmless_records.sort(key=lambda x: x["risk_score"], reverse=True)

    top_30 = train_harmless_records[:30]
    ranks_500_530 = train_harmless_records[500:530]

    out_file = ARTIFACTS_DIR / "hard_negatives_audit_samples.json"
    with open(out_file, "w") as f:
        json.dump({
            "top_30": top_30,
            "ranks_500_530": ranks_500_530,
        }, f, indent=2)
    print(f"Saved hard negative check samples to {out_file}")

    return {
        "total_harmless": len(train_harmless_records),
        "top_30": top_30,
        "ranks_500_530": ranks_500_530,
    }


if __name__ == "__main__":
    p1 = run_part1()
    p2 = run_part2()
    p3 = run_part3()

    with open(ARTIFACTS_DIR / "step123_audit_summary.json", "w") as f:
        # Convert any remaining int64
        def default_serializer(obj):
            if isinstance(obj, (np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            raise TypeError(f"Type {type(obj)} not serializable")
        json.dump({
            "part1": p1,
            "part2": p2,
            "part3_summary": {
                "total_harmless": p3["total_harmless"],
                "top_score": p3["top_30"][0]["risk_score"],
                "rank_30_score": p3["top_30"][-1]["risk_score"],
                "rank_500_score": p3["ranks_500_530"][0]["risk_score"],
                "rank_530_score": p3["ranks_500_530"][-1]["risk_score"],
            }
        }, f, indent=2, default=default_serializer)
    print("\nAll Part 1, 2, 3 audits completed successfully!")

"""Step 1 & Step 2: Build Model B training set and evaluate TF-IDF Model B and Deployed Baseline."""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.resegment_and_audit import CUAD_TO_CLAUSE_TYPE, extract_category_from_question

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
RAW_CUAD_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"

TARGET_CLASSES = [
    "Non-Compete",
    "Exclusivity",
    "Uncapped Liability",
    "Liquidated Damages",
]

SUBSTANTIVE_CLASSES = [
    "Anti-Assignment",
    "Audit Rights",
    "Cap on Liability",
    "Change of Control",
    "Exclusivity",
    "IP Ownership Assignment",
    "Liquidated Damages",
    "Non-Compete",
    "Termination for Convenience",
    "Uncapped Liability",
]


def load_all_annotations():
    with open(RAW_CUAD_PATH) as f:
        cuad_data = json.load(f)["data"]

    all_annots = {}
    for entry in cuad_data:
        title = entry["title"]
        annots = []
        for qa in entry["paragraphs"][0]["qas"]:
            cat = extract_category_from_question(qa["question"])
            if cat in CUAD_TO_CLAUSE_TYPE:
                c_cat = CUAD_TO_CLAUSE_TYPE[cat]
                for ans in qa["answers"]:
                    txt = ans["text"]
                    if len(txt) >= 20:
                        s = ans["answer_start"]
                        e = s + len(txt)
                        annots.append((c_cat, s, e, txt))
        all_annots[title] = annots
    return all_annots


def build_final_model_b_dataset():
    all_annots = load_all_annotations()
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    train_pos = train_df[train_df["label"] != "No Clause"].copy()

    # Identify 22 positives with unit coverage < 10%
    under_10_indices = set()
    for idx, r in train_pos.iterrows():
        c = r["contract"]
        lbl = r["label"]
        u_s = int(r["char_start"])
        u_e = int(r["char_end"])
        u_len = u_e - u_s
        best_u_cov = 0.0
        for cat, a_s, a_e, a_txt in all_annots.get(c, []):
            if cat == lbl:
                ov_s = max(u_s, a_s)
                ov_e = min(u_e, a_e)
                if ov_e > ov_s:
                    ov_len = ov_e - ov_s
                    u_cov = ov_len / u_len if u_len > 0 else 0
                    if u_cov > best_u_cov:
                        best_u_cov = u_cov
        if best_u_cov < 0.10:
            under_10_indices.add(idx)

    print(f"Total base train positives: {len(train_pos)}")
    print(f"Dropping {len(under_10_indices)} positives with unit coverage < 10%")
    clean_pos = train_pos.loc[~train_pos.index.isin(under_10_indices)].copy()
    print(f"Remaining clean base positives: {len(clean_pos)}")

    # Add 15 verified omitted positives
    with open(ARTIFACTS_DIR / "verified_omitted_positives_train.json") as f:
        pos_list = json.load(f)
    omitted_pos_df = pd.DataFrame(pos_list)
    omitted_pos_df["label"] = omitted_pos_df["class"]

    all_pos = pd.concat([
        clean_pos[["text", "label", "contract"]],
        omitted_pos_df[["text", "label", "contract"]]
    ], ignore_index=True)
    all_pos["sample_weight"] = 1.0
    print(f"Total final positives (including 15 omissions): {len(all_pos)}")

    all_pos_texts = set(all_pos["text"].tolist())

    # Harmless training pool
    train_nat = pd.read_csv(PROCESSED_DIR / "train_natural.csv")
    harmless_pool = train_nat[train_nat["label"] == "No Clause"].copy()
    harmless_pool = harmless_pool[~harmless_pool["text"].isin(all_pos_texts)].copy()

    # 650 Hard Negatives (ranks 101-250 and 501-1000)
    df_ranked = pd.read_csv(ARTIFACTS_DIR / "oof_ranked_harmless_units.csv")
    hard_negs_1 = df_ranked[(df_ranked["rank"] >= 101) & (df_ranked["rank"] <= 250)].copy()
    hard_negs_2 = df_ranked[(df_ranked["rank"] >= 501) & (df_ranked["rank"] <= 1000)].copy()
    hard_negs = pd.concat([hard_negs_1, hard_negs_2], ignore_index=True)
    hard_negs = hard_negs[~hard_negs["text"].isin(all_pos_texts)].copy()
    hard_negs["sample_weight"] = 0.5
    hard_negs_texts = set(hard_negs["text"].tolist())

    # 3,000 Random Negatives
    random_pool = harmless_pool[~harmless_pool["text"].isin(hard_negs_texts)].copy()
    random_negs = random_pool.sample(n=3000, random_state=SEED).copy()
    random_negs["sample_weight"] = 1.0

    # Combine into Model B training set
    model_b_df = pd.concat([
        all_pos[["text", "label", "contract", "sample_weight"]],
        random_negs[["text", "label", "contract", "sample_weight"]],
        hard_negs[["text", "label", "contract", "sample_weight"]]
    ], ignore_index=True).sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    print(f"Model B training set total rows: {len(model_b_df)}")
    print(f"  Positives: {(model_b_df['label'] != 'No Clause').sum()}")
    print(f"  Negatives (weight 1.0): {((model_b_df['label'] == 'No Clause') & (model_b_df['sample_weight'] == 1.0)).sum()}")
    print(f"  Hard Negatives (weight 0.5): {((model_b_df['label'] == 'No Clause') & (model_b_df['sample_weight'] == 0.5)).sum()}")

    # Save to processed dir
    model_b_df.to_csv(PROCESSED_DIR / "train_model_b_final.csv", index=False)
    return model_b_df


def compute_operating_points_table(model_name, probs, classes, val_df, target_fa_list=[3, 5, 8, 12, 20]):
    """Compute operating points table on val_natural.csv.
    
    Reports:
    - Target FA/c
    - Actual FA/c
    - Threshold
    - Flags count
    - False Alarms (FA)
    - True Positives (TP)
    - Precision (%)
    - Overall Recall (Flagged: any class flag)
    - Overall Recall (Flagged with correct class)
    - Non-Compete Recall (Flagged & Correct)
    - Exclusivity Recall (Flagged & Correct)
    - Uncapped Liability Recall (Flagged & Correct)
    - Liquidated Damages Recall (Flagged & Correct)
    """
    n_contracts = val_df["contract"].nunique()
    no_clause_idx = list(classes).index("No Clause")
    substantive_indices = [i for i, c in enumerate(classes) if c != "No Clause"]
    substantive_class_names = [classes[i] for i in substantive_indices]

    p_no_clause = probs[:, no_clause_idx]
    # Argmax over substantive classes
    sub_probs = probs[:, substantive_indices]
    pred_sub_indices = np.argmax(sub_probs, axis=-1)
    pred_sub_classes = np.array([substantive_class_names[idx] for idx in pred_sub_indices])

    y_true = val_df["label"].to_numpy()
    is_positive = (y_true != "No Clause")
    is_negative = (y_true == "No Clause")
    total_positives = int(is_positive.sum())

    sorted_neg_scores = np.sort(p_no_clause[is_negative])

    rows = []
    for target_fa_c in target_fa_list:
        target_fa_total = int(round(target_fa_c * n_contracts))
        thresh_idx = min(target_fa_total - 1, len(sorted_neg_scores) - 1)
        thresh = float(sorted_neg_scores[thresh_idx])

        # Flags: p_no_clause < thresh
        flagged = (p_no_clause < thresh)
        fa_count = int((flagged & is_negative).sum())
        actual_fa_c = round(fa_count / n_contracts, 2)
        flags_count = int(flagged.sum())

        # Overall recalls
        tp_flagged = int((flagged & is_positive).sum())
        tp_correct = int((flagged & is_positive & (pred_sub_classes == y_true)).sum())

        precision = round((tp_flagged / flags_count * 100), 2) if flags_count > 0 else 0.0
        rec_flagged_overall = round((tp_flagged / total_positives * 100), 2)
        rec_correct_overall = round((tp_correct / total_positives * 100), 2)

        row = {
            "model": model_name,
            "target_fa_c": target_fa_c,
            "actual_fa_c": actual_fa_c,
            "threshold": round(thresh, 4),
            "flags": flags_count,
            "fa": fa_count,
            "tp_flagged": tp_flagged,
            "tp_correct": tp_correct,
            "precision": precision,
            "rec_flagged_overall": rec_flagged_overall,
            "rec_correct_overall": rec_correct_overall,
        }

        # Per-class recalls for the 4 target classes
        for cat in TARGET_CLASSES:
            cat_mask = (y_true == cat)
            n_cat = int(cat_mask.sum())
            if n_cat > 0:
                cat_flagged = int((flagged & cat_mask).sum())
                cat_correct = int((flagged & cat_mask & (pred_sub_classes == cat)).sum())
                row[f"{cat}_flagged"] = round((cat_flagged / n_cat * 100), 2)
                row[f"{cat}_correct"] = round((cat_correct / n_cat * 100), 2)
            else:
                row[f"{cat}_flagged"] = 0.0
                row[f"{cat}_correct"] = 0.0

        rows.append(row)
    return rows


def print_table(rows, title):
    print("\n" + "=" * 130)
    print(f"OPERATING-POINTS TABLE: {title}")
    print("=" * 130)
    header = (
        f"{'Target':<7} {'Actual':<7} {'Thresh':<8} {'Flags':<6} {'FA':<5} {'Prec':<7} "
        f"{'Rec(Flag)':<10} {'Rec(Corr)':<10} "
        f"{'NC(Fl/Co)':<12} {'Exc(Fl/Co)':<12} {'Uncap(Fl/Co)':<14} {'Liq(Fl/Co)':<12}"
    )
    print(header)
    print("-" * 130)
    for r in rows:
        nc_str = f"{r['Non-Compete_flagged']:.1f}/{r['Non-Compete_correct']:.1f}%"
        exc_str = f"{r['Exclusivity_flagged']:.1f}/{r['Exclusivity_correct']:.1f}%"
        uncap_str = f"{r['Uncapped Liability_flagged']:.1f}/{r['Uncapped Liability_correct']:.1f}%"
        liq_str = f"{r['Liquidated Damages_flagged']:.1f}/{r['Liquidated Damages_correct']:.1f}%"
        line = (
            f"{r['target_fa_c']:<7} {r['actual_fa_c']:<7.2f} {r['threshold']:<8.4f} {r['flags']:<6} {r['fa']:<5} {r['precision']:<7.2f}% "
            f"{r['rec_flagged_overall']:<10.2f}% {r['rec_correct_overall']:<10.2f}% "
            f"{nc_str:<12} {exc_str:<12} {uncap_str:<14} {liq_str:<12}"
        )
        print(line)


def main():
    print("================================================================================")
    print("STEP 1: BUILDING FINAL MODEL B TRAINING SET")
    print("================================================================================")
    train_model_b_df = build_final_model_b_dataset()

    val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
    print(f"\nLoaded val_natural: {len(val_nat)} units across {val_nat['contract'].nunique()} contracts.")

    print("\n================================================================================")
    print("TRAINING TF-IDF MODEL B")
    print("================================================================================")
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50000, sublinear_tf=True)
    X_train = vec.fit_transform(train_model_b_df["text"])
    y_train = train_model_b_df["label"].to_numpy()
    weights_train = train_model_b_df["sample_weight"].to_numpy()

    clf_b = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEED, C=1.0, solver="lbfgs")
    clf_b.fit(X_train, y_train, sample_weight=weights_train)
    print(f"Fitted TF-IDF Model B with classes: {list(clf_b.classes_)}")

    X_val = vec.transform(val_nat["text"])
    probs_b = clf_b.predict_proba(X_val)

    # Save TF-IDF Model B predictions
    np.save(ARTIFACTS_DIR / "tfidf_model_b_val_natural_probs.npy", probs_b)
    with open(ARTIFACTS_DIR / "tfidf_model_b_classes.json", "w") as f:
        json.dump(list(clf_b.classes_), f)

    table_b = compute_operating_points_table("TF-IDF Model B", probs_b, clf_b.classes_, val_nat)
    print_table(table_b, "TF-IDF Model B (positives drop <10% cov, 3k rand, 650 hard w=0.5)")

    print("\n================================================================================")
    print("EVALUATING DEPLOYED BASELINE MODEL (baseline_model.joblib)")
    print("================================================================================")
    bm = joblib.load(ARTIFACTS_DIR / "baseline_model.joblib")
    bm_vec = bm["vectorizer"]
    bm_clf = bm["classifier"]
    bm_classes = bm["classes"]

    X_val_bm = bm_vec.transform(val_nat["text"])
    probs_bm = bm_clf.predict_proba(X_val_bm)

    np.save(ARTIFACTS_DIR / "deployed_baseline_val_natural_probs.npy", probs_bm)
    with open(ARTIFACTS_DIR / "deployed_baseline_classes.json", "w") as f:
        json.dump(bm_classes, f)

    table_bm = compute_operating_points_table("Deployed Baseline", probs_bm, bm_classes, val_nat)
    print_table(table_bm, "Deployed Baseline (baseline_model.joblib)")

    results = {
        "tfidf_model_b": table_b,
        "deployed_baseline": table_bm,
    }
    with open(ARTIFACTS_DIR / "step2_operating_points_tfidf.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved Step 2 results to ml/artifacts/step2_operating_points_tfidf.json")


if __name__ == "__main__":
    main()

"""Train Models A, B, and C with operating-points table on val_natural.
Model A: Positives (2,230 + 15 approved omissions) + 3,000 random negatives.
Model B: Model A + 650 hard negatives (ranks 101-250 and 501-1000, weight 0.5).
Model C: Model A + 88 verified negatives (weight 1.0).
"""
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

TARGET_CLASSES = [
    "Non-Compete",
    "Exclusivity",
    "Uncapped Liability",
    "Liquidated Damages",
]

def load_data():
    # 1. Base training positives
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    base_pos = train_df[train_df["label"] != "No Clause"].copy()
    
    # 2. Approved omitted positives (15 ranks)
    with open(ARTIFACTS_DIR / "verified_omitted_positives_train.json") as f:
        pos_list = json.load(f)
    omitted_pos_df = pd.DataFrame(pos_list)
    omitted_pos_df["label"] = omitted_pos_df["class"]
    
    all_pos = pd.concat([base_pos[["text", "label", "contract"]], omitted_pos_df[["text", "label", "contract"]]], ignore_index=True)
    all_pos_texts = set(all_pos["text"].tolist())
    
    # 3. Harmless training pool
    train_nat = pd.read_csv(PROCESSED_DIR / "train_natural.csv")
    harmless_pool = train_nat[train_nat["label"] == "No Clause"].copy()
    # Exclude any that match positive texts
    harmless_pool = harmless_pool[~harmless_pool["text"].isin(all_pos_texts)].copy()
    
    # 4. 650 Hard Negatives (ranks 101-250: 150 units, and ranks 501-1000: 500 units)
    df_ranked = pd.read_csv(ARTIFACTS_DIR / "oof_ranked_harmless_units.csv")
    # ranks are 1-indexed
    ranks_101_250 = df_ranked[(df_ranked["rank"] >= 101) & (df_ranked["rank"] <= 250)].copy()
    ranks_501_1000 = df_ranked[(df_ranked["rank"] >= 501) & (df_ranked["rank"] <= 1000)].copy()
    hard_negs_650 = pd.concat([ranks_101_250, ranks_501_1000], ignore_index=True)
    assert len(hard_negs_650) == 650, f"Expected 650 hard negs, got {len(hard_negs_650)}"
    hard_negs_texts = set(hard_negs_650["text"].tolist())
    
    # 5. 3,000 Random Negatives (excluding hard negs)
    clean_harmless = harmless_pool[~harmless_pool["text"].isin(hard_negs_texts)].copy()
    random_negs_3000 = clean_harmless.sample(n=3000, random_state=SEED).copy()
    random_negs_3000["label"] = "No Clause"
    
    # 6. Verified Negatives (88 units)
    with open(ARTIFACTS_DIR / "verified_negatives_train.json") as f:
        ver_neg_list = json.load(f)
    ver_neg_df = pd.DataFrame(ver_neg_list)
    ver_neg_df["label"] = "No Clause"
    
    # Val Natural
    val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
    
    return all_pos, random_negs_3000, hard_negs_650, ver_neg_df, val_nat


def build_models(all_pos, random_negs_3000, hard_negs_650, ver_neg_df):
    # Model A: Positives + 3,000 random negatives
    df_a = pd.concat([all_pos, random_negs_3000[["text", "label", "contract"]]], ignore_index=True)
    weights_a = np.ones(len(df_a))
    
    # Model B: Model A + 650 hard negatives (weight 0.5)
    hard_df = hard_negs_650[["text", "label", "contract"]].copy()
    hard_df["label"] = "No Clause"
    df_b = pd.concat([df_a, hard_df], ignore_index=True)
    weights_b = np.concatenate([np.ones(len(df_a)), np.full(len(hard_df), 0.5)])
    
    # Model C: Model A + Verified Negatives (weight 1.0)
    ver_df = ver_neg_df[["text", "label", "contract"]].copy()
    df_c = pd.concat([df_a, ver_df], ignore_index=True)
    weights_c = np.ones(len(df_c))
    
    return (df_a, weights_a), (df_b, weights_b), (df_c, weights_c)


def train_and_eval_model(train_df, weights, val_nat, model_name):
    print(f"\nTraining {model_name} (N={len(train_df)} rows)...")
    vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), sublinear_tf=True)
    X_train = vec.fit_transform(train_df["text"])
    clf = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=SEED)
    clf.fit(X_train, train_df["label"], sample_weight=weights)
    
    # Evaluate on val_natural
    X_val = vec.transform(val_nat["text"])
    probs = clf.predict_proba(X_val)
    classes = list(clf.classes_)
    no_clause_idx = classes.index("No Clause")
    clause_indices = [i for i in range(len(classes)) if i != no_clause_idx]
    
    # Risk score = 1 - P(No Clause)
    risk_scores = 1.0 - probs[:, no_clause_idx]
    # Argmax among risky classes
    pred_risk_classes = [classes[clause_indices[np.argmax(probs[i, clause_indices])]] for i in range(len(val_nat))]
    
    y_true = val_nat["label"].values
    contracts = val_nat["contract"].values
    num_contracts = len(set(contracts))
    
    is_actual_risky = (y_true != "No Clause")
    is_actual_harmless = (y_true == "No Clause")
    total_risky = int(is_actual_risky.sum())
    
    # Targets
    target_fa_rates = [3, 5, 8, 12, 20]
    results_table = []
    
    # Threshold sweep from 0.01 to 0.99
    thresholds = np.linspace(0.01, 0.99, 990)
    
    for fa_target in target_fa_rates:
        target_fa_count = fa_target * num_contracts
        
        # Find threshold that gives closest FA count without exceeding (or closest match)
        best_t = None
        best_diff = float("inf")
        best_fa = 0
        best_flags = 0
        
        for t in thresholds:
            pred_flags = (risk_scores >= t)
            fa_count = int((pred_flags & is_actual_harmless).sum())
            diff = abs(fa_count - target_fa_count)
            if diff < best_diff:
                best_diff = diff
                best_t = t
                best_fa = fa_count
                best_flags = int(pred_flags.sum())
                
        # Compute metrics at best_t
        pred_flags = (risk_scores >= best_t)
        tp = int((pred_flags & is_actual_risky).sum())
        prec = tp / best_flags if best_flags > 0 else 0.0
        overall_rec = tp / total_risky if total_risky > 0 else 0.0
        
        # Class-specific recall
        class_recalls = {}
        for cname in TARGET_CLASSES:
            c_mask = (y_true == cname)
            c_total = int(c_mask.sum())
            c_tp = int((pred_flags & c_mask).sum())
            class_recalls[cname] = c_tp / c_total if c_total > 0 else 0.0
            
        results_table.append({
            "target_fa_per_contract": fa_target,
            "actual_fa_per_contract": best_fa / num_contracts,
            "threshold": float(best_t),
            "flags": best_flags,
            "fa_count": best_fa,
            "tp_count": tp,
            "precision": prec,
            "overall_recall": overall_rec,
            "class_recalls": class_recalls,
        })
        
    return results_table


def main():
    print("=" * 80)
    print("TRAINING MODELS A, B, AND C WITH OPERATING-POINTS TABLE ON VAL_NATURAL")
    print("=" * 80)
    
    all_pos, random_negs_3000, hard_negs_650, ver_neg_df, val_nat = load_data()
    print(f"Total training positives: {len(all_pos)} (2,230 baseline + 15 approved omissions)")
    print(f"Random harmless negatives: {len(random_negs_3000)}")
    print(f"Hard negatives (ranks 101-250 & 501-1000): {len(hard_negs_650)}")
    print(f"Verified negatives: {len(ver_neg_df)}")
    print(f"Val natural units: {len(val_nat)} across {len(set(val_nat['contract']))} contracts")
    
    (df_a, w_a), (df_b, w_b), (df_c, w_c) = build_models(all_pos, random_negs_3000, hard_negs_650, ver_neg_df)
    
    res_a = train_and_eval_model(df_a, w_a, val_nat, "Model A (Positives + 3k Random Negatives)")
    res_b = train_and_eval_model(df_b, w_b, val_nat, "Model B (Model A + 650 Hard Negatives, w=0.5)")
    res_c = train_and_eval_model(df_c, w_c, val_nat, "Model C (Model A + 88 Verified Negatives, w=1.0)")
    
    with open(ARTIFACTS_DIR / "operating_points_abc.json", "w") as f:
        json.dump({
            "model_a": res_a,
            "model_b": res_b,
            "model_c": res_c,
        }, f, indent=2)
        
    print("\nOperating points evaluation complete!")

if __name__ == "__main__":
    main()

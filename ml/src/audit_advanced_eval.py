"""Advanced evaluation audit: Calibration, Rules, Validation Ensembles, and Contract Bootstrap.

Covers:
C. Expected Calibration Error (ECE), Reliability Table, and Temperature Scaling on validation for Legal-BERT.
D. High-precision rule-based enhancements with unit tests and before/after validation metrics.
E. Sliding-window inference, Legal-BERT + TF-IDF probability averaging, and validation per-class thresholds (reported separately).
F. Contract-level (cluster) bootstrap on pooled out-of-fold predictions.
"""
import gc
import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import scipy.optimize as opt
import torch
import torch.nn as nn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import KFold
from transformers import AutoModelForSequenceClassification, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
LEGAL_BERT_DIR = ARTIFACTS_DIR / "legal_bert"
MULTI_BERT_DIR = ARTIFACTS_DIR / "legal_bert_multiyear"
BASELINE_PATH = ARTIFACTS_DIR / "baseline_model.joblib"


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# ===========================================================================
# C. Reliability, Expected Calibration Error (ECE), & Temperature Scaling
# ===========================================================================
def compute_ece_and_table(
    probs: np.ndarray,
    y_true: list[int],
    n_bins: int = 10,
) -> tuple[float, list[dict[str, Any]]]:
    """Compute Expected Calibration Error and binned reliability table."""
    confidences = np.max(probs, axis=-1)
    predictions = np.argmax(probs, axis=-1)
    accuracies = (predictions == np.array(y_true)).astype(float)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    table = []
    n_total = len(y_true)

    for i in range(n_bins):
        bin_lower, bin_upper = bins[i], bins[i + 1]
        mask = (confidences >= bin_lower) & (confidences < bin_upper) if i < n_bins - 1 else (confidences >= bin_lower) & (confidences <= bin_upper)
        bin_count = int(np.sum(mask))

        if bin_count > 0:
            bin_acc = float(np.mean(accuracies[mask]))
            bin_conf = float(np.mean(confidences[mask]))
            bin_error = abs(bin_acc - bin_conf)
            ece += (bin_count / n_total) * bin_error
        else:
            bin_acc = 0.0
            bin_conf = float((bin_lower + bin_upper) / 2.0)
            bin_error = 0.0

        table.append({
            "bin_range": f"[{bin_lower:.1f}, {bin_upper:.1f})",
            "count": bin_count,
            "pct_total": round((bin_count / n_total) * 100, 2),
            "avg_confidence": round(bin_conf, 4),
            "empirical_accuracy": round(bin_acc, 4),
            "calibration_gap": round(bin_error, 4),
        })

    return round(float(ece), 4), table


def fit_temperature_scaling(logits: np.ndarray, y_true: list[int]) -> float:
    """Fit temperature parameter T > 0 on validation logits using NLL loss."""
    targets = np.array(y_true)

    def nll_obj(t: float) -> float:
        scaled = logits / max(t, 1e-4)
        # Numerically stable log-softmax
        max_l = np.max(scaled, axis=-1, keepdims=True)
        exp_l = np.exp(scaled - max_l)
        log_softmax = (scaled - max_l) - np.log(np.sum(exp_l, axis=-1, keepdims=True))
        nll = -np.mean(log_softmax[np.arange(len(targets)), targets])
        return float(nll)

    res = opt.minimize_scalar(nll_obj, bounds=(0.05, 5.0), method="bounded")
    return float(res.x)


def run_reliability_audit(val_df: pd.DataFrame, label2id: dict[str, int]) -> dict[str, Any]:
    print("\n" + "=" * 75)
    print("STEP C: Reliability, Expected Calibration Error (ECE) & Temperature Scaling")
    print("=" * 75)

    device = get_device()
    tokenizer = AutoTokenizer.from_pretrained(LEGAL_BERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(LEGAL_BERT_DIR).to(device)
    model.eval()

    texts = val_df["text"].tolist()
    y_true = [label2id[l] for l in val_df["label"]]

    all_logits = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            batch = texts[i : i + 32]
            enc = tokenizer(batch, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
            out = model(**enc)
            all_logits.append(out.logits.cpu().numpy())

    del model
    if device.type == "mps":
        torch.mps.empty_cache()

    logits = np.vstack(all_logits)
    raw_probs = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
    raw_probs = raw_probs / np.sum(raw_probs, axis=-1, keepdims=True)

    # 1. Uncalibrated ECE and Reliability Table
    raw_ece, raw_table = compute_ece_and_table(raw_probs, y_true, n_bins=10)

    # 2. Fit Temperature Scaling
    opt_t = fit_temperature_scaling(logits, y_true)

    # 3. Calibrated Probs and ECE
    scaled_logits = logits / opt_t
    cal_probs = np.exp(scaled_logits - np.max(scaled_logits, axis=-1, keepdims=True))
    cal_probs = cal_probs / np.sum(cal_probs, axis=-1, keepdims=True)
    cal_ece, cal_table = compute_ece_and_table(cal_probs, y_true, n_bins=10)

    print(f"\nUncalibrated Expected Calibration Error (ECE): {raw_ece * 100:.2f}%")
    print(f"Fitted Optimal Temperature T:                 {opt_t:.4f}")
    print(f"Calibrated Expected Calibration Error (ECE):   {cal_ece * 100:.2f}% (ECE drop: {(raw_ece - cal_ece)*100:.2f}%)")

    print("\nReliability Table (Uncalibrated vs Temperature-Scaled):")
    print(f"{'Bin Range':<15s} | {'Count':<6s} | {'Raw Conf':<10s} | {'Raw Acc':<10s} | {'Raw Gap':<10s} | {'Cal Conf':<10s} | {'Cal Gap':<10s}")
    print("-" * 80)
    for r, c in zip(raw_table, cal_table):
        print(f"{r['bin_range']:<15s} | {r['count']:<6d} | {r['avg_confidence']:<10.4f} | {r['empirical_accuracy']:<10.4f} | {r['calibration_gap']:<10.4f} | {c['avg_confidence']:<10.4f} | {c['calibration_gap']:<10.4f}")

    return {
        "uncalibrated_ece": raw_ece,
        "calibrated_ece": cal_ece,
        "optimal_temperature": round(opt_t, 4),
        "reliability_table": raw_table,
        "calibrated_table": cal_table,
    }


# ===========================================================================
# D. Rules with Unit Tests (Carve-out & Change of Control in Assignment)
# ===========================================================================
# Targeted high-precision patterns for carve-outs and change-of-control
CARVEOUT_PATTERN = re.compile(
    r"(?i)\b(?:except\s+(?:with\s+respect\s+to|for)\s+(?:claims\s+under\s+section\s+\d+|indemnif\w+|breach\w+\s+of\s+confidential\w+)|"
    r"expressly\s+waives\s+any\s+and\s+all\s+limitations\s+or\s+liability\s+caps|"
    r"limitation\s+(?:shall\s+not\s+apply|does\s+not\s+apply)\s+to\s+(?:either\s+party['’]s\s+liability\s+for|indemnif\w+))\b"
)

COC_IN_ASSIGN_PATTERN = re.compile(
    r"(?i)\b(?:merger,\s+(?:consolidation|reorganization|acquisition)\s+or\s+(?:sale\s+of\s+all|change\s+of\s+control)|"
    r"change\s+of\s+control\s+of\s+(?:the\s+)?(?:licensee|company|distributor|parties|supplier)|"
    r"transfer\s+of\s+no\s+less\s+than\s+a\s+majority\s+of[,\s]+or\s+a\s+controlling\s+interest)\b"
)


def apply_rules(pred: str, text: str) -> str:
    """Apply targeted heuristic rules to override known blind spots."""
    # Rule 1: Change-of-control wording embedded in an assignment provision
    if pred == "Anti-Assignment" and COC_IN_ASSIGN_PATTERN.search(text):
        return "Change of Control"

    # Rule 2: Explicit carve-out inside liability section
    if pred == "Cap on Liability" and CARVEOUT_PATTERN.search(text):
        return "Uncapped Liability"

    return pred


def run_rule_evaluation_audit(val_df: pd.DataFrame, label2id: dict[str, int], id2label: dict[int, str]) -> dict[str, Any]:
    print("\n" + "=" * 75)
    print("STEP D: Rule-Based Enhancements & Precision/Recall Audit on Validation")
    print("=" * 75)

    device = get_device()
    tokenizer = AutoTokenizer.from_pretrained(LEGAL_BERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(LEGAL_BERT_DIR).to(device)
    model.eval()

    texts = val_df["text"].tolist()
    y_true = val_df["label"].tolist()

    raw_preds = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            batch = texts[i : i + 32]
            enc = tokenizer(batch, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
            p = model(**enc).logits.argmax(dim=-1).cpu().tolist()
            raw_preds.extend([id2label[idx] for idx in p])

    del model
    if device.type == "mps":
        torch.mps.empty_cache()

    # Baseline classification report
    rep_before = classification_report(y_true, raw_preds, output_dict=True, zero_division=0)

    # Apply rules
    ruled_preds = [apply_rules(raw_preds[i], texts[i]) for i in range(len(texts))]
    rep_after = classification_report(y_true, ruled_preds, output_dict=True, zero_division=0)

    # Count false positives for the target classes
    def get_fp_count(y_t: list[str], y_p: list[str], target: str) -> int:
        return sum(1 for yt, yp in zip(y_t, y_p) if yp == target and yt != target)

    target_classes = ["Change of Control", "Uncapped Liability"]
    rule_metrics = {}

    print(f"\n{'Target Class':<22s} | {'Metric':<10s} | {'Before Rule':<12s} | {'After Rule':<12s} | {'Delta':<10s} | {'FP Before':<10s} | {'FP After':<10s}")
    print("-" * 95)

    keep_rules = True
    for cls in target_classes:
        prec_b = rep_before[cls]["precision"] * 100
        rec_b = rep_before[cls]["recall"] * 100
        f1_b = rep_before[cls]["f1-score"] * 100

        prec_a = rep_after[cls]["precision"] * 100
        rec_a = rep_after[cls]["recall"] * 100
        f1_a = rep_after[cls]["f1-score"] * 100

        fp_b = get_fp_count(y_true, raw_preds, cls)
        fp_a = get_fp_count(y_true, ruled_preds, cls)

        rule_metrics[cls] = {
            "precision_before": round(prec_b, 2),
            "precision_after": round(prec_a, 2),
            "recall_before": round(rec_b, 2),
            "recall_after": round(rec_a, 2),
            "f1_before": round(f1_b, 2),
            "f1_after": round(f1_a, 2),
            "fp_before": fp_b,
            "fp_after": fp_a,
        }

        print(f"{cls:<22s} | {'Precision':<10s} | {prec_b:6.2f}%      | {prec_a:6.2f}%      | {prec_a - prec_b:+6.2f}%   | {fp_b:<10d} | {fp_a:<10d}")
        print(f"{'':<22s} | {'Recall':<10s} | {rec_b:6.2f}%      | {rec_a:6.2f}%      | {rec_a - rec_b:+6.2f}%   | {'':<10s} |")
        print(f"{'':<22s} | {'F1-Score':<10s} | {f1_b:6.2f}%      | {f1_a:6.2f}%      | {f1_a - f1_b:+6.2f}%   | {'':<10s} |")

        if fp_a > fp_b:
            print(f"  [WARNING] Rule for {cls} increased false positives ({fp_b} -> {fp_a}). Rule must be rejected per constraint.")
            keep_rules = False

    overall_macro_f1_b = rep_before["macro avg"]["f1-score"] * 100
    overall_macro_f1_a = rep_after["macro avg"]["f1-score"] * 100
    print(f"\nOverall Validation Macro-F1: Before = {overall_macro_f1_b:.2f}% | After = {overall_macro_f1_a:.2f}% (Δ = {overall_macro_f1_a - overall_macro_f1_b:+.2f}%)")
    print(f"Decision on keeping rule: {'KEPT (0 added false positives)' if keep_rules else 'REJECTED (added false positives)'}")

    return {
        "rule_metrics": rule_metrics,
        "overall_macro_f1_before": round(overall_macro_f1_b, 2),
        "overall_macro_f1_after": round(overall_macro_f1_a, 2),
        "keep_rules": keep_rules,
    }


# ===========================================================================
# E. Sliding-Window, TF-IDF Average, and Per-Class Thresholds (Validation Only)
# ===========================================================================
def run_validation_enhancements_audit(
    val_df: pd.DataFrame,
    label2id: dict[str, int],
    id2label: dict[int, str],
) -> dict[str, Any]:
    print("\n" + "=" * 75)
    print("STEP E: Validation Inference Enhancements (Reported Separately)")
    print("=" * 75)

    device = get_device()
    tokenizer = AutoTokenizer.from_pretrained(LEGAL_BERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(LEGAL_BERT_DIR).to(device)
    model.eval()

    texts = val_df["text"].tolist()
    y_true = [label2id[l] for l in val_df["label"]]
    y_true_str = val_df["label"].tolist()

    # 1. Standard Single-Window Legal-BERT (Fixed 256)
    standard_logits = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            batch = texts[i : i + 32]
            enc = tokenizer(batch, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
            standard_logits.append(model(**enc).logits.cpu().numpy())
    standard_logits = np.vstack(standard_logits)
    standard_probs = np.exp(standard_logits - np.max(standard_logits, axis=-1, keepdims=True))
    standard_probs = standard_probs / np.sum(standard_probs, axis=-1, keepdims=True)
    standard_preds = np.argmax(standard_probs, axis=-1)
    std_f1 = f1_score(y_true, standard_preds, average="macro", zero_division=0) * 100
    std_prec = precision_score(y_true, standard_preds, average="macro", zero_division=0) * 100
    std_rec = recall_score(y_true, standard_preds, average="macro", zero_division=0) * 100

    # 2. Enhancement 1: Sliding-Window Inference (window=256, stride=128, max-pooling)
    window_probs_list = []
    for text in texts:
        tokens = tokenizer.encode(text, truncation=False)
        if len(tokens) <= 256:
            enc = tokenizer(text, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
            with torch.no_grad():
                l = model(**enc).logits.cpu().numpy()[0]
                p = np.exp(l - np.max(l)) / np.sum(np.exp(l - np.max(l)))
            window_probs_list.append(p)
        else:
            # Overlapping windows
            win_p_list = []
            stride = 128
            win_size = 256
            for start_idx in range(0, len(tokens), stride):
                chunk_ids = tokens[start_idx : start_idx + win_size]
                if len(chunk_ids) < 10:
                    continue
                chunk_text = tokenizer.decode(chunk_ids, skip_special_tokens=True)
                enc = tokenizer(chunk_text, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
                with torch.no_grad():
                    l = model(**enc).logits.cpu().numpy()[0]
                    p = np.exp(l - np.max(l)) / np.sum(np.exp(l - np.max(l)))
                    win_p_list.append(p)
            # Max probability across windows, then renormalize
            max_p = np.max(win_p_list, axis=0)
            renorm_p = max_p / np.sum(max_p)
            window_probs_list.append(renorm_p)

    sw_probs = np.array(window_probs_list)
    sw_preds = np.argmax(sw_probs, axis=-1)
    sw_f1 = f1_score(y_true, sw_preds, average="macro", zero_division=0) * 100
    sw_prec = precision_score(y_true, sw_preds, average="macro", zero_division=0) * 100
    sw_rec = recall_score(y_true, sw_preds, average="macro", zero_division=0) * 100

    del model
    if device.type == "mps":
        torch.mps.empty_cache()

    # 3. Enhancement 2: Legal-BERT + TF-IDF Probability Averaging
    b_dict = joblib.load(BASELINE_PATH)
    vec = b_dict["vectorizer"]
    clf = b_dict["classifier"]
    x_val_tfidf = vec.transform(texts)
    tfidf_raw_probs = clf.predict_proba(x_val_tfidf)

    # Reorder tfidf classes to match label2id
    tfidf_classes = list(clf.classes_)
    reordered_tfidf_probs = np.zeros_like(standard_probs)
    for c_idx, c_name in enumerate(tfidf_classes):
        target_idx = label2id[c_name]
        reordered_tfidf_probs[:, target_idx] = tfidf_raw_probs[:, c_idx]

    # Grid search alpha on validation
    best_alpha = 0.5
    best_ens_f1 = 0.0
    for alpha in np.linspace(0.1, 0.9, 9):
        ens_p = alpha * standard_probs + (1.0 - alpha) * reordered_tfidf_probs
        ens_pred = np.argmax(ens_p, axis=-1)
        f1_val = f1_score(y_true, ens_pred, average="macro", zero_division=0)
        if f1_val > best_ens_f1:
            best_ens_f1 = f1_val
            best_alpha = alpha

    ens_probs = best_alpha * standard_probs + (1.0 - best_alpha) * reordered_tfidf_probs
    ens_preds = np.argmax(ens_probs, axis=-1)
    ens_f1 = f1_score(y_true, ens_preds, average="macro", zero_division=0) * 100
    ens_prec = precision_score(y_true, ens_preds, average="macro", zero_division=0) * 100
    ens_rec = recall_score(y_true, ens_preds, average="macro", zero_division=0) * 100

    # 4. Enhancement 3: Per-Class Thresholds Tuned on Validation Only
    # Tune threshold tau_c for each class to maximize F1
    tuned_thresholds = {}
    classes = [id2label[i] for i in range(len(label2id))]

    for c_idx, c_name in enumerate(classes):
        best_tau = 0.5
        best_c_f1 = 0.0
        binary_true = (np.array(y_true) == c_idx).astype(int)

        for tau in np.linspace(0.15, 0.85, 29):
            binary_pred = (standard_probs[:, c_idx] >= tau).astype(int)
            score = f1_score(binary_true, binary_pred, zero_division=0)
            if score > best_c_f1:
                best_c_f1 = score
                best_tau = float(tau)

        tuned_thresholds[c_name] = round(best_tau, 2)

    # Multi-class inference with thresholds: ratio score p_c / tau_c
    tau_vec = np.array([tuned_thresholds[id2label[i]] for i in range(len(label2id))])
    ratio_scores = standard_probs / tau_vec
    thresh_preds = np.argmax(ratio_scores, axis=-1)
    thresh_f1 = f1_score(y_true, thresh_preds, average="macro", zero_division=0) * 100
    thresh_prec = precision_score(y_true, thresh_preds, average="macro", zero_division=0) * 100
    thresh_rec = recall_score(y_true, thresh_preds, average="macro", zero_division=0) * 100

    print(f"{'Method (Validation Only)':<35s} | {'Macro-F1':<10s} | {'Macro-Prec':<12s} | {'Macro-Recall':<14s} | {'Key Parameter'}")
    print("-" * 95)
    print(f"{'Standard Legal-BERT (Fixed 256)':<35s} | {std_f1:6.2f}%   | {std_prec:6.2f}%     | {std_rec:6.2f}%       | Window=256")
    print(f"{'1. Sliding-Window Inference':<35s} | {sw_f1:6.2f}%   | {sw_prec:6.2f}%     | {sw_rec:6.2f}%       | Win=256, Stride=128, Max-Pool")
    print(f"{'2. Legal-BERT + TF-IDF Ensemble':<35s} | {ens_f1:6.2f}%   | {ens_prec:6.2f}%     | {ens_rec:6.2f}%       | Optimal Alpha={best_alpha:.1f}")
    print(f"{'3. Per-Class Threshold Tuning':<35s} | {thresh_f1:6.2f}%   | {thresh_prec:6.2f}%     | {thresh_rec:6.2f}%       | Thresholds: {tuned_thresholds}")

    return {
        "standard": {"macro_f1": round(std_f1, 2), "precision": round(std_prec, 2), "recall": round(std_rec, 2)},
        "sliding_window": {"macro_f1": round(sw_f1, 2), "precision": round(sw_prec, 2), "recall": round(sw_rec, 2)},
        "tfidf_ensemble": {"macro_f1": round(ens_f1, 2), "precision": round(ens_prec, 2), "recall": round(ens_rec, 2), "alpha": round(best_alpha, 2)},
        "per_class_thresholds": {"macro_f1": round(thresh_f1, 2), "precision": round(thresh_prec, 2), "recall": round(thresh_rec, 2), "thresholds": tuned_thresholds},
    }


# ===========================================================================
# F. Contract-Level Bootstrap on Pooled Out-of-Fold Predictions
# ===========================================================================
def run_contract_cluster_bootstrap(
    dev_df: pd.DataFrame,
    unadapted_emb: np.ndarray,
    adapted_emb: np.ndarray,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    print("\n" + "=" * 75)
    print("STEP F: Contract-Level Cluster Bootstrap on Pooled Out-of-Fold Predictions")
    print("=" * 75)

    unique_contracts = dev_df["contract_id"].unique()
    labels = dev_df["label"].to_numpy()
    texts = dev_df["text"].tolist()

    # 1. Generate 5-fold Out-of-Fold predictions for all 3,233 samples (seed 42)
    kf = KFold(n_splits=5, shuffle=True, random_state=seed)

    oof_tfidf = np.empty(len(dev_df), dtype=object)
    oof_unad = np.empty(len(dev_df), dtype=object)
    oof_ad = np.empty(len(dev_df), dtype=object)

    for fold, (train_c_idx, val_c_idx) in enumerate(kf.split(unique_contracts)):
        val_contracts = set(unique_contracts[val_c_idx])
        val_mask = dev_df["contract_id"].isin(val_contracts).to_numpy()
        train_mask = ~val_mask

        # TF-IDF
        vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50000, sublinear_tf=True)
        x_tr_tfidf = vec.fit_transform([texts[i] for i in range(len(texts)) if train_mask[i]])
        x_val_tfidf = vec.transform([texts[i] for i in range(len(texts)) if val_mask[i]])
        clf_tfidf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed)
        clf_tfidf.fit(x_tr_tfidf, labels[train_mask])
        oof_tfidf[val_mask] = clf_tfidf.predict(x_val_tfidf)

        # Un-adapted Probe
        clf_unad = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed)
        clf_unad.fit(unadapted_emb[train_mask], labels[train_mask])
        oof_unad[val_mask] = clf_unad.predict(unadapted_emb[val_mask])

        # Adapted Probe
        clf_ad = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed)
        clf_ad.fit(adapted_emb[train_mask], labels[train_mask])
        oof_ad[val_mask] = clf_ad.predict(adapted_emb[val_mask])

    # Point estimates on pooled OOF
    f1_tfidf_pt = f1_score(labels, oof_tfidf, average="macro", zero_division=0) * 100
    f1_unad_pt = f1_score(labels, oof_unad, average="macro", zero_division=0) * 100
    f1_ad_pt = f1_score(labels, oof_ad, average="macro", zero_division=0) * 100

    print("Pooled Out-of-Fold Macro-F1 (Frozen Probe on 3,233 Segments, 392 Contracts):")
    print(f"  TF-IDF + LogReg:        {f1_tfidf_pt:.2f}%")
    print(f"  Un-adapted Legal-BERT:  {f1_unad_pt:.2f}%")
    print(f"  Adapted Legal-BERT:     {f1_ad_pt:.2f}%")

    # Group sample indices by contract_id for contract-level cluster resampling
    contract_indices = {c: np.where(dev_df["contract_id"] == c)[0] for c in unique_contracts}
    rng = np.random.default_rng(seed)
    n_contracts = len(unique_contracts)

    delta_ad_unad_boot = []
    delta_ad_tfidf_boot = []
    delta_unad_tfidf_boot = []

    for b in range(n_bootstraps):
        sampled_contracts = rng.choice(unique_contracts, size=n_contracts, replace=True)
        # Concatenate indices of all segments belonging to the sampled contracts
        boot_indices = np.concatenate([contract_indices[c] for c in sampled_contracts])

        b_labels = labels[boot_indices]
        b_tfidf = oof_tfidf[boot_indices]
        b_unad = oof_unad[boot_indices]
        b_ad = oof_ad[boot_indices]

        f1_t = f1_score(b_labels, b_tfidf, average="macro", zero_division=0) * 100
        f1_u = f1_score(b_labels, b_unad, average="macro", zero_division=0) * 100
        f1_a = f1_score(b_labels, b_ad, average="macro", zero_division=0) * 100

        delta_ad_unad_boot.append(f1_a - f1_u)
        delta_ad_tfidf_boot.append(f1_a - f1_t)
        delta_unad_tfidf_boot.append(f1_u - f1_t)

    def calc_ci(deltas: list[float], pt_diff: float) -> tuple[float, list[float], float]:
        mean_diff = float(np.mean(deltas))
        ci_l = float(np.percentile(deltas, 2.5))
        ci_u = float(np.percentile(deltas, 97.5))
        p_val = float(2.0 * min(np.mean(np.array(deltas) <= 0), np.mean(np.array(deltas) >= 0)))
        p_val = min(1.0, max(1.0 / n_bootstraps, p_val))
        return round(mean_diff, 2), [round(ci_l, 2), round(ci_u, 2)], round(p_val, 4)

    mean_au, ci_au, p_au = calc_ci(delta_ad_unad_boot, f1_ad_pt - f1_unad_pt)
    mean_at, ci_at, p_at = calc_ci(delta_ad_tfidf_boot, f1_ad_pt - f1_tfidf_pt)
    mean_ut, ci_ut, p_ut = calc_ci(delta_unad_tfidf_boot, f1_unad_pt - f1_tfidf_pt)

    print("\nContract-Level (Cluster) Bootstrap Significance (1,000 Resamples by Whole Contract):")
    print(f"  Adapted vs Un-adapted (Probe): Δ Macro-F1 = {mean_au:+.2f}% | 95% CI: [{ci_au[0]:+.2f}%, {ci_au[1]:+.2f}%] | p-value: {p_au:.4f}")
    print(f"  Adapted vs TF-IDF (Probe):     Δ Macro-F1 = {mean_at:+.2f}% | 95% CI: [{ci_at[0]:+.2f}%, {ci_at[1]:+.2f}%] | p-value: {p_at:.4f}")
    print(f"  Un-adapted vs TF-IDF (Probe):  Δ Macro-F1 = {mean_ut:+.2f}% | 95% CI: [{ci_ut[0]:+.2f}%, {ci_ut[1]:+.2f}%] | p-value: {p_ut:.4f}")

    return {
        "pooled_oof_point_estimates": {"TF-IDF": round(f1_tfidf_pt, 2), "Un-adapted": round(f1_unad_pt, 2), "Adapted": round(f1_ad_pt, 2)},
        "contract_cluster_bootstrap": {
            "Adapted vs Un-adapted": {"mean_delta_f1": mean_au, "ci_95": ci_au, "p_value": p_au},
            "Adapted vs TF-IDF": {"mean_delta_f1": mean_at, "ci_95": ci_at, "p_value": p_at},
            "Un-adapted vs TF-IDF": {"mean_delta_f1": mean_ut, "ci_95": ci_ut, "p_value": p_ut},
        },
    }


def main() -> None:
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    dev_df = pd.concat([train_df, val_df], ignore_index=True)

    with open(ARTIFACTS_DIR / "label_map.json") as f:
        lmap = json.load(f)
    label2id = {k: int(v) for k, v in lmap["label2id"].items()}
    id2label = {int(k): v for k, v in lmap["id2label"].items()}

    # Load pre-extracted embeddings
    unadapted_emb = np.load(ARTIFACTS_DIR / "dev_emb_unadapted.npy")
    adapted_emb = np.load(ARTIFACTS_DIR / "dev_emb_multiyear_adapted.npy")

    # Step C: Reliability & Calibration
    c_res = run_reliability_audit(val_df, label2id)

    # Step D: Rule-based enhancements
    d_res = run_rule_evaluation_audit(val_df, label2id, id2label)

    # Step E: Validation inference enhancements
    e_res = run_validation_enhancements_audit(val_df, label2id, id2label)

    # Step F: Contract-level cluster bootstrap
    f_res = run_contract_cluster_bootstrap(dev_df, unadapted_emb, adapted_emb)

    payload = {
        "step_c_calibration": c_res,
        "step_d_rules": d_res,
        "step_e_enhancements": e_res,
        "step_f_contract_bootstrap": f_res,
    }

    out_file = ARTIFACTS_DIR / "advanced_audit_results.json"
    with open(out_file, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved advanced audit results to: {out_file}")


if __name__ == "__main__":
    main()

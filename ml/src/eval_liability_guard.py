"""Evaluate Liability Guard and Secondary Label on val_natural.csv using saved probabilities."""
import ast
import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_val_natural")

REPO_ROOT = Path("/Users/chetanajatpur/Desktop/clauseguard")
VAL_PATH = REPO_ROOT / "ml" / "data" / "processed" / "val_natural.csv"
PROBS_PATH = REPO_ROOT / "ml" / "artifacts" / "legal_bert_val_natural_probs.npy"
LABEL_MAP_PATH = REPO_ROOT / "ml" / "artifacts" / "label_map.json"
OP_PATH = REPO_ROOT / "ml" / "artifacts" / "operating_points.json"

# Liability Guard Pattern
# Matches carve-outs and explicit waivers/uncapped liability statements
LIABILITY_GUARD_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"except\s+(?:with\s+respect\s+to|for)\s+(?:claims\s+under\s+section\s+\d+|indemnif\w+|breach\w+\s+of\s+confidential\w+)|"
    r"expressly\s+waives\s+any\s+and\s+all\s+limitations\s+or\s+liability\s+caps|"
    r"limitation\s+(?:shall\s+not\s+apply|does\s+not\s+apply)\s+to\s+(?:either\s+party['’]s\s+liability\s+for|indemnif\w+)|"
    r"(?:shall\s+not\s+be|is\s+not|not)\s+subject\s+to\s+any\s+(?:limit|limitation|cap)|"
    r"unlimited\s+(?:and\s+subject\s+to\s+no\s+cap|liability)|"
    r"(?:subject\s+to\s+)?no\s+(?:cap|limit)\s+(?:whatsoever)?|"
    r"without\s+limit(?:ation)?\s+as\s+to\s+amount"
    r")\b"
)


def run_evaluation():
    # Load label map
    with open(LABEL_MAP_PATH) as f:
        lmap_raw = json.load(f)
    if "label2id" in lmap_raw:
        label2id = lmap_raw["label2id"]
        id2label = {int(k): v for k, v in lmap_raw["id2label"].items()}
    else:
        label2id = lmap_raw
        id2label = {v: k for k, v in label2id.items()}

    no_clause_idx = label2id["No Clause"]
    sub_indices = [idx for name, idx in label2id.items() if name != "No Clause"]
    sub_names = [id2label[i] for i in sub_indices]

    # Load operating points
    with open(OP_PATH) as f:
        op_data = json.load(f)
    presets = op_data.get("presets", {})
    tau_balanced = presets.get("balanced", {}).get("tau", 0.035452)
    logger.info("Balanced tau=%.6f", tau_balanced)

    # Load val_natural
    val_df = pd.read_csv(VAL_PATH)
    logger.info("Loaded %d validation units from %s", len(val_df), VAL_PATH)
    unique_contracts = val_df["contract"].nunique()
    logger.info("Unique validation contracts: %d", unique_contracts)

    # Load calibrated probabilities
    all_cal_probs = np.load(PROBS_PATH)
    logger.info("Loaded probabilities shape: %s", all_cal_probs.shape)

    # 1. Base Legal-BERT predictions at balanced preset
    p_no_clause = all_cal_probs[:, no_clause_idx]
    flagged_base = p_no_clause < tau_balanced

    pred_labels_base = []
    pred_confs_base = []
    second_labels = []
    second_confs = []

    for i, flag in enumerate(flagged_base):
        row = all_cal_probs[i]
        if flag:
            sub_probs = [(sub_names[k], float(row[sub_indices[k]])) for k in range(len(sub_indices))]
            sub_probs.sort(key=lambda x: x[1], reverse=True)
            top1_label, top1_prob = sub_probs[0]
            top2_label, top2_prob = sub_probs[1]
            pred_labels_base.append(top1_label)
            pred_confs_base.append(top1_prob)
            second_labels.append(top2_label)
            second_confs.append(top2_prob)
        else:
            pred_labels_base.append("No Clause")
            pred_confs_base.append(float(row[no_clause_idx]))
            second_labels.append(None)
            second_confs.append(0.0)

    val_df["pred_base"] = pred_labels_base
    val_df["flagged_base"] = flagged_base
    val_df["second_label"] = second_labels
    val_df["second_conf"] = second_confs

    # 2. Apply Liability Guard
    # If flagged and predicted Cap on Liability, and text matches LIABILITY_GUARD_PATTERN -> override to Uncapped Liability
    pred_labels_guard = []
    overridden_count = 0
    overridden_indices = []

    texts = val_df["text"].tolist()
    for i, (pred, flag, text) in enumerate(zip(pred_labels_base, flagged_base, texts)):
        if flag and pred == "Cap on Liability" and LIABILITY_GUARD_PATTERN.search(str(text)):
            pred_labels_guard.append("Uncapped Liability")
            overridden_count += 1
            overridden_indices.append(i)
        else:
            pred_labels_guard.append(pred)

    val_df["pred_guard"] = pred_labels_guard
    logger.info("Liability Guard triggered on %d units in val_natural", overridden_count)

    # Inspect overridden units
    overridden_details = []
    for idx in overridden_indices:
        row = val_df.iloc[idx]
        overridden_details.append({
            "idx": int(idx),
            "contract": str(row["contract"]),
            "true_label": str(row["label"]),
            "secondary_labels": str(row.get("secondary_labels", "")),
            "pred_before": str(row["pred_base"]),
            "pred_after": str(row["pred_guard"]),
            "text_snippet": str(row["text"])[:150],
        })

    # Metrics before vs after Liability Guard for Uncapped Liability and Cap on Liability
    def compute_class_metrics(df, pred_col):
        results = {}
        for cls in ["Uncapped Liability", "Cap on Liability"]:
            true_pos = (df["label"] == cls)
            pred_pos = (df[pred_col] == cls)
            tp = int((true_pos & pred_pos).sum())
            fp = int((~true_pos & pred_pos).sum())
            fn = int((true_pos & ~pred_pos).sum())
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            results[cls] = {
                "tp": tp, "fp": fp, "fn": fn,
                "precision": round(float(prec) * 100, 2),
                "recall": round(float(rec) * 100, 2),
                "f1": round(float(f1) * 100, 2),
            }
        return results

    metrics_before = compute_class_metrics(val_df, "pred_base")
    metrics_after = compute_class_metrics(val_df, "pred_guard")

    # 3. Secondary Label Audit ("May also contain: <label>")
    flagged_df = val_df[val_df["flagged_base"]].copy()
    secondary_candidates = flagged_df[flagged_df["second_conf"] >= 0.20].copy()

    total_flagged = len(flagged_df)
    total_secondary = len(secondary_candidates)
    sec_pct = (total_secondary / total_flagged) * 100 if total_flagged > 0 else 0.0

    logger.info(
        "Secondary label (prob >= 0.20) appears on %d / %d flagged units (%.2f%%)",
        total_secondary, total_flagged, sec_pct
    )

    # Evaluate true vs false chips
    true_chips = 0
    false_chips = 0
    chips_by_contract = {}

    for _, row in secondary_candidates.iterrows():
        cid = row["contract"]
        c_second = row["second_label"]
        true_lbl = row["label"]
        raw_sec = row.get("secondary_labels", "")
        parsed_sec = []
        if pd.notna(raw_sec) and raw_sec.strip():
            try:
                parsed_sec = ast.literal_eval(raw_sec) if isinstance(raw_sec, str) else list(raw_sec)
            except Exception:
                parsed_sec = []

        is_true_chip = (c_second == true_lbl) or (c_second in parsed_sec)
        if is_true_chip:
            true_chips += 1
        else:
            false_chips += 1
            chips_by_contract[cid] = chips_by_contract.get(cid, 0) + 1

    false_chips_per_contract = false_chips / unique_contracts

    logger.info(
        "Secondary Label Stats: True Chips=%d, False Chips=%d, False Chips/Contract=%.4f (Threshold: 1.0)",
        true_chips, false_chips, false_chips_per_contract
    )

    # Also test on DOC-08
    doc08_path = REPO_ROOT / "clauseguard-testkit" / "contracts" / "DOC-08_partnership_compound.txt"
    doc08_cards = []
    if doc08_path.exists():
        from app.services.classifier import classifier
        classifier.load(
            model_path=str(REPO_ROOT / "ml" / "artifacts" / "legal_bert_final"),
            label_map_path=str(LABEL_MAP_PATH),
            operating_points_path=str(OP_PATH),
        )
        from app.services.segmenter import segment_text
        doc08_text = doc08_path.read_text()
        doc08_chunks = segment_text(doc08_text)
        doc08_preds = classifier.predict(doc08_chunks, sensitivity="balanced")

        for idx, (chunk, pred) in enumerate(zip(doc08_chunks, doc08_preds)):
            doc08_cards.append({
                "section": idx + 1,
                "text_snippet": chunk[:80].replace("\n", " "),
                "flagged": pred["flagged"],
                "primary_label": pred["label"],
                "confidence": pred["confidence"],
                "risk_tier": pred["risk_tier"],
                "secondary_label": pred.get("secondary_label"),
                "second_prob": pred.get("second_prob"),
            })

    results = {
        "liability_guard": {
            "triggered_count": overridden_count,
            "overridden_units": overridden_details,
            "metrics_before": metrics_before,
            "metrics_after": metrics_after,
        },
        "secondary_label": {
            "total_flagged_units": total_flagged,
            "units_with_second_prob_ge_20": total_secondary,
            "pct_of_flagged": round(sec_pct, 2),
            "true_chips": true_chips,
            "false_chips": false_chips,
            "false_chips_per_contract": round(false_chips_per_contract, 4),
            "gate_passed": bool(false_chips_per_contract <= 1.0),
        },
        "doc08_analysis": doc08_cards,
    }

    out_file = REPO_ROOT / "ml" / "artifacts" / "liability_guard_and_secondary_audit.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Saved audit results to %s", out_file)
    print("\n" + json.dumps(results, indent=2))


if __name__ == "__main__":
    run_evaluation()

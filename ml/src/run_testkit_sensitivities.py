"""Evaluate clauseguard-testkit at strict, balanced, and thorough sensitivity presets."""
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

from app.services.classifier import ClauseClassifier
from app.services.segmenter import segment_text

logging.basicConfig(level=logging.WARNING)

TESTKIT_DIR = REPO_ROOT / "clauseguard-testkit"
CONTRACTS_DIR = TESTKIT_DIR / "contracts"
GT_PATH = TESTKIT_DIR / "ground_truth.json"

with open(GT_PATH) as f:
    ground_truth = json.load(f)

print(f"Loaded ground truth for {len(ground_truth)} contracts:")
for k in ground_truth.keys():
    print(f"  • {k} (Difficulty: {ground_truth[k]['difficulty']}, Labels: {len(ground_truth[k]['labels'])})")

# Load classifier
clf = ClauseClassifier()
clf.load(
    model_path=str(REPO_ROOT / "ml" / "artifacts" / "legal_bert_final"),
    label_map_path=str(REPO_ROOT / "ml" / "artifacts" / "label_map.json"),
    backend="legal_bert",
    temperature=0.9270,
    operating_points_path=str(REPO_ROOT / "ml" / "artifacts" / "operating_points.json"),
)

presets = ["strict", "balanced", "thorough"]

all_results = {}

for preset in presets:
    tau = clf.presets[preset]["tau"]
    print("\n" + "=" * 90)
    print(f"RUNNING TESTKIT AT SENSITIVITY: {preset.upper()} (tau = {tau:.6f})")
    print("=" * 90)
    
    total_sections = 0
    total_true_pos = 0
    total_true_neg = 0
    tp_flagged = 0
    tp_correct = 0
    false_alarms = 0
    flagged_harmless_list = []
    
    contract_summaries = []

    for fn, meta in ground_truth.items():
        contract_path = CONTRACTS_DIR / fn
        if not contract_path.exists():
            print(f"WARNING: File {contract_path} does not exist!")
            continue
            
        text = contract_path.read_text(encoding="utf-8")
        chunks = segment_text(text)
        expected = meta["labels"]
        
        preds = clf.predict(chunks, sensitivity=preset)
        min_len = min(len(chunks), len(expected))
        
        c_flags = 0
        c_fa = 0
        c_tp = 0
        
        for i in range(min_len):
            chunk = chunks[i]
            true_label = expected[i]
            pred = preds[i]
            is_flagged = pred["flagged"]
            pred_label = pred["label"]
            conf = pred["calibrated_probability"]
            
            is_pos = (true_label != "No Clause")
            is_neg = (true_label == "No Clause")
            
            total_sections += 1
            if is_pos:
                total_true_pos += 1
                if is_flagged:
                    tp_flagged += 1
                    c_flags += 1
                    c_tp += 1
                    if pred_label == true_label:
                        tp_correct += 1
            else:
                total_true_neg += 1
                if is_flagged:
                    false_alarms += 1
                    c_flags += 1
                    c_fa += 1
                    flagged_harmless_list.append({
                        "contract": fn,
                        "section_idx": i + 1,
                        "text": chunk,
                        "predicted_label": pred_label,
                        "risk_tier": pred["risk_tier"],
                        "confidence": conf,
                    })

        contract_summaries.append({
            "contract": fn,
            "difficulty": meta["difficulty"],
            "chunks": min_len,
            "flags": c_flags,
            "tp": c_tp,
            "fa": c_fa,
        })
    
    precision = tp_flagged / (tp_flagged + false_alarms) * 100 if (tp_flagged + false_alarms) > 0 else 0.0
    recall_flagged = tp_flagged / total_true_pos * 100 if total_true_pos > 0 else 0.0
    recall_correct = tp_correct / total_true_pos * 100 if total_true_pos > 0 else 0.0
    
    print(f"\n--- Aggregate Results for {preset.upper()} ---")
    print(f"Total Sections: {total_sections} ({total_true_pos} True Risky Clauses, {total_true_neg} Harmless/No Clause)")
    print(f"Total Flagged: {tp_flagged + false_alarms}")
    print(f"True Positives Flagged: {tp_flagged}/{total_true_pos} (Recall Flagged: {recall_flagged:.2f}%)")
    print(f"True Positives Correct Class: {tp_correct}/{total_true_pos} (Recall Correct: {recall_correct:.2f}%)")
    print(f"False Alarms (Flagged Harmless): {false_alarms}/{total_true_neg}")
    print(f"Precision: {precision:.2f}%")
    
    print("\nContract breakdown:")
    for cs in contract_summaries:
        print(f"  • {cs['contract']:<32} | Chunks: {cs['chunks']:<2} | Flags: {cs['flags']:<2} | TP: {cs['tp']:<2} | FA: {cs['fa']:<2}")
        
    print(f"\nFlagged Harmless Sections count: {len(flagged_harmless_list)}")
    if flagged_harmless_list:
        print("-" * 80)
        print("DETAILS OF FLAGGED HARMLESS SECTIONS:")
        for idx, fh in enumerate(flagged_harmless_list, 1):
            print(f"\n[{idx}] Contract: {fh['contract']} (Section #{fh['section_idx']})")
            print(f"    Predicted Class: {fh['predicted_label']} (Tier: {fh['risk_tier']}, Conf: {fh['confidence']*100:.2f}%)")
            snippet = fh['text'].replace('\n', ' ').strip()
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."
            print(f"    Text: \"{snippet}\"")
    else:
        print("  -> None (Zero harmless sections flagged!)")
        
    all_results[preset] = {
        "tau": tau,
        "total_sections": total_sections,
        "true_positives": total_true_pos,
        "true_negatives": total_true_neg,
        "tp_flagged": tp_flagged,
        "tp_correct": tp_correct,
        "false_alarms": false_alarms,
        "precision": precision,
        "recall_flagged": recall_flagged,
        "recall_correct": recall_correct,
        "flagged_harmless": flagged_harmless_list,
    }

# Save output
with open(TESTKIT_DIR / "results" / "testkit_sensitivity_evaluation.json", "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\nSaved testkit sensitivity results to {TESTKIT_DIR / 'results' / 'testkit_sensitivity_evaluation.json'}")

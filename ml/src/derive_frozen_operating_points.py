"""Re-derive frozen operating points on val_natural with single rule: P_calibrated(No Clause) < tau."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
probs = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")

with open(ARTIFACTS_DIR / "label_map.json") as f:
    label_data = json.load(f)
label2id = label_data["label2id"]
id2label = {int(k): v for k, v in label_data["id2label"].items()}
class_names = [id2label[i] for i in range(11)]

no_clause_idx = label2id["No Clause"]
sub_indices = [i for i in range(11) if i != no_clause_idx]
sub_names = [id2label[i] for i in sub_indices]

p_no_clause = probs[:, no_clause_idx]
sub_probs = probs[:, sub_indices]
pred_sub = np.array([sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)])

y_true = val_nat["label"].to_numpy()
is_neg = (y_true == "No Clause")
is_pos = (y_true != "No Clause")
total_positives = int(is_pos.sum())  # 501
n_contracts = val_nat["contract"].nunique()  # 76

sorted_negs = np.sort(p_no_clause[is_neg])

presets = {}
preset_configs = [
    ("strict", 3),
    ("balanced", 8),
    ("thorough", 12),
]

print("=" * 80)
print("FROZEN OPERATING POINTS DERIVATION ON VAL_NATURAL (T=0.9270)")
print("=" * 80)

for name, target_fa_c in preset_configs:
    target_fa_total = int(round(target_fa_c * n_contracts))
    thresh = float(sorted_negs[target_fa_total - 1])

    flagged = (p_no_clause < thresh)
    actual_fa = int((flagged & is_neg).sum())
    actual_fa_c = round(actual_fa / n_contracts, 2)
    flags_count = int(flagged.sum())

    tp_flagged = int((flagged & is_pos).sum())
    tp_correct = int((flagged & is_pos & (pred_sub == y_true)).sum())

    rec_flagged = round(tp_flagged / total_positives * 100, 2)
    rec_correct = round(tp_correct / total_positives * 100, 2)
    precision = round(tp_flagged / flags_count * 100, 2) if flags_count > 0 else 0.0

    print(f"\nPreset '{name}' (Target {target_fa_c} FA/contract):")
    print(f"  Threshold (tau):           {thresh:.6f}")
    print(f"  Flags:                     {flags_count}")
    print(f"  False Alarms:              {actual_fa} ({actual_fa_c} FA/contract)")
    print(f"  True Positives (Flagged):  {tp_flagged} / {total_positives} ({rec_flagged}%)")
    print(f"  True Positives (Correct):  {tp_correct} / {total_positives} ({rec_correct}%)")
    print(f"  Precision:                 {precision}%")

    presets[name] = {
        "target_fa_per_contract": target_fa_c,
        "tau": round(thresh, 6),
        "actual_fa_per_contract": actual_fa_c,
        "flags_count": flags_count,
        "fa_count": actual_fa,
        "tp_flagged": tp_flagged,
        "tp_correct": tp_correct,
        "total_positives": total_positives,
        "recall_flagged": rec_flagged,
        "recall_correct": rec_correct,
        "precision": precision,
    }

output_data = {
    "model": "nlpaueb/legal-bert-base-uncased",
    "checkpoint": "ml/artifacts/legal_bert_final",
    "seed": 42,
    "temperature": 0.9270,
    "rule": "P_calibrated(No Clause) < tau",
    "validation_contracts": n_contracts,
    "validation_units": len(val_nat),
    "presets": presets,
}

out_path = ARTIFACTS_DIR / "operating_points.json"
with open(out_path, "w") as f:
    json.dump(output_data, f, indent=2)

print(f"\nSaved operating points to {out_path}")

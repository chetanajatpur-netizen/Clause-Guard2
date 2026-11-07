"""Sweep May-Also-Contain probability cutoff on val_natural.csv."""
import ast
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

val_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
probs = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")

with open(ARTIFACTS_DIR / "label_map.json") as f:
    lmap = json.load(f)["label2id"]
id2label = {v: k for k, v in lmap.items()}

no_clause_idx = lmap["No Clause"]
sub_indices = [idx for name, idx in lmap.items() if name != "No Clause"]
sub_names = [id2label[i] for i in sub_indices]

with open(ARTIFACTS_DIR / "operating_points.json") as f:
    tau_bal = json.load(f)["presets"]["balanced"]["tau"]

n_c = 76
p_nc = probs[:, no_clause_idx]
flagged = (p_nc < tau_bal)
units_flagged = np.where(flagged)[0]

top1_list = []
top2_list = []
prob2_list = []

for idx in units_flagged:
    sp = [(sub_names[k], float(probs[idx, sub_indices[k]])) for k in range(len(sub_indices))]
    sp.sort(key=lambda x: x[1], reverse=True)
    top1_list.append(sp[0][0])
    top2_list.append(sp[1][0])
    prob2_list.append(sp[1][1])

prob2_arr = np.array(prob2_list)
top1_arr = np.array(top1_list)
top2_arr = np.array(top2_list)

true_labels = val_df.iloc[units_flagged]["label"].to_numpy()
sec_labels_raw = val_df.iloc[units_flagged]["secondary_labels"].tolist()

sec_parsed = []
for s in sec_labels_raw:
    try:
        sec_parsed.append(ast.literal_eval(s) if isinstance(s, str) else list(s))
    except:
        sec_parsed.append([])

print("=" * 105)
print("MAY-ALSO-CONTAIN PROBABILITY CUTOFF SWEEP (val_natural.csv, 76 contracts, 1,012 flagged units)")
print("=" * 105)
header = f"{'Cutoff':<8} | {'Total Chips':<11} | {'Chips/c':<8} | {'True Sec Match':<15} | {'Recoveries':<12} | {'False Chips':<12} | {'False Chips/c':<14} | {'Status'}"
print(header)
print("-" * 105)

sweep_results = {}
for cutoff in [0.20, 0.25, 0.30, 0.35, 0.40]:
    mask = (prob2_arr >= cutoff)
    total_chips = int(mask.sum())
    chips_per_c = total_chips / n_c
    
    true_sec = 0
    recoveries = 0
    false_chips = 0
    
    for i in np.where(mask)[0]:
        t1 = top1_arr[i]
        t2 = top2_arr[i]
        yl = true_labels[i]
        secs = sec_parsed[i]
        
        is_sec = (t2 in secs)
        is_rec = (t1 != yl and t2 == yl and yl != "No Clause")
        
        if is_sec:
            true_sec += 1
        if is_rec:
            recoveries += 1
            
        if not is_sec and not is_rec:
            false_chips += 1
            
    false_chips_per_c = false_chips / n_c
    status = "Pass (<= 1.0)" if false_chips_per_c <= 1.0 else "Fail (> 1.0)"
    sweep_results[str(cutoff)] = {
        "cutoff": cutoff,
        "total_chips": total_chips,
        "chips_per_contract": round(chips_per_c, 4),
        "true_secondary_matches": true_sec,
        "correct_class_recoveries": recoveries,
        "false_chips": false_chips,
        "false_chips_per_contract": round(false_chips_per_c, 4),
        "gate_passed": bool(false_chips_per_c <= 1.0),
    }
    print(f"{cutoff:<8.2f} | {total_chips:<11d} | {chips_per_c:<8.2f} | {true_sec:<15d} | {recoveries:<12d} | {false_chips:<12d} | {false_chips_per_c:<14.4f} | {status}")

with open(ARTIFACTS_DIR / "secondary_cutoff_sweep.json", "w") as f:
    json.dump(sweep_results, f, indent=2)
print("\nSaved sweep results to ml/artifacts/secondary_cutoff_sweep.json")

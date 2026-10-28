"""Compare Seed 42 and Seed 100 on val_natural with their calibrated temperatures."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
probs_42 = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")
probs_100 = np.load(ARTIFACTS_DIR / "legal_bert_seed_100" / "val_natural_probs.npy")

with open(ARTIFACTS_DIR / "label_map.json") as f:
    label_data = json.load(f)
label2id = label_data["label2id"]
id2label = {int(k): v for k, v in label_data["id2label"].items()}

no_clause_idx = label2id["No Clause"]
sub_indices = [i for i in range(11) if i != no_clause_idx]
sub_names = [id2label[i] for i in sub_indices]

y_true = val_nat["label"].to_numpy()
is_neg = (y_true == "No Clause")
is_pos = (y_true != "No Clause")
total_pos = int(is_pos.sum())
n_contracts = val_nat["contract"].nunique()

def eval_seed(probs):
    p_no_clause = probs[:, no_clause_idx]
    sub_probs = probs[:, sub_indices]
    pred_sub = np.array([sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)])
    
    sorted_negs = np.sort(p_no_clause[is_neg])
    
    results = {}
    for fa_c in [3, 8, 12]:
        target_fa_total = int(round(fa_c * n_contracts))
        thresh = float(sorted_negs[target_fa_total - 1])
        
        flagged = (p_no_clause < thresh)
        actual_fa = int((flagged & is_neg).sum())
        flags_count = int(flagged.sum())
        
        tp_flagged = int((flagged & is_pos).sum())
        tp_correct = int((flagged & is_pos & (pred_sub == y_true)).sum())
        
        results[fa_c] = {
            "thresh": thresh,
            "flags": flags_count,
            "fa": actual_fa,
            "tp_flagged": tp_flagged,
            "tp_correct": tp_correct,
            "rec_flagged": round(tp_flagged / total_pos * 100, 2),
            "rec_correct": round(tp_correct / total_pos * 100, 2),
            "precision": round(tp_flagged / flags_count * 100, 2) if flags_count > 0 else 0.0,
            "flagged_mask": flagged,
            "correct_mask": (flagged & is_pos & (pred_sub == y_true)),
        }
    return results

res_42 = eval_seed(probs_42)
res_100 = eval_seed(probs_100)

print(f"Validation Natural set: {len(val_nat)} units ({total_pos} positives, {is_neg.sum()} negatives across {n_contracts} contracts)")
print(f"Seed 42 fitted T: 0.9270 | Seed 100 fitted T: 1.0583\n")

header = f"{'FA/c':<6} | {'Seed 42 Tau':<12} {'S42 Rec(Fl)':<12} {'S42 Rec(Co)':<12} | {'S100 Tau':<12} {'S100 Rec(Fl)':<13} {'S100 Rec(Co)':<13} | {'Delta Fl (S100-S42)':<20} {'Delta Co (S100-S42)':<20}"
print(header)
print("-" * len(header))

for fa_c in [3, 8, 12]:
    r42 = res_42[fa_c]
    r100 = res_100[fa_c]
    d_flag = r100["tp_flagged"] - r42["tp_flagged"]
    d_corr = r100["tp_correct"] - r42["tp_correct"]
    line = f"{fa_c:<6} | {r42['thresh']:<12.6f} {r42['rec_flagged']:<11.2f}% {r42['rec_correct']:<11.2f}% | {r100['thresh']:<12.6f} {r100['rec_flagged']:<12.2f}% {r100['rec_correct']:<12.2f}% | {d_flag:+3d} clauses ({r100['rec_flagged']-r42['rec_flagged']:+0.2f}%)   {d_corr:+3d} clauses ({r100['rec_correct']-r42['rec_correct']:+0.2f}%)"
    print(line)

print("\n" + "=" * 80)
print("CLAUSE-LEVEL OVERLAP & DISAGREEMENT (TRUE POSITIVES ONLY):")
print("=" * 80)
for fa_c in [3, 8, 12]:
    m42 = res_42[fa_c]["flagged_mask"] & is_pos
    m100 = res_100[fa_c]["flagged_mask"] & is_pos
    both = int((m42 & m100).sum())
    only_42 = int((m42 & ~m100).sum())
    only_100 = int((~m42 & m100).sum())
    neither = int((~m42 & ~m100 & is_pos).sum())
    
    c42 = res_42[fa_c]["correct_mask"]
    c100 = res_100[fa_c]["correct_mask"]
    both_c = int((c42 & c100).sum())
    only_42_c = int((c42 & ~c100).sum())
    only_100_c = int((~c42 & c100).sum())
    
    print(f"\n--- At {fa_c} False Alarms / Contract ---")
    print(f"Flagged Recall:")
    print(f"  • Seed 42:  {res_42[fa_c]['tp_flagged']}/{total_pos} ({res_42[fa_c]['rec_flagged']}%)")
    print(f"  • Seed 100: {res_100[fa_c]['tp_flagged']}/{total_pos} ({res_100[fa_c]['rec_flagged']}%)")
    print(f"  • Both flagged: {both} ({both/total_pos*100:.2f}%)")
    print(f"  • Flagged by Seed 42 only: {only_42} ({only_42/total_pos*100:.2f}%)")
    print(f"  • Flagged by Seed 100 only: {only_100} ({only_100/total_pos*100:.2f}%)")
    print(f"  • Missed by both: {neither} ({neither/total_pos*100:.2f}%)")
    print(f"Correct Class Recall:")
    print(f"  • Seed 42:  {res_42[fa_c]['tp_correct']}/{total_pos} ({res_42[fa_c]['rec_correct']}%)")
    print(f"  • Seed 100: {res_100[fa_c]['tp_correct']}/{total_pos} ({res_100[fa_c]['rec_correct']}%)")
    print(f"  • Both correct: {both_c} ({both_c/total_pos*100:.2f}%)")
    print(f"  • Correct in Seed 42 only: {only_42_c}")
    print(f"  • Correct in Seed 100 only: {only_100_c}")

# Save results
out_data = {
    "seed_42": {fa_c: {k: v for k, v in res_42[fa_c].items() if not k.endswith("_mask")} for fa_c in [3, 8, 12]},
    "seed_100": {fa_c: {k: v for k, v in res_100[fa_c].items() if not k.endswith("_mask")} for fa_c in [3, 8, 12]},
}
with open(ARTIFACTS_DIR / "seed_comparison_results.json", "w") as f:
    json.dump(out_data, f, indent=2)
print(f"\nSaved comparison to {ARTIFACTS_DIR / 'seed_comparison_results.json'}")

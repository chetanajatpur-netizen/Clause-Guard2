"""Evaluate Seed Average (Seed 42 + Seed 100) on val_natural.csv and run contract-level bootstrap."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

val_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
p42 = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")
p100 = np.load(ARTIFACTS_DIR / "legal_bert_seed_100" / "val_natural_probs.npy")
p_avg = (p42 + p100) / 2.0

with open(ARTIFACTS_DIR / "label_map.json") as f:
    lmap = json.load(f)["label2id"]
id2label = {v: k for k, v in lmap.items()}

no_clause_idx = lmap["No Clause"]
sub_indices = [idx for name, idx in lmap.items() if name != "No Clause"]
sub_names = [id2label[i] for i in sub_indices]

true_labels = val_df["label"].to_numpy()
is_neg = (true_labels == "No Clause")
is_pos = (true_labels != "No Clause")
total_pos = int(is_pos.sum())
contracts = val_df["contract"].to_numpy()
unique_contracts = np.unique(contracts)
n_c = len(unique_contracts)

def eval_model(probs):
    p_nc = probs[:, no_clause_idx]
    pred_sub = np.array([sub_names[idx] for idx in np.argmax(probs[:, sub_indices], axis=-1)])
    sorted_negs = np.sort(p_nc[is_neg])
    
    res = {}
    for fa_c in [3, 8, 12]:
        target_fa = int(round(fa_c * n_c))
        thresh = float(sorted_negs[target_fa - 1])
        fl = (p_nc < thresh)
        fa = int((fl & is_neg).sum())
        tp_fl = int((fl & is_pos).sum())
        tp_co = int((fl & is_pos & (pred_sub == true_labels)).sum())
        prec = (tp_fl / fl.sum() * 100) if fl.sum() > 0 else 0.0
        
        res[fa_c] = {
            "thresh": thresh,
            "flags": int(fl.sum()),
            "fa": fa,
            "tp_fl": tp_fl,
            "tp_co": tp_co,
            "rec_fl": tp_fl / total_pos * 100,
            "rec_co": tp_co / total_pos * 100,
            "prec": prec,
            "fl_mask": fl,
            "co_mask": (fl & is_pos & (pred_sub == true_labels)),
            "p_nc": p_nc,
        }
    return res

res_42 = eval_model(p42)
res_100 = eval_model(p100)
res_avg = eval_model(p_avg)

print("=" * 105)
print("OPERATING POINTS TABLE: SEED 42 vs SEED 100 vs SEED AVERAGE (SEEDS 42 + 100)")
print("=" * 105)
header = f"{'FA/c':<5} | {'Model':<12} | {'Tau':<10} | {'Flags':<6} | {'FA':<5} | {'TP (Fl)':<7} | {'TP (Co)':<7} | {'Rec(Fl)%':<9} | {'Rec(Co)%':<9} | {'Prec%':<6}"
print(header)
print("-" * len(header))

for fa_c in [3, 8, 12]:
    r42 = res_42[fa_c]
    r100 = res_100[fa_c]
    ravg = res_avg[fa_c]
    print(f"{fa_c:<5} | {'Seed 42':<12} | {r42['thresh']:<10.6f} | {r42['flags']:<6} | {r42['fa']:<5} | {r42['tp_fl']:<7} | {r42['tp_co']:<7} | {r42['rec_fl']:<9.2f} | {r42['rec_co']:<9.2f} | {r42['prec']:<6.2f}")
    print(f"{fa_c:<5} | {'Seed 100':<12} | {r100['thresh']:<10.6f} | {r100['flags']:<6} | {r100['fa']:<5} | {r100['tp_fl']:<7} | {r100['tp_co']:<7} | {r100['rec_fl']:<9.2f} | {r100['rec_co']:<9.2f} | {r100['prec']:<6.2f}")
    print(f"{fa_c:<5} | {'Seed Avg':<12} | {ravg['thresh']:<10.6f} | {ravg['flags']:<6} | {ravg['fa']:<5} | {ravg['tp_fl']:<7} | {ravg['tp_co']:<7} | {ravg['rec_fl']:<9.2f} | {ravg['rec_co']:<9.2f} | {ravg['prec']:<6.2f}")
    d_fl = ravg['tp_fl'] - r42['tp_fl']
    d_co = ravg['tp_co'] - r42['tp_co']
    print(f"      Delta (Avg - S42): {'':<10} | {'':<6} | {'':<5} | {d_fl:+7d} | {d_co:+7d} | {ravg['rec_fl']-r42['rec_fl']:+9.2f} | {ravg['rec_co']-r42['rec_co']:+9.2f} | {ravg['prec']-r42['prec']:+6.2f}")
    print("-" * len(header))

# Contract-level bootstrap (1,000 resamples)
rng = np.random.default_rng(42)
n_boot = 1000
contract_indices = {c: np.where(contracts == c)[0] for c in unique_contracts}

print("\n" + "=" * 105)
print("CONTRACT-LEVEL BOOTSTRAP (1,000 RESAMPLES): SEED AVG vs SEED 42")
print("=" * 105)

bootstrap_results = {}
for fa_c in [3, 8, 12]:
    m42_fl = res_42[fa_c]["fl_mask"]
    mavg_fl = res_avg[fa_c]["fl_mask"]
    m42_co = res_42[fa_c]["co_mask"]
    mavg_co = res_avg[fa_c]["co_mask"]
    
    diff_fl = []
    diff_co = []
    
    for b in range(n_boot):
        sample_c = rng.choice(unique_contracts, size=n_c, replace=True)
        idx = np.concatenate([contract_indices[c] for c in sample_c])
        pos_idx = idx[is_pos[idx]]
        
        r42_f = m42_fl[pos_idx].sum() / len(pos_idx) if len(pos_idx) > 0 else 0
        ravg_f = mavg_fl[pos_idx].sum() / len(pos_idx) if len(pos_idx) > 0 else 0
        diff_fl.append((ravg_f - r42_f) * 100)
        
        r42_c = m42_co[pos_idx].sum() / len(pos_idx) if len(pos_idx) > 0 else 0
        ravg_c = mavg_co[pos_idx].sum() / len(pos_idx) if len(pos_idx) > 0 else 0
        diff_co.append((ravg_c - r42_c) * 100)
        
    diff_fl = np.array(diff_fl)
    diff_co = np.array(diff_co)
    ci_fl = np.percentile(diff_fl, [2.5, 97.5])
    ci_co = np.percentile(diff_co, [2.5, 97.5])
    
    bootstrap_results[fa_c] = {
        "diff_flagged_mean": float(diff_fl.mean()),
        "diff_flagged_ci": [float(ci_fl[0]), float(ci_fl[1])],
        "diff_correct_mean": float(diff_co.mean()),
        "diff_correct_ci": [float(ci_co[0]), float(ci_co[1])],
    }
    
    print(f"--- At {fa_c} False Alarms / Contract ---")
    print(f"  Delta Recall (Flagged):       mean = {diff_fl.mean():+0.2f}% | 95% CI: [{ci_fl[0]:+0.2f}%, {ci_fl[1]:+0.2f}%]")
    print(f"  Delta Recall (Correct Class): mean = {diff_co.mean():+0.2f}% | 95% CI: [{ci_co[0]:+0.2f}%, {ci_co[1]:+0.2f}%]")

with open(ARTIFACTS_DIR / "seed_average_results.json", "w") as f:
    json.dump({
        "operating_points": {
            "seed_42": {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in res_42.items()},
            "seed_100": {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in res_100.items()},
            "seed_avg": {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in res_avg.items()},
        },
        "bootstrap": bootstrap_results,
    }, f, indent=2)
print("\nSaved artifacts to ml/artifacts/seed_average_results.json")

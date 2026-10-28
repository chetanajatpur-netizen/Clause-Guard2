import json
from collections import defaultdict
import numpy as np
import pandas as pd
from ml.src.resegment_and_audit import CUAD_TO_CLAUSE_TYPE, extract_category_from_question

with open("ml/data/raw/CUAD_v1/CUAD_v1.json") as f:
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

train_df = pd.read_csv("ml/data/processed/train.csv")
train_pos = train_df[train_df["label"] != "No Clause"].copy()

by_class_cov = defaultdict(list)
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
    by_class_cov[lbl].append(best_u_cov)

print("=== POSITIVE UNITS UNIT COVERAGE IN TRAIN (SHARE OF UNIT INSIDE SPAN) ===")
print(f"{'Class':<28} {'N':<6} {'<10%':<12} {'10-25%':<12} {'25-50%':<12} {'50%+':<12} {'Mean':<8} {'Median'}")
print("-" * 105)

for cat in sorted(by_class_cov.keys()):
    covs = np.array(by_class_cov[cat])
    n = len(covs)
    b_under10 = int((covs < 0.10).sum())
    b_10_25 = int(((covs >= 0.10) & (covs < 0.25)).sum())
    b_25_50 = int(((covs >= 0.25) & (covs < 0.50)).sum())
    b_50plus = int((covs >= 0.50).sum())
    
    p_u10 = b_under10 / n * 100
    p_1025 = b_10_25 / n * 100
    p_2550 = b_25_50 / n * 100
    p_50p = b_50plus / n * 100
    
    mean_val = covs.mean() * 100
    med_val = np.median(covs) * 100
    
    u10_str = f"{b_under10} ({p_u10:.1f}%)"
    u25_str = f"{b_10_25} ({p_1025:.1f}%)"
    u50_str = f"{b_25_50} ({p_2550:.1f}%)"
    p50_str = f"{b_50plus} ({p_50p:.1f}%)"
    
    print(f"{cat:<28} {n:<6d} {u10_str:<12} {u25_str:<12} {u50_str:<12} {p50_str:<12} {mean_val:5.1f}%   {med_val:5.1f}%")

all_covs = np.concatenate(list(by_class_cov.values()))
total_n = len(all_covs)
print("-" * 105)
tot_u10 = f"{(all_covs<0.10).sum()} ({(all_covs<0.10).sum()/total_n*100:.1f}%)"
tot_1025 = f"{((all_covs>=0.10)&(all_covs<0.25)).sum()} ({((all_covs>=0.10)&(all_covs<0.25)).sum()/total_n*100:.1f}%)"
tot_2550 = f"{((all_covs>=0.25)&(all_covs<0.50)).sum()} ({((all_covs>=0.25)&(all_covs<0.50)).sum()/total_n*100:.1f}%)"
tot_50p = f"{(all_covs>=0.50).sum()} ({(all_covs>=0.50).sum()/total_n*100:.1f}%)"
tot_mean = all_covs.mean() * 100
tot_med = np.median(all_covs) * 100
print(f"{'OVERALL TOTAL':<28} {total_n:<6d} {tot_u10:<12} {tot_1025:<12} {tot_2550:<12} {tot_50p:<12} {tot_mean:5.1f}%   {tot_med:5.1f}%")

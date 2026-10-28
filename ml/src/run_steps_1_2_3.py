"""Analyze Step 1 (contract overlap), Step 2 (risk-tier confusion matrix), and Step 3 (liquidated damages audit and rule)."""
import json
import re
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
PROCESSED_OLD_DIR = PROJECT_ROOT / "ml" / "data" / "processed_old"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
RAW_CUAD_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"

from ml.src.risk_map import RISK_MAP


def run_step1_overlap_check():
    print("=" * 80)
    print("STEP 1: CONTRACT-OVERLAP AUDIT ACROSS DATA GENERATIONS")
    print("=" * 80)

    # 1. Re-generate Generation 1 split contracts
    with open(RAW_CUAD_PATH) as f:
        cuad_data = json.load(f)["data"]

    import random
    SEED = 42

    CUAD_TO_CLAUSE_TYPE = {
        "Non-Compete": "Non-Compete",
        "Exclusivity": "Exclusivity",
        "Termination For Convenience": "Termination for Convenience",
        "Anti-Assignment": "Anti-Assignment",
        "Uncapped Liability": "Uncapped Liability",
        "Cap On Liability": "Cap on Liability",
        "Liquidated Damages": "Liquidated Damages",
        "Audit Rights": "Audit Rights",
        "Change Of Control": "Change of Control",
        "Ip Ownership Assignment": "IP Ownership Assignment",
    }

    def extract_cat(q):
        m = re.search(r"\"([^\"]+)\"", q)
        return m.group(1) if m else None

    def segment_contract_with_spans(text, min_len=50, max_len=2000):
        paragraphs = re.split(r"\n\s*\n", text)
        chunks = []
        current_offset = 0
        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                current_offset += len(para) + 2
                continue
            start_idx = text.find(para_clean, current_offset)
            if start_idx == -1:
                start_idx = current_offset
            end_idx = start_idx + len(para_clean)
            current_offset = end_idx
            if len(para_clean) < min_len:
                continue
            if len(para_clean) > max_len:
                sentences = re.split(r"(?<=[.!?])\s+", para_clean)
                sub_chunk = ""
                sub_start = start_idx
                for sent in sentences:
                    if len(sub_chunk) + len(sent) > max_len and sub_chunk:
                        chunks.append((sub_chunk.strip(), sub_start, sub_start + len(sub_chunk.strip())))
                        sub_start = sub_start + len(sub_chunk)
                        sub_chunk = sent + " "
                    else:
                        sub_chunk += sent + " "
                if sub_chunk.strip():
                    chunks.append((sub_chunk.strip(), sub_start, sub_start + len(sub_chunk.strip())))
            else:
                chunks.append((para_clean, start_idx, end_idx))
        return chunks

    records_g1 = []
    for doc in cuad_data:
        title = doc.get("title", "Unknown")
        for para in doc["paragraphs"]:
            context = para["context"]
            spans_by_type = defaultdict(list)
            for qa in para["qas"]:
                cat = extract_cat(qa["question"])
                if cat and cat in CUAD_TO_CLAUSE_TYPE:
                    ct = CUAD_TO_CLAUSE_TYPE[cat]
                    for ans in qa.get("answers", []):
                        s_a = ans["answer_start"]
                        e_a = s_a + len(ans["text"])
                        if e_a > s_a:
                            spans_by_type[ct].append((s_a, e_a))
            chunks = segment_contract_with_spans(context)
            for chunk_text, c_start, c_end in chunks:
                best_label = "No Clause"
                best_overlap = 0
                for ct, s_list in spans_by_type.items():
                    for s_start, s_end in s_list:
                        overlap = min(c_end, s_end) - max(c_start, s_start)
                        if overlap > 15 and overlap > best_overlap:
                            best_overlap = overlap
                            best_label = ct
                records_g1.append({"contract_id": title, "text": chunk_text, "label": best_label})

    df_g1 = pd.DataFrame(records_g1)
    label_counts = df_g1["label"].value_counts()
    other_counts = label_counts.drop("No Clause", errors="ignore")
    avg_other = int(other_counts.mean())
    max_no_clause = int(avg_other * 3.0)
    no_clause_df = df_g1[df_g1["label"] == "No Clause"]
    other_df = df_g1[df_g1["label"] != "No Clause"]
    no_clause_sampled = no_clause_df.sample(n=max_no_clause, random_state=SEED)
    df_down = pd.concat([other_df, no_clause_sampled], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)

    contracts_g1 = sorted(df_down["contract_id"].unique().tolist())
    rng = random.Random(SEED)
    rng.shuffle(contracts_g1)
    n1 = len(contracts_g1)
    n_tr1 = int(n1 * 0.70)
    n_val1 = int(n1 * 0.15)
    train_g1 = set(contracts_g1[:n_tr1])
    val_g1 = set(contracts_g1[n_tr1 : n_tr1 + n_val1])
    test_g1 = set(contracts_g1[n_tr1 + n_val1 :])

    # Generation 2 (processed_old)
    train_g2 = set(pd.read_csv(PROCESSED_OLD_DIR / "train_natural.csv")["contract"].unique())
    val_g2 = set(pd.read_csv(PROCESSED_OLD_DIR / "val_natural.csv")["contract"].unique())
    test_g2 = set(pd.read_csv(PROCESSED_OLD_DIR / "test_natural.csv")["contract"].unique())

    # Generation 3 (processed)
    train_g3 = set(pd.read_csv(PROCESSED_DIR / "train_natural.csv")["contract"].unique())
    val_g3 = set(pd.read_csv(PROCESSED_DIR / "val_natural.csv")["contract"].unique())
    test_g3 = set(pd.read_csv(PROCESSED_DIR / "test_natural.csv")["contract"].unique())

    print(f"Generation 1 (Original Data Prep): {n1} contracts")
    print(f"  Train: {len(train_g1)} | Val: {len(val_g1)} | Test: {len(test_g1)}")
    print(f"Generation 2 (processed_old): {len(train_g2) + len(val_g2) + len(test_g2)} contracts")
    print(f"  Train: {len(train_g2)} | Val: {len(val_g2)} | Test: {len(test_g2)}")
    print(f"Generation 3 (Current Regenerated): {len(train_g3) + len(val_g3) + len(test_g3)} contracts")
    print(f"  Train: {len(train_g3)} | Val: {len(val_g3)} | Test: {len(test_g3)}")

    # Check overlaps between Gen 1 Train (training set of deployed models) and Gen 3 Val & Test
    overlap_val = sorted(list(train_g1 & val_g3))
    overlap_test = sorted(list(train_g1 & test_g3))

    pct_val_leaked = len(overlap_val) / len(val_g3) * 100
    pct_test_leaked = len(overlap_test) / len(test_g3) * 100

    print(f"\nCRITICAL LEAKAGE FINDING:")
    print(f"1. Deployed Baseline & Deployed Legal-BERT were trained on Generation 1 Train ({len(train_g1)} contracts).")
    print(f"2. Overlap with Generation 3 Val ({len(val_g3)} contracts): {len(overlap_val)} contracts ({pct_val_leaked:.1f}%)")
    print(f"3. Overlap with Generation 3 Test ({len(test_g3)} contracts): {len(overlap_test)} contracts ({pct_test_leaked:.1f}%)")
    print(f"--> CONCLUSION: The deployed baseline and deployed Legal-BERT evaluated on Generation 3 val_natural")
    print(f"    suffer from severe data leakage ({len(overlap_val)} of 76 validation contracts were in their training set).")
    print(f"    STATUS: DEPLOYED BASELINE EVALUATION IS MARKED INVALID.")

    return {
        "gen1": {"train": sorted(list(train_g1)), "val": sorted(list(val_g1)), "test": sorted(list(test_g1))},
        "gen2": {"train": sorted(list(train_g2)), "val": sorted(list(val_g2)), "test": sorted(list(test_g2))},
        "gen3": {"train": sorted(list(train_g3)), "val": sorted(list(val_g3)), "test": sorted(list(test_g3))},
        "leaked_val_contracts": overlap_val,
        "leaked_test_contracts": overlap_test,
    }


def run_step2_risk_tier_metrics():
    print("\n" + "=" * 80)
    print("STEP 2: RISK-TIER METRICS FOR LEGAL-BERT AT 8 AND 12 FA/CONTRACT")
    print("=" * 80)

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

    p_nc = probs[:, no_clause_idx]
    sub_probs = probs[:, sub_indices]
    pred_sub_classes = np.array([sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)])

    y_true_label = val_nat["label"].to_numpy()
    is_neg = (y_true_label == "No Clause")
    n_contracts = val_nat["contract"].nunique()

    # Map true label to true risk tier
    def to_tier(lbl):
        if lbl == "No Clause":
            return "None"
        return RISK_MAP.get(lbl, "None")

    y_true_tier = np.array([to_tier(l) for l in y_true_label])

    tiers = ["High", "Medium", "Low", "None"]

    results_step2 = {}

    for target_fa_c in [8, 12]:
        target_fa_total = int(round(target_fa_c * n_contracts))
        sorted_negs = np.sort(p_nc[is_neg])
        thresh = float(sorted_negs[min(target_fa_total - 1, len(sorted_negs) - 1)])

        flagged = (p_nc < thresh)
        pred_tier = np.array([
            RISK_MAP.get(pred_sub_classes[i], "None") if flagged[i] else "None"
            for i in range(len(val_nat))
        ])

        # Build confusion matrix: True Tier (rows) vs Pred Tier (cols)
        cm = pd.DataFrame(0, index=tiers, columns=tiers)
        for t_true in tiers:
            for t_pred in tiers:
                cm.loc[t_true, t_pred] = int(((y_true_tier == t_true) & (pred_tier == t_pred)).sum())

        # Recall of true High units shown as High
        high_total = int((y_true_tier == "High").sum())
        high_shown_as_high = int(((y_true_tier == "High") & (pred_tier == "High")).sum())
        high_shown_flagged = int(((y_true_tier == "High") & (pred_tier != "None")).sum())

        high_as_high_recall = round(high_shown_as_high / high_total * 100, 2)
        high_flagged_recall = round(high_shown_flagged / high_total * 100, 2)

        print(f"\n--- Operating Point: {target_fa_c} False Alarms / Contract (Threshold={thresh:.4f}) ---")
        print(f"Confusion Matrix (True Tier vs Predicted Tier):")
        print(cm.to_string())
        print(f"\nTrue High Units: {high_total}")
        print(f"  True High shown as High:    {high_shown_as_high}/{high_total} ({high_as_high_recall}%)")
        print(f"  True High flagged (any):    {high_shown_flagged}/{high_total} ({high_flagged_recall}%)")
        print(f"  Breakdown of True High predictions:")
        for t_pred in tiers:
            cnt = int(((y_true_tier == "High") & (pred_tier == t_pred)).sum())
            print(f"    Predicted {t_pred:<6s}: {cnt:>3d} ({cnt / high_total * 100:.1f}%)")

        results_step2[target_fa_c] = {
            "threshold": thresh,
            "confusion_matrix": cm.to_dict(),
            "high_total": high_total,
            "high_shown_as_high": high_shown_as_high,
            "high_as_high_recall": high_as_high_recall,
            "high_shown_flagged": high_shown_flagged,
            "high_flagged_recall": high_flagged_recall,
        }

    return results_step2


def run_step3_liquidated_damages():
    print("\n" + "=" * 80)
    print("STEP 3: LIQUIDATED DAMAGES VALIDATION UNITS AUDIT & RULE EVALUATION")
    print("=" * 80)

    val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
    probs = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")

    with open(ARTIFACTS_DIR / "label_map.json") as f:
        label_data = json.load(f)
    label2id = label_data["label2id"]
    id2label = {int(k): v for k, v in label_data["id2label"].items()}

    no_clause_idx = label2id["No Clause"]
    sub_indices = [i for i in range(11) if i != no_clause_idx]
    sub_names = [id2label[i] for i in sub_indices]

    p_nc = probs[:, no_clause_idx]
    sub_probs = probs[:, sub_indices]
    pred_sub = [sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)]

    # Threshold at 8 FA/c
    n_contracts = val_nat["contract"].nunique()
    is_neg = (val_nat["label"] == "No Clause")
    sorted_negs = np.sort(p_nc[is_neg])
    thresh_8fa = float(sorted_negs[min(int(round(8 * n_contracts)) - 1, len(sorted_negs) - 1)])
    thresh_12fa = float(sorted_negs[min(int(round(12 * n_contracts)) - 1, len(sorted_negs) - 1)])

    # List the 14 validation Liquidated Damages units
    ld_indices = val_nat[val_nat["label"] == "Liquidated Damages"].index.tolist()
    print(f"Total True Liquidated Damages units in val_natural: {len(ld_indices)}")

    rule_pattern = re.compile(r"(?i)\b(?:liquidated\s+damages|pre-estimate\s+of\s+damages)\b")

    ld_units_data = []
    print(f"\n{'Idx':<5} {'Contract (truncated)':<35} {'P(NoCl)':<9} {'Pred(8FA)':<22} {'Pred(12FA)':<22} {'Matches Rule?'} {'Text snippet'}")
    print("-" * 135)

    for i, idx in enumerate(ld_indices):
        row = val_nat.loc[idx]
        txt = str(row["text"])
        c_name = str(row["contract"])[:33]
        p_no = p_nc[idx]
        p_class = pred_sub[idx]

        flag_8 = (p_no < thresh_8fa)
        flag_12 = (p_no < thresh_12fa)

        pred_8_str = f"Flag: {p_class}" if flag_8 else "No Clause (Miss)"
        pred_12_str = f"Flag: {p_class}" if flag_12 else "No Clause (Miss)"

        matches_rule = bool(rule_pattern.search(txt))
        snip = txt.replace("\n", " ")[:45]

        print(f"{i+1:<5} {c_name:<35} {p_no:<9.4f} {pred_8_str:<22} {pred_12_str:<22} {str(matches_rule):<13} {snip}...")

        ld_units_data.append({
            "idx": idx,
            "contract": row["contract"],
            "p_no_clause": float(p_no),
            "pred_sub_class": p_class,
            "flagged_8fa": bool(flag_8),
            "flagged_12fa": bool(flag_12),
            "matches_rule": matches_rule,
            "text": txt,
        })

    # Rule evaluation on all 10,861 val_natural units
    matches_all = val_nat["text"].astype(str).str.contains(rule_pattern, regex=True).to_numpy()
    total_rule_matches = int(matches_all.sum())

    # How many of these are true negatives?
    rule_true_pos = int((matches_all & (val_nat["label"] != "No Clause")).sum())
    rule_true_ld = int((matches_all & (val_nat["label"] == "Liquidated Damages")).sum())
    rule_false_alarms = int((matches_all & is_neg).sum())

    extra_fa_c = round(rule_false_alarms / n_contracts, 3)

    # Combined with Legal-BERT at 8 FA/c
    flagged_8fa = (p_nc < thresh_8fa)
    combined_flagged_8fa = flagged_8fa | matches_all

    fa_base_8 = int((flagged_8fa & is_neg).sum())
    fa_comb_8 = int((combined_flagged_8fa & is_neg).sum())
    new_fa_8 = fa_comb_8 - fa_base_8
    new_fa_c_8 = round(new_fa_8 / n_contracts, 3)

    ld_flagged_base = int((flagged_8fa & (val_nat["label"] == "Liquidated Damages")).sum())
    ld_flagged_comb = int((combined_flagged_8fa & (val_nat["label"] == "Liquidated Damages")).sum())
    ld_gain = ld_flagged_comb - ld_flagged_base
    ld_rec_base = ld_flagged_base / 14 * 100
    ld_rec_comb = ld_flagged_comb / 14 * 100

    print(f"\n================================================================================")
    print("RULE MEASUREMENT ON VAL_NATURAL (10,861 units across 76 contracts)")
    print("Rule: Text contains 'liquidated damages' or 'pre-estimate of damages'")
    print("================================================================================")
    print(f"Total units matching rule in val_natural: {total_rule_matches}")
    print(f"  Matches on True Liquidated Damages:     {rule_true_ld} / 14")
    print(f"  Matches on other positive clauses:      {rule_true_pos - rule_true_ld}")
    print(f"  Matches on harmless units (No Clause):  {rule_false_alarms}")
    print(f"  Standalone False Alarms per contract:   {extra_fa_c:.3f} FA/contract ({rule_false_alarms} FAs)")
    print(f"\nImpact when applied on top of Legal-BERT at 8 FA/c:")
    print(f"  Liquidated Damages recall:              {ld_rec_base:.1f}% ({ld_flagged_base}/14) -> {ld_rec_comb:.1f}% ({ld_flagged_comb}/14) [Gain: +{ld_gain} clauses, +{ld_rec_comb - ld_rec_base:.1f}%]")
    print(f"  False Alarms:                           {fa_base_8} -> {fa_comb_8} [+{new_fa_8} FAs, +{new_fa_c_8:.3f} FA/contract]")

    return {
        "ld_14_units": ld_units_data,
        "rule_matches_total": total_rule_matches,
        "rule_true_ld": rule_true_ld,
        "rule_false_alarms": rule_false_alarms,
        "extra_fa_per_contract_standalone": extra_fa_c,
        "new_fa_at_8fa": new_fa_8,
        "new_fa_per_contract_at_8fa": new_fa_c_8,
        "ld_recall_base_8fa": round(ld_rec_base, 2),
        "ld_recall_comb_8fa": round(ld_rec_comb, 2),
        "ld_recall_gain_pct": round(ld_rec_comb - ld_rec_base, 2),
    }


def main():
    step1_res = run_step1_overlap_check()
    step2_res = run_step2_risk_tier_metrics()
    step3_res = run_step3_liquidated_damages()

    out_file = ARTIFACTS_DIR / "steps_1_2_3_audit_results.json"
    with open(out_file, "w") as f:
        json.dump({
            "step1": step1_res,
            "step2": step2_res,
            "step3": step3_res,
        }, f, indent=2)
    print(f"\nSaved Steps 1, 2, 3 results to {out_file}")


if __name__ == "__main__":
    main()

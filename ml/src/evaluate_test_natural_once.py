"""CHECKPOINT A: One-time evaluation of test_natural with seed-42 model at the 3 frozen thresholds."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "legal_bert_final"

from ml.src.risk_map import RISK_MAP


class SimpleTextDataset(Dataset):
    def __init__(self, encodings):
        self.input_ids = encodings["input_ids"]
        self.attention_mask = encodings["attention_mask"]

    def __len__(self):
        return len(self.input_ids)

    def __getitem__(self, idx):
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
        }


def main():
    print("=" * 80)
    print("CHECKPOINT A: ONE-TIME EVALUATION ON TEST_NATURAL (SEED-42 MODEL, T=0.9270)")
    print("=" * 80)

    device = torch.device("cpu")
    print(f"Device for inference: {device}")

    # Load frozen operating points presets
    with open(ARTIFACTS_DIR / "operating_points.json") as f:
        op_data = json.load(f)
    presets = op_data["presets"]
    T = op_data["temperature"]  # 0.9270

    print(f"Loaded frozen temperature: T={T:.4f}")
    print("Frozen Presets:")
    for k, v in presets.items():
        print(f"  {k:<10}: target={v['target_fa_per_contract']} FA/c, tau={v['tau']}")

    # Load label map
    with open(ARTIFACTS_DIR / "label_map.json") as f:
        label_data = json.load(f)
    label2id = label_data["label2id"]
    id2label = {int(k): v for k, v in label_data["id2label"].items()}
    class_names = [id2label[i] for i in range(11)]

    no_clause_idx = label2id["No Clause"]
    sub_indices = [i for i in range(11) if i != no_clause_idx]
    sub_names = [id2label[i] for i in sub_indices]

    # Load test_natural
    test_nat = pd.read_csv(PROCESSED_DIR / "test_natural.csv")
    n_contracts = test_nat["contract"].nunique()  # 77 contracts
    total_units = len(test_nat)  # 10,480 units
    y_true_label = test_nat["label"].to_numpy()
    is_pos = (y_true_label != "No Clause")
    is_neg = (y_true_label == "No Clause")
    total_positives = int(is_pos.sum())

    print(f"\nLoaded test_natural: {total_units} units across {n_contracts} contracts.")
    print(f"Total True Positives in test_natural: {total_positives}")
    print("Test positive label breakdown:")
    print(test_nat[is_pos]["label"].value_counts().to_string())

    # Map to risk tiers
    def to_tier(l):
        if l == "No Clause":
            return "None"
        return RISK_MAP.get(l, "None")

    y_true_tier = np.array([to_tier(l) for l in y_true_label])

    # Inference with frozen seed-42 model
    print(f"\nLoading model from {MODEL_DIR}...")
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, num_labels=11).to(device)
    model.eval()

    print(f"Tokenizing {total_units} test units...")
    encodings = tokenizer(
        test_nat["text"].tolist(),
        max_length=256,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    test_ds = SimpleTextDataset(encodings)
    loader = DataLoader(test_ds, batch_size=64, shuffle=False)

    print("Running inference...")
    all_logits = []
    with torch.no_grad():
        for batch in loader:
            b_in = batch["input_ids"].to(device)
            b_attn = batch["attention_mask"].to(device)
            out = model(input_ids=b_in, attention_mask=b_attn)
            all_logits.append(out.logits.cpu().numpy())

    raw_logits = np.vstack(all_logits)
    scaled_logits = raw_logits / T
    probs = np.exp(scaled_logits - np.max(scaled_logits, axis=-1, keepdims=True))
    probs = probs / np.sum(probs, axis=-1, keepdims=True)

    # Save test predictions
    np.save(ARTIFACTS_DIR / "test_natural_probs.npy", probs)

    p_no_clause = probs[:, no_clause_idx]
    sub_probs = probs[:, sub_indices]
    pred_sub = np.array([sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)])

    results_test = {}

    print("\n" + "=" * 120)
    print("CHECKPOINT A: TEST_NATURAL EVALUATION RESULTS AT FROZEN THRESHOLDS")
    print("=" * 120)

    for preset_name, p_info in presets.items():
        tau = p_info["tau"]
        target_fa_c = p_info["target_fa_per_contract"]

        flagged = (p_no_clause < tau)
        fa_count = int((flagged & is_neg).sum())
        fa_per_contract = round(fa_count / n_contracts, 2)
        flags_count = int(flagged.sum())

        tp_flagged = int((flagged & is_pos).sum())
        tp_correct = int((flagged & is_pos & (pred_sub == y_true_label)).sum())

        rec_flagged = round(tp_flagged / total_positives * 100, 2)
        rec_correct = round(tp_correct / total_positives * 100, 2)
        precision = round(tp_flagged / flags_count * 100, 2) if flags_count > 0 else 0.0

        # By risk tier
        rec_by_tier = {}
        for tier in ["High", "Medium", "Low"]:
            t_mask = (y_true_tier == tier)
            n_tier = int(t_mask.sum())
            if n_tier > 0:
                t_fl = int((flagged & t_mask).sum())
                t_co = int((flagged & t_mask & (pred_sub == y_true_label)).sum())
                rec_by_tier[tier] = {
                    "total": n_tier,
                    "flagged": t_fl,
                    "correct": t_co,
                    "recall_flagged": round(t_fl / n_tier * 100, 2),
                    "recall_correct": round(t_co / n_tier * 100, 2),
                }

        # By class
        rec_by_class = {}
        for c_name in sub_names:
            c_mask = (y_true_label == c_name)
            n_c = int(c_mask.sum())
            if n_c > 0:
                c_fl = int((flagged & c_mask).sum())
                c_co = int((flagged & c_mask & (pred_sub == c_name)).sum())
                rec_by_class[c_name] = {
                    "total": n_c,
                    "flagged": c_fl,
                    "correct": c_co,
                    "recall_flagged": round(c_fl / n_c * 100, 2),
                    "recall_correct": round(c_co / n_c * 100, 2),
                }

        print(f"\n--- Preset '{preset_name}' (Target {target_fa_c} FA/c, tau={tau:.6f}) ---")
        print(f"  Flags:                    {flags_count}")
        print(f"  False Alarms:             {fa_count} ({fa_per_contract:.2f} FA/contract across {n_contracts} test contracts)")
        print(f"  Precision:                {precision:.2f}%")
        print(f"  Recall (Flagged, Any):    {tp_flagged}/{total_positives} ({rec_flagged:.2f}%)")
        print(f"  Recall (Correct Class):   {tp_correct}/{total_positives} ({rec_correct:.2f}%)")
        print(f"\n  Recall by Risk Tier:")
        for tier, t_val in rec_by_tier.items():
            print(f"    {tier:<8}: Flagged={t_val['recall_flagged']:.1f}% ({t_val['flagged']}/{t_val['total']}) | Correct={t_val['recall_correct']:.1f}% ({t_val['correct']}/{t_val['total']})")
        print(f"\n  Recall by Clause Category:")
        for c_name, c_val in rec_by_class.items():
            print(f"    {c_name:<30}: Flagged={c_val['recall_flagged']:.1f}% ({c_val['flagged']}/{c_val['total']}) | Correct={c_val['recall_correct']:.1f}% ({c_val['correct']}/{c_val['total']})")

        results_test[preset_name] = {
            "preset": preset_name,
            "target_fa_per_contract": target_fa_c,
            "tau": tau,
            "flags_count": flags_count,
            "fa_count": fa_count,
            "fa_per_contract": fa_per_contract,
            "precision": precision,
            "tp_flagged": tp_flagged,
            "tp_correct": tp_correct,
            "total_positives": total_positives,
            "recall_flagged": rec_flagged,
            "recall_correct": rec_correct,
            "recall_by_tier": rec_by_tier,
            "recall_by_class": rec_by_class,
        }

    # Save to artifacts
    out_file = ARTIFACTS_DIR / "checkpoint_a_test_evaluation.json"
    with open(out_file, "w") as f:
        json.dump(results_test, f, indent=2)
    print(f"\nSaved Checkpoint A evaluation results to {out_file}")

    # Check 70% condition at 8 FA/c
    balanced_rec = results_test["balanced"]["recall_flagged"]
    print(f"\n>>> CHECKPOINT A STATUS: Recall at 8 FA/contract is {balanced_rec:.2f}% <<<")
    if balanced_rec < 70.0:
        print(f"ALERT: Recall at 8 FA/contract ({balanced_rec:.2f}%) is UNDER 70.0% threshold. Stopping per instruction.")
        sys.exit(1)
    else:
        print(f"SUCCESS: Recall at 8 FA/contract ({balanced_rec:.2f}%) exceeds 70.0% threshold. Proceeding with subsequent steps.")


if __name__ == "__main__":
    from pathlib import Path
    main()

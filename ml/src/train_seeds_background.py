"""Train Legal-BERT with seeds 100 and 2024 in the background on train_model_b_final.csv."""
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.optimize as opt
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"


def get_device() -> torch.device:
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class TensorClauseDataset(Dataset):
    def __init__(self, input_ids: torch.Tensor, attention_mask: torch.Tensor, labels: torch.Tensor, sample_weights: torch.Tensor):
        self.input_ids = input_ids
        self.attention_mask = attention_mask
        self.labels = labels
        self.sample_weights = sample_weights

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "label": self.labels[idx],
            "sample_weight": self.sample_weights[idx],
        }


def fit_temperature_scaling(logits: np.ndarray, y_true: list[int] | np.ndarray) -> float:
    targets = np.array(y_true)

    def nll_obj(t: float) -> float:
        scaled = logits / max(t, 1e-4)
        max_l = np.max(scaled, axis=-1, keepdims=True)
        exp_l = np.exp(scaled - max_l)
        log_softmax = (scaled - max_l) - np.log(np.sum(exp_l, axis=-1, keepdims=True))
        nll = -np.mean(log_softmax[np.arange(len(targets)), targets])
        return float(nll)

    res = opt.minimize_scalar(nll_obj, bounds=(0.05, 5.0), method="bounded")
    return float(res.x)


def compute_operating_points_for_seed(probs: np.ndarray, val_df: pd.DataFrame, label2id: dict[str, int], id2label: dict[int, str]) -> dict[int, dict[str, Any]]:
    n_contracts = val_df["contract"].nunique()
    no_clause_idx = label2id["No Clause"]
    sub_indices = [i for i in range(11) if i != no_clause_idx]
    sub_names = [id2label[i] for i in sub_indices]

    p_no_clause = probs[:, no_clause_idx]
    sub_probs = probs[:, sub_indices]
    pred_sub = np.array([sub_names[idx] for idx in np.argmax(sub_probs, axis=-1)])

    y_true = val_df["label"].to_numpy()
    is_neg = (y_true == "No Clause")
    is_pos = (y_true != "No Clause")
    total_positives = int(is_pos.sum())

    sorted_negs = np.sort(p_no_clause[is_neg])
    table = {}

    for fa_c in [5, 8, 12]:
        target_fa_total = int(round(fa_c * n_contracts))
        thresh = float(sorted_negs[target_fa_total - 1])

        flagged = (p_no_clause < thresh)
        actual_fa = int((flagged & is_neg).sum())
        flags_count = int(flagged.sum())

        tp_flagged = int((flagged & is_pos).sum())
        tp_correct = int((flagged & is_pos & (pred_sub == y_true)).sum())

        table[fa_c] = {
            "target_fa_per_contract": fa_c,
            "threshold": round(thresh, 6),
            "actual_fa_per_contract": round(actual_fa / n_contracts, 2),
            "flags_count": flags_count,
            "fa_count": actual_fa,
            "tp_flagged": tp_flagged,
            "tp_correct": tp_correct,
            "recall_flagged": round(tp_flagged / total_positives * 100, 2),
            "recall_correct": round(tp_correct / total_positives * 100, 2),
            "precision": round(tp_flagged / flags_count * 100, 2) if flags_count > 0 else 0.0,
        }
    return table


def train_single_seed(
    seed: int,
    train_dataset: TensorClauseDataset,
    val_dataset: TensorClauseDataset,
    val_nat_dataset: TensorClauseDataset,
    val_nat_df: pd.DataFrame,
    class_weights: torch.Tensor,
    device: torch.device,
    label2id: dict[str, int],
    id2label: dict[int, str],
) -> dict[str, Any]:
    print("\n" + "=" * 70)
    print(f"STARTING TRAINING FOR SEED {seed}")
    print("=" * 70)

    # Set seed
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    t_start = time.time()
    save_dir = ARTIFACTS_DIR / f"legal_bert_seed_{seed}"
    save_dir.mkdir(parents=True, exist_ok=True)

    model = AutoModelForSequenceClassification.from_pretrained("nlpaueb/legal-bert-base-uncased", num_labels=11).to(device)
    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False)

    criterion = nn.CrossEntropyLoss(weight=class_weights, reduction="none")
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)

    epochs = 3
    grad_accum = 4
    total_update_steps = (len(train_loader) // grad_accum) * epochs
    warmup_steps = int(total_update_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_update_steps)

    best_val_f1 = -1.0
    val_y_true = val_dataset.labels.numpy()

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        optimizer.zero_grad()
        t_ep = time.time()

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            weights = batch["sample_weight"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            per_sample_loss = criterion(outputs.logits, labels)
            loss = (per_sample_loss * weights).sum() / (weights.sum() + 1e-8)

            loss_to_back = loss / grad_accum
            loss_to_back.backward()
            running_loss += loss.item()

            if (step + 1) % grad_accum == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        if device.type == "mps":
            torch.mps.empty_cache()

        # Validation evaluation
        model.eval()
        val_logits_list = []
        with torch.no_grad():
            for v_batch in val_loader:
                v_in = v_batch["input_ids"].to(device)
                v_attn = v_batch["attention_mask"].to(device)
                out = model(input_ids=v_in, attention_mask=v_attn)
                val_logits_list.append(out.logits.cpu().numpy())

        val_logits = np.vstack(val_logits_list)
        val_preds = np.argmax(val_logits, axis=-1)
        val_f1 = f1_score(val_y_true, val_preds, average="macro", zero_division=0)
        dt_ep = time.time() - t_ep
        print(f"Seed {seed} Epoch {epoch + 1}/{epochs} finished in {dt_ep:.1f}s | Val Macro-F1: {val_f1 * 100:.2f}%")

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            model.save_pretrained(save_dir)

    wall_clock_time = time.time() - t_start
    print(f"Seed {seed} training complete in {wall_clock_time:.1f}s ({wall_clock_time / 60:.2f} minutes).")

    # Reload best model & calibrate
    best_model = AutoModelForSequenceClassification.from_pretrained(save_dir, num_labels=11).to(device)
    best_model.eval()

    # Val logits
    val_logits_best = []
    with torch.no_grad():
        for v_batch in val_loader:
            v_in = v_batch["input_ids"].to(device)
            v_attn = v_batch["attention_mask"].to(device)
            out = best_model(input_ids=v_in, attention_mask=v_attn)
            val_logits_best.append(out.logits.cpu().numpy())
    optimal_t = fit_temperature_scaling(np.vstack(val_logits_best), val_y_true)
    print(f"Seed {seed} fitted temperature T: {optimal_t:.4f}")

    # Inference on val_natural
    print(f"Running Seed {seed} inference on val_natural...")
    nat_loader = DataLoader(val_nat_dataset, batch_size=32, shuffle=False)
    nat_logits_list = []
    with torch.no_grad():
        for batch in nat_loader:
            b_in = batch["input_ids"].to(device)
            b_attn = batch["attention_mask"].to(device)
            out = best_model(input_ids=b_in, attention_mask=b_attn)
            nat_logits_list.append(out.logits.cpu().numpy())

    nat_logits = np.vstack(nat_logits_list)
    scaled_logits = nat_logits / optimal_t
    probs = np.exp(scaled_logits - np.max(scaled_logits, axis=-1, keepdims=True))
    probs = probs / np.sum(probs, axis=-1, keepdims=True)

    np.save(save_dir / "val_natural_probs.npy", probs)
    op_table = compute_operating_points_for_seed(probs, val_nat_df, label2id, id2label)

    return {
        "seed": seed,
        "wall_clock_seconds": round(wall_clock_time, 2),
        "wall_clock_minutes": round(wall_clock_time / 60, 2),
        "best_val_macro_f1": round(float(best_val_f1) * 100, 2),
        "temperature": round(float(optimal_t), 4),
        "operating_points": op_table,
    }


def main():
    device = get_device()
    print(f"Background Training Device: {device}")

    # Load label map
    with open(ARTIFACTS_DIR / "label_map.json") as f:
        label_data = json.load(f)
    label2id = label_data["label2id"]
    id2label = {int(k): v for k, v in label_data["id2label"].items()}

    # Load datasets
    train_df = pd.read_csv(PROCESSED_DIR / "train_model_b_final.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    val_nat_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")

    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")

    # Pretokenize
    def prep(df):
        texts = df["text"].tolist()
        labels = [label2id[l] for l in df["label"]]
        weights = df["sample_weight"].tolist() if "sample_weight" in df.columns else [1.0] * len(df)
        enc = tokenizer(texts, max_length=256, padding="max_length", truncation=True, return_tensors="pt")
        return TensorClauseDataset(enc["input_ids"], enc["attention_mask"], torch.tensor(labels, dtype=torch.long), torch.tensor(weights, dtype=torch.float32))

    train_ds = prep(train_df)
    val_ds = prep(val_df)
    val_nat_ds = prep(val_nat_df)

    counts = train_df["label"].value_counts()
    total = len(train_df)
    w = torch.zeros(11, dtype=torch.float32)
    for l, idx in label2id.items():
        w[idx] = total / (11 * counts.get(l, 1))
    class_weights = (w / w.sum() * 11).to(device)

    results = {}
    seeds_to_run = [100, 2024]

    for seed in seeds_to_run:
        res = train_single_seed(seed, train_ds, val_ds, val_nat_ds, val_nat_df, class_weights, device, label2id, id2label)
        results[f"seed_{seed}"] = res

        # Check timeout rule: skip seed 2024 if a run takes over 90 minutes
        if res["wall_clock_minutes"] > 90.0:
            print(f"Seed {seed} took {res['wall_clock_minutes']:.1f} minutes (>90m). Skipping subsequent seed.")
            break

    # Save results
    out_file = ARTIFACTS_DIR / "seeds_100_2024_evaluation.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll seed runs completed. Saved to {out_file}")


if __name__ == "__main__":
    main()

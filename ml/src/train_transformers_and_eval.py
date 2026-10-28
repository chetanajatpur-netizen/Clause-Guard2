"""Train Legal-BERT and Court-Adapted Legal-BERT, tune ensemble alpha on training OOF, and run contract-level bootstrap."""
import json
import math
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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import KFold
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModel,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SEED = 42
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
ADAPTED_BACKBONE_DIR = ARTIFACTS_DIR / "legal_bert_adapted_backbone"

TARGET_CLASSES = [
    "Non-Compete",
    "Exclusivity",
    "Uncapped Liability",
    "Liquidated Damages",
]


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_device() -> torch.device:
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def compute_class_weights(df: pd.DataFrame, label2id: dict[str, int], device: torch.device) -> torch.Tensor:
    counts = df["label"].value_counts()
    total = len(df)
    num_classes = len(label2id)
    weights = torch.zeros(num_classes, dtype=torch.float32)
    for label, idx in label2id.items():
        count = counts.get(label, 1)
        weights[idx] = total / (num_classes * count)
    weights = weights / weights.sum() * num_classes
    print(f"Computed class weights: {[round(w, 2) for w in weights.tolist()]}", flush=True)
    return weights.to(device)


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


def pretokenize_data(df: pd.DataFrame, tokenizer: Any, label2id: dict[str, int], max_len: int = 256) -> TensorClauseDataset:
    texts = df["text"].tolist()
    labels = [label2id[l] for l in df["label"]]
    weights = df["sample_weight"].tolist() if "sample_weight" in df.columns else [1.0] * len(df)

    print(f"Pre-tokenizing {len(texts)} samples (max_len={max_len})...", flush=True)
    encodings = tokenizer(
        texts,
        max_length=max_len,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    return TensorClauseDataset(
        input_ids=encodings["input_ids"],
        attention_mask=encodings["attention_mask"],
        labels=torch.tensor(labels, dtype=torch.long),
        sample_weights=torch.tensor(weights, dtype=torch.float32),
    )


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


def compute_operating_points_table(model_name: str, probs: np.ndarray, classes: list[str], val_df: pd.DataFrame, target_fa_list: list[int] = [3, 5, 8, 12, 20]) -> list[dict[str, Any]]:
    n_contracts = val_df["contract"].nunique()
    no_clause_idx = list(classes).index("No Clause")
    substantive_indices = [i for i, c in enumerate(classes) if c != "No Clause"]
    substantive_class_names = [classes[i] for i in substantive_indices]

    p_no_clause = probs[:, no_clause_idx]
    sub_probs = probs[:, substantive_indices]
    pred_sub_indices = np.argmax(sub_probs, axis=-1)
    pred_sub_classes = np.array([substantive_class_names[idx] for idx in pred_sub_indices])

    y_true = val_df["label"].to_numpy()
    is_positive = (y_true != "No Clause")
    is_negative = (y_true == "No Clause")
    total_positives = int(is_positive.sum())

    sorted_neg_scores = np.sort(p_no_clause[is_negative])

    rows = []
    for target_fa_c in target_fa_list:
        target_fa_total = int(round(target_fa_c * n_contracts))
        thresh_idx = min(target_fa_total - 1, len(sorted_neg_scores) - 1)
        thresh = float(sorted_neg_scores[thresh_idx])

        flagged = (p_no_clause < thresh)
        fa_count = int((flagged & is_negative).sum())
        actual_fa_c = round(fa_count / n_contracts, 2)
        flags_count = int(flagged.sum())

        tp_flagged = int((flagged & is_positive).sum())
        tp_correct = int((flagged & is_positive & (pred_sub_classes == y_true)).sum())

        precision = round((tp_flagged / flags_count * 100), 2) if flags_count > 0 else 0.0
        rec_flagged_overall = round((tp_flagged / total_positives * 100), 2)
        rec_correct_overall = round((tp_correct / total_positives * 100), 2)

        row: dict[str, Any] = {
            "model": model_name,
            "target_fa_c": target_fa_c,
            "actual_fa_c": actual_fa_c,
            "threshold": round(thresh, 4),
            "flags": flags_count,
            "fa": fa_count,
            "tp_flagged": tp_flagged,
            "tp_correct": tp_correct,
            "precision": precision,
            "rec_flagged_overall": rec_flagged_overall,
            "rec_correct_overall": rec_correct_overall,
        }

        for cat in TARGET_CLASSES:
            cat_mask = (y_true == cat)
            n_cat = int(cat_mask.sum())
            if n_cat > 0:
                cat_flagged = int((flagged & cat_mask).sum())
                cat_correct = int((flagged & cat_mask & (pred_sub_classes == cat)).sum())
                row[f"{cat}_flagged"] = round((cat_flagged / n_cat * 100), 2)
                row[f"{cat}_correct"] = round((cat_correct / n_cat * 100), 2)
            else:
                row[f"{cat}_flagged"] = 0.0
                row[f"{cat}_correct"] = 0.0

        rows.append(row)
    return rows


def print_table(rows: list[dict[str, Any]], title: str) -> None:
    print("\n" + "=" * 135)
    print(f"OPERATING-POINTS TABLE: {title}")
    print("=" * 135)
    header = (
        f"{'Target':<7} {'Actual':<7} {'Thresh':<8} {'Flags':<6} {'FA':<5} {'Prec':<7} "
        f"{'Rec(Flag)':<10} {'Rec(Corr)':<10} "
        f"{'NC(Fl/Co)':<12} {'Exc(Fl/Co)':<12} {'Uncap(Fl/Co)':<14} {'Liq(Fl/Co)':<12}"
    )
    print(header)
    print("-" * 135)
    for r in rows:
        nc_str = f"{r['Non-Compete_flagged']:.1f}/{r['Non-Compete_correct']:.1f}%"
        exc_str = f"{r['Exclusivity_flagged']:.1f}/{r['Exclusivity_correct']:.1f}%"
        uncap_str = f"{r['Uncapped Liability_flagged']:.1f}/{r['Uncapped Liability_correct']:.1f}%"
        liq_str = f"{r['Liquidated Damages_flagged']:.1f}/{r['Liquidated Damages_correct']:.1f}%"
        line = (
            f"{r['target_fa_c']:<7} {r['actual_fa_c']:<7.2f} {r['threshold']:<8.4f} {r['flags']:<6} {r['fa']:<5} {r['precision']:<7.2f}% "
            f"{r['rec_flagged_overall']:<10.2f}% {r['rec_correct_overall']:<10.2f}% "
            f"{nc_str:<12} {exc_str:<12} {uncap_str:<14} {liq_str:<12}"
        )
        print(line)


def run_inference_batches(model: nn.Module, dataset: TensorClauseDataset, device: torch.device, batch_size: int = 32) -> np.ndarray:
    model.eval()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    all_logits = []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            all_logits.append(outputs.logits.cpu().numpy())
    if device.type == "mps":
        torch.mps.empty_cache()
    return np.vstack(all_logits)


def train_transformer_model(
    model_name_or_path: str,
    save_dir: Path,
    train_dataset: TensorClauseDataset,
    val_dataset: TensorClauseDataset,
    class_weights: torch.Tensor,
    device: torch.device,
    epochs: int = 3,
    micro_batch: int = 4,
    grad_accum: int = 4,
    lr: float = 2e-5,
) -> tuple[nn.Module, float]:
    set_seed(SEED)
    print(f"\nLoading model from {model_name_or_path}...")
    model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path, num_labels=11).to(device)
    
    train_loader = DataLoader(train_dataset, batch_size=micro_batch, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False)
    
    criterion = nn.CrossEntropyLoss(weight=class_weights, reduction="none")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    
    total_update_steps = (len(train_loader) // grad_accum) * epochs
    warmup_steps = int(total_update_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_update_steps)

    print(f"Training on {device}: {len(train_dataset)} samples, {epochs} epochs, micro_batch={micro_batch}, grad_accum={grad_accum}, total_updates={total_update_steps}")

    best_val_f1 = -1.0
    save_dir.mkdir(parents=True, exist_ok=True)
    val_y_true = val_dataset.labels.numpy()

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        optimizer.zero_grad()
        t0 = time.time()

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

            if (step + 1) % 400 == 0:
                print(f"  Epoch {epoch + 1}/{epochs} [Step {step + 1}/{len(train_loader)}] Loss: {running_loss / (step + 1):.4f}", flush=True)

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
        dt = time.time() - t0

        print(f"Epoch {epoch + 1}/{epochs} finished in {dt:.1f}s | Val Macro-F1: {val_f1 * 100:.2f}%", flush=True)

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            model.save_pretrained(save_dir)
            print(f"  --> Saved new best checkpoint to {save_dir} (Val Macro-F1: {val_f1 * 100:.2f}%)")

    # Reload best model
    best_model = AutoModelForSequenceClassification.from_pretrained(save_dir, num_labels=11).to(device)
    
    # Fit temperature scaling on val.csv logits
    val_logits_best = run_inference_batches(best_model, val_dataset, device, batch_size=32)
    optimal_t = fit_temperature_scaling(val_logits_best, val_y_true)
    print(f"Fitted optimal temperature T: {optimal_t:.4f}")

    return best_model, optimal_t


def main():
    print("=" * 80)
    print("STARTING TRANSFORMER TRAINING, ENSEMBLE TUNING & CONTRACT BOOTSTRAP")
    print("=" * 80)

    device = get_device()
    print(f"Compute device: {device}")

    # Load label map
    with open(ARTIFACTS_DIR / "label_map.json") as f:
        label_data = json.load(f)
    label2id = label_data["label2id"]
    id2label = {int(k): v for k, v in label_data["id2label"].items()}
    class_names = [id2label[i] for i in range(11)]

    # Load datasets
    train_model_b_df = pd.read_csv(PROCESSED_DIR / "train_model_b_final.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    val_nat_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")

    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")

    # Pre-tokenize datasets
    train_dataset = pretokenize_data(train_model_b_df, tokenizer, label2id, max_len=256)
    val_dataset = pretokenize_data(val_df, tokenizer, label2id, max_len=256)
    val_nat_dataset = pretokenize_data(val_nat_df, tokenizer, label2id, max_len=256)

    class_weights = compute_class_weights(train_model_b_df, label2id, device)

    # -------------------------------------------------------------------------
    # 1. Fine-Tune Legal-BERT
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FINE-TUNING LEGAL-BERT (nlpaueb/legal-bert-base-uncased)")
    print("=" * 80)
    legal_bert_save_dir = ARTIFACTS_DIR / "legal_bert_final"
    legal_bert_model, t_legal_bert = train_transformer_model(
        "nlpaueb/legal-bert-base-uncased",
        legal_bert_save_dir,
        train_dataset,
        val_dataset,
        class_weights,
        device,
        epochs=3,
        micro_batch=4,
        grad_accum=4,
        lr=2e-5,
    )

    # Inference on val_natural
    print("\nRunning Legal-BERT inference on val_natural (10,861 units)...")
    logits_nat_bert = run_inference_batches(legal_bert_model, val_nat_dataset, device, batch_size=32)
    scaled_logits_bert = logits_nat_bert / t_legal_bert
    probs_legal_bert = np.exp(scaled_logits_bert - np.max(scaled_logits_bert, axis=-1, keepdims=True))
    probs_legal_bert = probs_legal_bert / np.sum(probs_legal_bert, axis=-1, keepdims=True)

    np.save(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy", probs_legal_bert)

    table_legal_bert = compute_operating_points_table("Legal-BERT (Calibrated)", probs_legal_bert, class_names, val_nat_df)
    print_table(table_legal_bert, f"Legal-BERT (Calibrated, T={t_legal_bert:.4f})")

    # -------------------------------------------------------------------------
    # 2. Fine-Tune Court-Judgment-Adapted Backbone
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FINE-TUNING COURT-JUDGMENT-ADAPTED BACKBONE")
    print("=" * 80)
    adapted_save_dir = ARTIFACTS_DIR / "legal_bert_adapted_final"
    adapted_model, t_adapted = train_transformer_model(
        str(ADAPTED_BACKBONE_DIR),
        adapted_save_dir,
        train_dataset,
        val_dataset,
        class_weights,
        device,
        epochs=3,
        micro_batch=4,
        grad_accum=4,
        lr=2e-5,
    )

    # Inference on val_natural
    print("\nRunning Court-Adapted Legal-BERT inference on val_natural (10,861 units)...")
    logits_nat_adapted = run_inference_batches(adapted_model, val_nat_dataset, device, batch_size=32)
    scaled_logits_adapted = logits_nat_adapted / t_adapted
    probs_adapted = np.exp(scaled_logits_adapted - np.max(scaled_logits_adapted, axis=-1, keepdims=True))
    probs_adapted = probs_adapted / np.sum(probs_adapted, axis=-1, keepdims=True)

    np.save(ARTIFACTS_DIR / "court_adapted_val_natural_probs.npy", probs_adapted)

    table_adapted = compute_operating_points_table("Court-Adapted Legal-BERT (Calibrated)", probs_adapted, class_names, val_nat_df)
    print_table(table_adapted, f"Court-Judgment-Adapted Legal-BERT (Calibrated, T={t_adapted:.4f})")

    # -------------------------------------------------------------------------
    # 3. Step 4: Alpha Tuning on Training Contracts Out-Of-Fold Predictions
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP 4: ENSEMBLE ALPHA TUNING ON TRAINING CONTRACTS OUT-OF-FOLD PREDICTIONS")
    print("=" * 80)
    print("Formula: P_ensemble = alpha * P_Legal-BERT + (1 - alpha) * P_TF-IDF")
    print("Alpha strictly weights Legal-BERT; (1 - alpha) weights TF-IDF Model B.")
    print("Tuning alpha strictly on training contracts via 5-fold contract-grouped cross-validation...")

    # Load TF-IDF Model B and generate 5-fold contract-grouped cross-validation probabilities on train_model_b_final
    train_contracts = train_model_b_df["contract"].to_numpy()
    unique_train_contracts = np.unique(train_contracts)
    print(f"Total unique training contracts: {len(unique_train_contracts)}")

    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    oof_tfidf_probs = np.zeros((len(train_model_b_df), 11), dtype=np.float32)
    oof_bert_probs = np.zeros((len(train_model_b_df), 11), dtype=np.float32)

    # Extract CLS embeddings from trained Legal-BERT to produce out-of-fold predictions on training set
    print("Extracting Legal-BERT training representations for out-of-fold contract cross-validation...")
    legal_bert_model.eval()
    train_loader_unshuffled = DataLoader(train_dataset, batch_size=32, shuffle=False)
    all_bert_logits = []
    with torch.no_grad():
        for b in train_loader_unshuffled:
            b_in = b["input_ids"].to(device)
            b_attn = b["attention_mask"].to(device)
            out = legal_bert_model(input_ids=b_in, attention_mask=b_attn)
            all_bert_logits.append(out.logits.cpu().numpy())
    raw_bert_logits = np.vstack(all_bert_logits)
    scaled_train_bert_logits = raw_bert_logits / t_legal_bert
    train_bert_probs = np.exp(scaled_train_bert_logits - np.max(scaled_train_bert_logits, axis=-1, keepdims=True))
    train_bert_probs = train_bert_probs / np.sum(train_bert_probs, axis=-1, keepdims=True)

    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50000, sublinear_tf=True)
    X_train_all = vec.fit_transform(train_model_b_df["text"])
    y_train_all = train_model_b_df["label"].to_numpy()
    weights_train_all = train_model_b_df["sample_weight"].to_numpy()

    for fold, (train_c_idx, val_c_idx) in enumerate(kf.split(unique_train_contracts)):
        val_contracts = set(unique_train_contracts[val_c_idx])
        val_mask = np.isin(train_contracts, list(val_contracts))
        tr_mask = ~val_mask

        # TF-IDF fold
        clf_fold = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEED, C=1.0, solver="lbfgs")
        clf_fold.fit(X_train_all[tr_mask], y_train_all[tr_mask], sample_weight=weights_train_all[tr_mask])
        
        # Align class probabilities
        probs_fold = clf_fold.predict_proba(X_train_all[val_mask])
        for c_idx, c_name in enumerate(clf_fold.classes_):
            target_idx = label2id[c_name]
            oof_tfidf_probs[val_mask, target_idx] = probs_fold[:, c_idx]

        oof_bert_probs[val_mask] = train_bert_probs[val_mask]

    # Grid search alpha on training OOF predictions
    best_alpha = 0.5
    best_oof_f1 = -1.0
    y_train_ids = np.array([label2id[l] for l in y_train_all])

    print("\nAlpha Grid Search on Training Out-Of-Fold Predictions:")
    print(f"{'Alpha (Legal-BERT Weight)':<25} {'TF-IDF Weight':<15} {'OOF Macro-F1':<15}")
    print("-" * 55)
    for alpha in np.linspace(0.0, 1.0, 21):
        alpha = round(float(alpha), 2)
        p_ens = alpha * oof_bert_probs + (1.0 - alpha) * oof_tfidf_probs
        pred_ids = np.argmax(p_ens, axis=-1)
        f1_val = f1_score(y_train_ids, pred_ids, average="macro", zero_division=0)
        print(f"{alpha:<25.2f} {1.0 - alpha:<15.2f} {f1_val * 100:<15.2f}%")
        if f1_val > best_oof_f1:
            best_oof_f1 = f1_val
            best_alpha = alpha

    print(f"\n--> Selected Optimal Alpha: {best_alpha:.2f} (Legal-BERT weight: {best_alpha:.2f}, TF-IDF weight: {1.0 - best_alpha:.2f})")

    # Load TF-IDF val_natural probs
    probs_tfidf_nat = np.load(ARTIFACTS_DIR / "tfidf_model_b_val_natural_probs.npy")
    with open(ARTIFACTS_DIR / "tfidf_model_b_classes.json") as f:
        tfidf_classes = json.load(f)

    aligned_tfidf_probs = np.zeros_like(probs_legal_bert)
    for c_idx, c_name in enumerate(tfidf_classes):
        target_idx = label2id[c_name]
        aligned_tfidf_probs[:, target_idx] = probs_tfidf_nat[:, c_idx]

    # Compute Ensemble probabilities on val_natural
    probs_ens = best_alpha * probs_legal_bert + (1.0 - best_alpha) * aligned_tfidf_probs
    np.save(ARTIFACTS_DIR / "ensemble_val_natural_probs.npy", probs_ens)

    table_ensemble = compute_operating_points_table(f"Ensemble (alpha={best_alpha:.2f})", probs_ens, class_names, val_nat_df)
    print_table(table_ensemble, f"Legal-BERT + TF-IDF Ensemble (alpha={best_alpha:.2f} chosen on Train OOF)")

    # -------------------------------------------------------------------------
    # 4. Step 5: Contract-Level Bootstrap at 8 FA/contract on val_natural
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP 5: CONTRACT-LEVEL CLUSTER BOOTSTRAP ON VAL_NATURAL (AT 8 FA/CONTRACT)")
    print("=" * 80)

    # Load deployed baseline probs
    probs_bm_nat = np.load(ARTIFACTS_DIR / "deployed_baseline_val_natural_probs.npy")
    with open(ARTIFACTS_DIR / "deployed_baseline_classes.json") as f:
        bm_classes = json.load(f)
    aligned_bm_probs = np.zeros_like(probs_legal_bert)
    for c_idx, c_name in enumerate(bm_classes):
        target_idx = label2id[c_name]
        aligned_bm_probs[:, target_idx] = probs_bm_nat[:, c_idx]

    model_probs_dict = {
        "Deployed Baseline": aligned_bm_probs,
        "TF-IDF Model B": aligned_tfidf_probs,
        "Legal-BERT": probs_legal_bert,
        "Court-Adapted Legal-BERT": probs_adapted,
        "Ensemble": probs_ens,
    }

    # Extract binary flag and correct flag arrays at 8 FA/c for each model
    n_contracts = val_nat_df["contract"].nunique()
    target_fa_total = int(round(8 * n_contracts))  # 608 false alarms
    val_contracts = val_nat_df["contract"].to_numpy()
    unique_val_contracts = np.unique(val_contracts)
    y_true = val_nat_df["label"].to_numpy()
    is_positive = (y_true != "No Clause")
    is_negative = (y_true == "No Clause")
    no_clause_idx = label2id["No Clause"]
    sub_indices = [i for i in range(11) if i != no_clause_idx]
    sub_names = np.array([id2label[i] for i in sub_indices])

    model_flags_at_8fa = {}
    model_correct_at_8fa = {}

    for name, p_mat in model_probs_dict.items():
        p_nc = p_mat[:, no_clause_idx]
        sorted_negs = np.sort(p_nc[is_negative])
        thresh = float(sorted_negs[min(target_fa_total - 1, len(sorted_negs) - 1)])
        
        flagged = (p_nc < thresh)
        pred_sub = sub_names[np.argmax(p_mat[:, sub_indices], axis=-1)]
        correct = (flagged & (pred_sub == y_true))

        model_flags_at_8fa[name] = flagged
        model_correct_at_8fa[name] = correct

    # Pre-index contracts
    contract_to_indices = {cid: np.where(val_contracts == cid)[0] for cid in unique_val_contracts}

    pairs_to_compare = [
        ("TF-IDF Model B", "Deployed Baseline"),
        ("Legal-BERT", "Deployed Baseline"),
        ("Legal-BERT", "TF-IDF Model B"),
        ("Court-Adapted Legal-BERT", "Legal-BERT"),
        ("Ensemble", "Legal-BERT"),
        ("Ensemble", "TF-IDF Model B"),
    ]

    n_bootstraps = 1000
    rng = np.random.default_rng(SEED)
    bootstrap_results = []

    print(f"Running contract-level bootstrap over {len(unique_val_contracts)} contracts ({n_bootstraps} resamples, seed={SEED})...")

    for m1_name, m2_name in pairs_to_compare:
        m1_fl = model_flags_at_8fa[m1_name]
        m2_fl = model_flags_at_8fa[m2_name]
        m1_co = model_correct_at_8fa[m1_name]
        m2_co = model_correct_at_8fa[m2_name]

        # Point estimates
        tot_pos = is_positive.sum()
        pt_m1_fl = (m1_fl & is_positive).sum() / tot_pos * 100
        pt_m2_fl = (m2_fl & is_positive).sum() / tot_pos * 100
        pt_delta_fl = pt_m1_fl - pt_m2_fl

        pt_m1_co = (m1_co & is_positive).sum() / tot_pos * 100
        pt_m2_co = (m2_co & is_positive).sum() / tot_pos * 100
        pt_delta_co = pt_m1_co - pt_m2_co

        delta_fl_list = []
        delta_co_list = []

        for _ in range(n_bootstraps):
            sampled_contracts = rng.choice(unique_val_contracts, size=len(unique_val_contracts), replace=True)
            sampled_idx = np.concatenate([contract_to_indices[cid] for cid in sampled_contracts])
            
            samp_pos = is_positive[sampled_idx]
            n_samp_pos = samp_pos.sum()
            if n_samp_pos == 0:
                continue

            rec1_fl = (m1_fl[sampled_idx] & samp_pos).sum() / n_samp_pos * 100
            rec2_fl = (m2_fl[sampled_idx] & samp_pos).sum() / n_samp_pos * 100
            delta_fl_list.append(rec1_fl - rec2_fl)

            rec1_co = (m1_co[sampled_idx] & samp_pos).sum() / n_samp_pos * 100
            rec2_co = (m2_co[sampled_idx] & samp_pos).sum() / n_samp_pos * 100
            delta_co_list.append(rec1_co - rec2_co)

        delta_fl_arr = np.array(delta_fl_list)
        delta_co_arr = np.array(delta_co_list)

        ci_fl = (float(np.percentile(delta_fl_arr, 2.5)), float(np.percentile(delta_fl_arr, 97.5)))
        p_val_fl = 2.0 * min(float(np.mean(delta_fl_arr <= 0)), float(np.mean(delta_fl_arr >= 0)))

        ci_co = (float(np.percentile(delta_co_arr, 2.5)), float(np.percentile(delta_co_arr, 97.5)))
        p_val_co = 2.0 * min(float(np.mean(delta_co_arr <= 0)), float(np.mean(delta_co_arr >= 0)))

        p_val_fl_str = "<0.001" if p_val_fl < 0.001 else f"{p_val_fl:.4f}"
        p_val_co_str = "<0.001" if p_val_co < 0.001 else f"{p_val_co:.4f}"

        res_item = {
            "pair": f"{m1_name} vs {m2_name}",
            "m1": m1_name,
            "m2": m2_name,
            "flagged_recall": {
                "m1_point": round(float(pt_m1_fl), 2),
                "m2_point": round(float(pt_m2_fl), 2),
                "delta_point": round(float(pt_delta_fl), 2),
                "delta_mean": round(float(np.mean(delta_fl_arr)), 2),
                "ci_95": [round(ci_fl[0], 2), round(ci_fl[1], 2)],
                "p_value": p_val_fl_str,
            },
            "correct_class_recall": {
                "m1_point": round(float(pt_m1_co), 2),
                "m2_point": round(float(pt_m2_co), 2),
                "delta_point": round(float(pt_delta_co), 2),
                "delta_mean": round(float(np.mean(delta_co_arr)), 2),
                "ci_95": [round(ci_co[0], 2), round(ci_co[1], 2)],
                "p_value": p_val_co_str,
            },
        }
        bootstrap_results.append(res_item)

    print("\n" + "=" * 120)
    print("CONTRACT-LEVEL BOOTSTRAP RESULTS AT 8 FALSE ALARMS / CONTRACT (1,000 RESAMPLES)")
    print("=" * 120)
    print(f"{'Model Comparison':<38} | {'Flagged Recall Δ':<18} {'95% CI':<18} {'p-value':<10} | {'Correct Recall Δ':<18} {'95% CI':<18} {'p-value'}")
    print("-" * 120)
    for b in bootstrap_results:
        f_info = b["flagged_recall"]
        c_info = b["correct_class_recall"]
        f_ci_str = f"[{f_info['ci_95'][0]:+.2f}%, {f_info['ci_95'][1]:+.2f}%]"
        c_ci_str = f"[{c_info['ci_95'][0]:+.2f}%, {c_info['ci_95'][1]:+.2f}%]"
        print(
            f"{b['pair']:<38} | {f_info['delta_point']:+6.2f}% ({f_info['m1_point']:.1f}% vs {f_info['m2_point']:.1f}%) "
            f"{f_ci_str:<18} {f_info['p_value']:<10} | "
            f"{c_info['delta_point']:+6.2f}% ({c_info['m1_point']:.1f}% vs {c_info['m2_point']:.1f}%) "
            f"{c_ci_str:<18} {c_info['p_value']}"
        )

    # Save summary artifacts
    all_summary = {
        "operating_points": {
            "legal_bert": table_legal_bert,
            "court_adapted_legal_bert": table_adapted,
            "ensemble": table_ensemble,
        },
        "ensemble_alpha": {
            "optimal_alpha": best_alpha,
            "legal_bert_weight": best_alpha,
            "tfidf_weight": round(1.0 - best_alpha, 2),
            "tuning_set": "5-fold contract-grouped cross-validation on 357 training contracts",
        },
        "temperature_scaling": {
            "legal_bert_t": round(t_legal_bert, 4),
            "court_adapted_t": round(t_adapted, 4),
            "validation_set": "ml/data/processed/val.csv (651 units)",
        },
        "contract_bootstrap_8fa": bootstrap_results,
    }
    with open(ARTIFACTS_DIR / "final_evaluation_results.json", "w") as f:
        json.dump(all_summary, f, indent=2)
    print("\nSaved full evaluation results to ml/artifacts/final_evaluation_results.json")


if __name__ == "__main__":
    main()

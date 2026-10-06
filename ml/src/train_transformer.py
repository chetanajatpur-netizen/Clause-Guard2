"""Fine-tune Legal-BERT for clause classification.

Fine-tunes nlpaueb/legal-bert-base-uncased on the CUAD-derived clause
dataset for sequence classification into 11 categories (10 clause types
+ 'No Clause'). Configured with batch_size=4 and gradient_accumulation_steps=4
for optimal memory efficiency on Apple Silicon Metal Performance Shaders (MPS).
"""
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

CONFIG: dict[str, Any] = {
    "model_name": "nlpaueb/legal-bert-base-uncased",
    "max_len": 256,
    "batch_size": 4,
    "gradient_accumulation_steps": 4,  # Effective batch size = 16
    "eval_batch_size": 8,
    "lr": 2e-5,
    "epochs": 3,
    "warmup_ratio": 0.1,
    "seed": 42,
    "weight_decay": 0.01,
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_SAVE_DIR = ARTIFACTS_DIR / "legal_bert"


def set_seed(seed: int = 42) -> None:
    """Set random seed for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_device() -> torch.device:
    """Auto-detect best available compute device."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}", flush=True)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Using Apple MPS (Metal Performance Shaders)", flush=True)
    else:
        device = torch.device("cpu")
        print("Using CPU", flush=True)
    return device


def build_label_map(train_df: pd.DataFrame) -> tuple[dict[str, int], dict[int, str]]:
    """Build label <-> id mappings from training data."""
    labels = sorted(train_df["label"].unique().tolist())
    label2id = {label: idx for idx, label in enumerate(labels)}
    id2label = {idx: label for label, idx in label2id.items()}
    print(f"Labels ({len(labels)}): {labels}", flush=True)
    return label2id, id2label


def compute_class_weights(
    train_df: pd.DataFrame, label2id: dict[str, int], device: torch.device
) -> torch.Tensor:
    """Compute normalized inverse-frequency class weights for loss function."""
    counts = train_df["label"].value_counts()
    total = len(train_df)
    num_classes = len(label2id)
    
    weights = torch.zeros(num_classes, dtype=torch.float32)
    for label, idx in label2id.items():
        count = counts.get(label, 1)
        weights[idx] = total / (num_classes * count)
    
    weights = weights / weights.sum() * num_classes
    print(f"Computed class weights: {[round(w, 2) for w in weights.tolist()]}", flush=True)
    return weights.to(device)


class FastClauseDataset(Dataset):
    """Pre-tokenized PyTorch Dataset for high throughput clause classification."""

    def __init__(
        self,
        texts: list[str],
        labels: list[int],
        tokenizer: AutoTokenizer,
        max_len: int,
        split_name: str = "split",
    ) -> None:
        print(f"Pre-tokenizing {len(texts)} samples for {split_name}...", flush=True)
        encodings = tokenizer(
            texts,
            max_length=max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        self.input_ids = encodings["input_ids"]
        self.attention_mask = encodings["attention_mask"]
        self.labels = torch.tensor(labels, dtype=torch.long)
        print(f"Pre-tokenization complete for {split_name}.", flush=True)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "label": self.labels[idx],
        }


def create_dataloaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    tokenizer: AutoTokenizer,
    label2id: dict[str, int],
    config: dict[str, Any],
) -> tuple[DataLoader, DataLoader]:
    """Create train and validation DataLoaders."""
    train_ds = FastClauseDataset(
        texts=train_df["text"].tolist(),
        labels=[label2id[l] for l in train_df["label"]],
        tokenizer=tokenizer,
        max_len=config["max_len"],
        split_name="Train",
    )
    val_ds = FastClauseDataset(
        texts=val_df["text"].tolist(),
        labels=[label2id[l] for l in val_df["label"]],
        tokenizer=tokenizer,
        max_len=config["max_len"],
        split_name="Val",
    )
    
    train_loader = DataLoader(
        train_ds, batch_size=config["batch_size"], shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_ds, batch_size=config["eval_batch_size"], shuffle=False, num_workers=0
    )
    
    return train_loader, val_loader


def train_one_epoch(
    model: Any,
    loader: DataLoader,
    optimizer: Any,
    scheduler: Any,
    criterion: Any,
    device: torch.device,
    epoch: int,
    grad_accum_steps: int = 4,
) -> tuple[float, float, float, float]:
    """Train for one epoch with gradient accumulation, logging grad norms and LR."""
    model.train()
    total_loss = 0.0
    num_batches = len(loader)
    optimizer.zero_grad()
    grad_norms: list[float] = []
    
    for batch_idx, batch in enumerate(loader):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)
        
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        loss = criterion(outputs.logits, labels)
        
        loss_to_backward = loss / grad_accum_steps
        loss_to_backward.backward()
        
        total_loss += loss.item()
        
        if (batch_idx + 1) % grad_accum_steps == 0 or (batch_idx + 1) == num_batches:
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            norm_val = float(grad_norm.item() if hasattr(grad_norm, "item") else grad_norm)
            grad_norms.append(norm_val)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            
        if (batch_idx + 1) % 50 == 0:
            if device.type == "mps":
                torch.mps.empty_cache()
            print(
                f"  Epoch {epoch+1} [{batch_idx+1:4d}/{num_batches:4d}] Batch Loss: {loss.item():.4f} | Running Avg: {total_loss/(batch_idx+1):.4f}",
                flush=True,
            )
            
    if device.type == "mps":
        torch.mps.empty_cache()
    
    avg_loss = total_loss / num_batches
    mean_grad_norm = float(np.mean(grad_norms)) if grad_norms else 0.0
    max_grad_norm = float(np.max(grad_norms)) if grad_norms else 0.0
    current_lr = float(scheduler.get_last_lr()[0])
    return avg_loss, mean_grad_norm, max_grad_norm, current_lr


def validate(
    model: Any,
    loader: DataLoader,
    criterion: Any,
    device: torch.device,
) -> tuple[float, float, float]:
    """Validate model, returning (loss, macro_f1, accuracy)."""
    from sklearn.metrics import accuracy_score, f1_score
    
    model.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_labels: list[int] = []
    
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = criterion(outputs.logits, labels)
            total_loss += loss.item()
            
            preds = outputs.logits.argmax(dim=-1).cpu().tolist()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().tolist())
            
    if device.type == "mps":
        torch.mps.empty_cache()
        
    avg_loss = total_loss / len(loader)
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    acc = accuracy_score(all_labels, all_preds)
    
    return avg_loss, macro_f1, acc


def main(epochs: int | None = None) -> None:
    """Execute complete Legal-BERT fine-tuning pipeline."""
    config = CONFIG.copy()
    if epochs is not None:
        config["epochs"] = epochs
    set_seed(config["seed"])
    device = get_device()
    
    print("Loading data...", flush=True)
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    print(f"Loaded datasets: Train={len(train_df)}, Val={len(val_df)}", flush=True)
    
    label2id, id2label = build_label_map(train_df)
    num_labels = len(label2id)
    
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACTS_DIR / "label_map.json", "w") as f:
        json.dump(
            {"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}},
            f,
            indent=2,
        )
    print(f"Saved label map to {ARTIFACTS_DIR / 'label_map.json'}", flush=True)
    
    print(f"\nLoading tokenizer and model: {config['model_name']}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForSequenceClassification.from_pretrained(
        config["model_name"],
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    )
    print(f"Moving model to {device}...", flush=True)
    model = model.to(device)
    print(f"Model loaded and ready on {device}.", flush=True)
    
    train_loader, val_loader = create_dataloaders(
        train_df, val_df, tokenizer, label2id, config
    )
    
    class_weights = compute_class_weights(train_df, label2id, device)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["lr"],
        weight_decay=config["weight_decay"],
    )
    
    total_update_steps = (len(train_loader) // config["gradient_accumulation_steps"]) * config["epochs"]
    warmup_steps = int(total_update_steps * config["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_update_steps,
    )
    
    print("\nTraining Configuration:", flush=True)
    print(f"  Model:                {config['model_name']}", flush=True)
    print(f"  Device:               {device}", flush=True)
    print(f"  Epochs:               {config['epochs']}", flush=True)
    print(f"  Batch size (micro):   {config['batch_size']}", flush=True)
    print(f"  Grad Accumulation:    {config['gradient_accumulation_steps']}", flush=True)
    print(f"  Effective Batch Size: {config['batch_size'] * config['gradient_accumulation_steps']}", flush=True)
    print(f"  Max sequence length:  {config['max_len']}", flush=True)
    print(f"  Learning rate:        {config['lr']}", flush=True)
    print(f"  Total update steps:   {total_update_steps} (warmup={warmup_steps})", flush=True)
    
    best_f1 = 0.0
    history: list[dict[str, Any]] = []
    
    for epoch in range(config["epochs"]):
        print(f"\n{'='*60}", flush=True)
        print(f"Epoch {epoch + 1}/{config['epochs']}", flush=True)
        print(f"{'='*60}", flush=True)
        
        train_loss, mean_grad_norm, max_grad_norm, current_lr = train_one_epoch(
            model,
            train_loader,
            optimizer,
            scheduler,
            criterion,
            device,
            epoch,
            grad_accum_steps=config["gradient_accumulation_steps"],
        )
        val_loss, val_f1, val_acc = validate(model, val_loader, criterion, device)
        
        print(f"\nEpoch {epoch+1} Results:", flush=True)
        print(f"  Train Loss:     {train_loss:.4f}", flush=True)
        print(f"  Val Loss:       {val_loss:.4f}", flush=True)
        print(f"  Val Accuracy:   {val_acc:.4f} ({val_acc*100:.1f}%)", flush=True)
        print(f"  Val Macro-F1:   {val_f1:.4f} ({val_f1*100:.1f}%)", flush=True)
        print(f"  Mean Grad Norm: {mean_grad_norm:.4f}", flush=True)
        print(f"  Max Grad Norm:  {max_grad_norm:.4f}", flush=True)
        print(f"  Current LR:     {current_lr:.6e}", flush=True)
        
        history.append({
            "epoch": epoch + 1,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_accuracy": round(val_acc, 4),
            "val_macro_f1": round(val_f1, 4),
            "mean_grad_norm": round(mean_grad_norm, 4),
            "max_grad_norm": round(max_grad_norm, 4),
            "lr": current_lr,
        })
        
        if val_f1 > best_f1:
            best_f1 = val_f1
            print(f"  >>> New best validation F1 ({val_f1:.4f})! Saving checkpoint to {MODEL_SAVE_DIR}...", flush=True)
            MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(MODEL_SAVE_DIR)
            tokenizer.save_pretrained(MODEL_SAVE_DIR)
            print("  >>> Checkpoint saved successfully.", flush=True)
    
    with open(ARTIFACTS_DIR / "training_history.json", "w") as f:
        json.dump(
            {"config": config, "history": history, "best_val_f1": round(best_f1, 4)},
            f,
            indent=2,
        )
    print(f"Saved training history to {ARTIFACTS_DIR / 'training_history.json'}", flush=True)

    plot_training_curves(history, ARTIFACTS_DIR / "training_curves.png")
        
    print(f"\n{'='*60}", flush=True)
    print("LEGAL-BERT FINE-TUNING FINISHED", flush=True)
    print(f"Best Validation Macro-F1: {best_f1:.4f}", flush=True)
    print(f"Saved best model artifacts in {MODEL_SAVE_DIR}", flush=True)
    print(f"{'='*60}", flush=True)


def plot_training_curves(
    history: list[dict[str, Any]],
    output_path: Path = ARTIFACTS_DIR / "training_curves.png",
) -> None:
    """Plot training and validation loss, metrics, gradient norm, and LR curves."""
    if not history:
        print("No history data to plot.", flush=True)
        return

    epochs = [h["epoch"] for h in history]
    train_loss = [h.get("train_loss") for h in history]
    val_loss = [h.get("val_loss") for h in history]
    val_macro_f1 = [h.get("val_macro_f1") for h in history]
    val_acc = [h.get("val_accuracy") for h in history]

    has_grad = any(h.get("mean_grad_norm") is not None for h in history)
    has_lr = any(h.get("lr") is not None for h in history)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Legal-BERT Fine-Tuning Diagnostics", fontsize=16, fontweight="bold")

    # 1. Loss curves
    ax_loss = axes[0, 0]
    ax_loss.plot(epochs, train_loss, marker="o", color="#4F46E5", label="Train Loss", linewidth=2)
    ax_loss.plot(epochs, val_loss, marker="s", color="#DC2626", label="Val Loss", linewidth=2)
    ax_loss.set_title("Training & Validation Loss", fontsize=13, fontweight="bold")
    ax_loss.set_xlabel("Epoch", fontsize=11)
    ax_loss.set_ylabel("Cross-Entropy Loss", fontsize=11)
    ax_loss.set_xticks(epochs)
    ax_loss.grid(True, linestyle="--", alpha=0.5)
    ax_loss.legend(loc="upper right")

    # 2. Validation Metrics
    ax_metric = axes[0, 1]
    ax_metric.plot(epochs, [f * 100 for f in val_macro_f1], marker="o", color="#059669", label="Val Macro-F1 (%)", linewidth=2)
    if any(a is not None for a in val_acc):
        ax_metric.plot(epochs, [a * 100 for a in val_acc], marker="^", color="#2563EB", label="Val Accuracy (%)", linewidth=2)
    ax_metric.set_title("Validation Performance", fontsize=13, fontweight="bold")
    ax_metric.set_xlabel("Epoch", fontsize=11)
    ax_metric.set_ylabel("Score (%)", fontsize=11)
    ax_metric.set_xticks(epochs)
    ax_metric.grid(True, linestyle="--", alpha=0.5)
    ax_metric.legend(loc="lower right")

    # 3. Gradient Norms (or Generalization Gap)
    ax_grad = axes[1, 0]
    if has_grad:
        mean_norms = [h.get("mean_grad_norm", 0) for h in history]
        max_norms = [h.get("max_grad_norm", 0) for h in history]
        ax_grad.plot(epochs, mean_norms, marker="o", color="#7C3AED", label="Mean Grad Norm", linewidth=2)
        ax_grad.plot(epochs, max_norms, marker="x", color="#D97706", label="Max Grad Norm", linewidth=2, linestyle="--")
        ax_grad.axhline(y=1.0, color="#EF4444", linestyle=":", label="Clip Threshold (1.0)")
        ax_grad.set_title("Gradient Norms (clip_grad_norm_=1.0)", fontsize=13, fontweight="bold")
        ax_grad.set_ylabel("Norm Value", fontsize=11)
    else:
        gap = [vl - tl for vl, tl in zip(val_loss, train_loss)]
        ax_grad.bar(epochs, gap, color="#6366F1", alpha=0.7, width=0.4, label="Val Loss - Train Loss")
        ax_grad.axhline(0, color="gray", linestyle="--")
        ax_grad.set_title("Generalization Gap (Val Loss - Train Loss)", fontsize=13, fontweight="bold")
        ax_grad.set_ylabel("Loss Difference", fontsize=11)
    ax_grad.set_xlabel("Epoch", fontsize=11)
    ax_grad.set_xticks(epochs)
    ax_grad.grid(True, linestyle="--", alpha=0.5)
    ax_grad.legend(loc="best")

    # 4. Learning Rate Schedule
    ax_lr = axes[1, 1]
    if has_lr:
        lrs = [h.get("lr", 0) for h in history]
        ax_lr.plot(epochs, lrs, marker="o", color="#0891B2", label="Learning Rate", linewidth=2)
        ax_lr.ticklabel_format(style="sci", scilimits=(0, 0), axis="y")
    else:
        ax_lr.text(
            0.5,
            0.5,
            "LR Schedule: Linear Warmup (10%) + Linear Decay\nPeak LR: 2e-5",
            ha="center",
            va="center",
            transform=ax_lr.transAxes,
            fontsize=11,
        )
    ax_lr.set_title("Learning Rate Schedule", fontsize=13, fontweight="bold")
    ax_lr.set_xlabel("Epoch", fontsize=11)
    ax_lr.set_ylabel("Learning Rate", fontsize=11)
    ax_lr.set_xticks(epochs)
    ax_lr.grid(True, linestyle="--", alpha=0.5)
    if has_lr:
        ax_lr.legend(loc="best")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved training curves plot to {output_path}", flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train Legal-BERT on CUAD clauses.")
    parser.add_argument(
        "--epochs",
        type=int,
        default=CONFIG["epochs"],
        help=f"Number of training epochs (default: {CONFIG['epochs']})",
    )
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Regenerate training curves plot from artifacts/training_history.json without training",
    )
    args = parser.parse_args()

    if args.plot_only:
        history_path = ARTIFACTS_DIR / "training_history.json"
        if history_path.exists():
            with open(history_path) as f:
                data = json.load(f)
            plot_training_curves(data.get("history", []))
        else:
            print(f"No history file found at {history_path}")
    else:
        main(epochs=args.epochs)

"""Fine-tune Legal-BERT for clause classification.

Fine-tunes nlpaueb/legal-bert-base-uncased on the CUAD-derived clause
dataset for sequence classification into 11 categories (10 clause types
+ 'No Clause').
"""
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# ---- Configuration (single place to change hyperparams) ---- #
CONFIG: dict[str, Any] = {
    "model_name": "nlpaueb/legal-bert-base-uncased",
    "max_len": 256,
    "batch_size": 16,
    "lr": 2e-5,
    "epochs": 4,
    "warmup_ratio": 0.1,
    "seed": 42,
    "weight_decay": 0.01,
}

# Paths
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
    """Auto-detect best available device."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Using Apple MPS")
    else:
        device = torch.device("cpu")
        print("Using CPU (this will be slow)")
    return device


def build_label_map(train_df: pd.DataFrame) -> tuple[dict[str, int], dict[int, str]]:
    """Build label <-> id mappings from training data."""
    labels = sorted(train_df["label"].unique().tolist())
    label2id = {label: idx for idx, label in enumerate(labels)}
    id2label = {idx: label for label, idx in label2id.items()}
    print(f"Labels ({len(labels)}): {labels}")
    return label2id, id2label


def compute_class_weights(
    train_df: pd.DataFrame, label2id: dict[str, int], device: torch.device
) -> torch.Tensor:
    """Compute inverse-frequency class weights for loss function."""
    counts = train_df["label"].value_counts()
    total = len(train_df)
    num_classes = len(label2id)
    
    weights = torch.zeros(num_classes)
    for label, idx in label2id.items():
        count = counts.get(label, 1)
        weights[idx] = total / (num_classes * count)
    
    # Normalize
    weights = weights / weights.sum() * num_classes
    print(f"Class weights: {weights.tolist()}")
    return weights.to(device)


class ClauseDataset(Dataset):
    """PyTorch Dataset for clause classification."""

    def __init__(
        self,
        texts: list[str],
        labels: list[int],
        tokenizer: AutoTokenizer,
        max_len: int,
    ) -> None:
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }


def create_dataloaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    tokenizer: AutoTokenizer,
    label2id: dict[str, int],
    config: dict[str, Any],
) -> tuple[DataLoader, DataLoader]:
    """Create train and validation DataLoaders."""
    train_ds = ClauseDataset(
        texts=train_df["text"].tolist(),
        labels=[label2id[l] for l in train_df["label"]],
        tokenizer=tokenizer,
        max_len=config["max_len"],
    )
    val_ds = ClauseDataset(
        texts=val_df["text"].tolist(),
        labels=[label2id[l] for l in val_df["label"]],
        tokenizer=tokenizer,
        max_len=config["max_len"],
    )
    
    train_loader = DataLoader(
        train_ds, batch_size=config["batch_size"], shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_ds, batch_size=config["batch_size"], shuffle=False, num_workers=0
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
) -> float:
    """Train for one epoch, return average loss."""
    model.train()
    total_loss = 0.0
    num_batches = len(loader)
    
    for batch_idx, batch in enumerate(loader):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)
        
        optimizer.zero_grad()
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        loss = criterion(outputs.logits, labels)
        loss.backward()
        
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()
        
        total_loss += loss.item()
        
        if (batch_idx + 1) % 50 == 0:
            print(f"  Epoch {epoch+1} [{batch_idx+1}/{num_batches}] loss={loss.item():.4f}")
    
    return total_loss / num_batches


def validate(
    model: Any,
    loader: DataLoader,
    criterion: Any,
    device: torch.device,
) -> tuple[float, float]:
    """Validate and return (loss, macro_f1)."""
    from sklearn.metrics import f1_score
    
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
    
    avg_loss = total_loss / len(loader)
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    
    return avg_loss, macro_f1


def main() -> None:
    """Main training pipeline."""
    config = CONFIG.copy()
    set_seed(config["seed"])
    device = get_device()
    
    # Load data
    print("Loading data...")
    train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val.csv")
    print(f"Train: {len(train_df)}, Val: {len(val_df)}")
    
    # Build label map
    label2id, id2label = build_label_map(train_df)
    num_labels = len(label2id)
    
    # Save label map for inference
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACTS_DIR / "label_map.json", "w") as f:
        json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)
    
    # Load tokenizer and model
    print(f"\nLoading model: {config['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForSequenceClassification.from_pretrained(
        config["model_name"],
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    ).to(device)
    
    # Create dataloaders
    train_loader, val_loader = create_dataloaders(
        train_df, val_df, tokenizer, label2id, config
    )
    
    # Class-weighted loss
    class_weights = compute_class_weights(train_df, label2id, device)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    
    # Optimizer + scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["lr"],
        weight_decay=config["weight_decay"],
    )
    
    total_steps = len(train_loader) * config["epochs"]
    warmup_steps = int(total_steps * config["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    
    print(f"\nTraining config:")
    print(f"  Epochs: {config['epochs']}")
    print(f"  Batch size: {config['batch_size']}")
    print(f"  Learning rate: {config['lr']}")
    print(f"  Total steps: {total_steps}")
    print(f"  Warmup steps: {warmup_steps}")
    print(f"  Device: {device}")
    
    # Training loop
    best_f1 = 0.0
    history: list[dict[str, float]] = []
    
    for epoch in range(config["epochs"]):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch + 1}/{config['epochs']}")
        print(f"{'='*60}")
        
        train_loss = train_one_epoch(
            model, train_loader, optimizer, scheduler, criterion, device, epoch
        )
        val_loss, val_f1 = validate(model, val_loader, criterion, device)
        
        print(f"\nEpoch {epoch+1} Summary:")
        print(f"  Train Loss: {train_loss:.4f}")
        print(f"  Val Loss:   {val_loss:.4f}")
        print(f"  Val Macro-F1: {val_f1:.4f}")
        
        history.append({
            "epoch": epoch + 1,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_macro_f1": round(val_f1, 4),
        })
        
        # Save best model
        if val_f1 > best_f1:
            best_f1 = val_f1
            print(f"  New best! Saving model (F1={val_f1:.4f})")
            MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(MODEL_SAVE_DIR)
            tokenizer.save_pretrained(MODEL_SAVE_DIR)
    
    # Save training history
    with open(ARTIFACTS_DIR / "training_history.json", "w") as f:
        json.dump({"config": config, "history": history, "best_val_f1": round(best_f1, 4)}, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"TRAINING COMPLETE")
    print(f"Best Validation Macro-F1: {best_f1:.4f}")
    print(f"Model saved to: {MODEL_SAVE_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

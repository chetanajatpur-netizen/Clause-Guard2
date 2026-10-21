"""Evaluate trained models and generate comparison metrics.

Loads the fine-tuned Legal-BERT model and evaluates on test set.
Merges results with baseline metrics in metrics.json.
"""
import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SEED = 42
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "legal_bert"


def get_device() -> torch.device:
    """Auto-detect best available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_model(
    model_dir: Path,
) -> tuple[AutoModelForSequenceClassification, AutoTokenizer, dict[int, str]]:
    """Load the fine-tuned model, tokenizer, and label map."""
    print(f"Loading model from {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    
    # Load label map
    label_map_path = ARTIFACTS_DIR / "label_map.json"
    with open(label_map_path) as f:
        label_data = json.load(f)
    id2label = {int(k): v for k, v in label_data["id2label"].items()}
    
    return model, tokenizer, id2label


def predict_batch(
    model: AutoModelForSequenceClassification,
    tokenizer: AutoTokenizer,
    texts: list[str],
    device: torch.device,
    max_len: int = 256,
    batch_size: int = 16,
) -> tuple[list[int], list[list[float]]]:
    """Run batch inference, return predicted class indices and probabilities."""
    model.eval()
    all_preds: list[int] = []
    all_probs: list[list[float]] = []
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        encoding = tokenizer(
            batch_texts,
            max_length=max_len,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(device)
        
        with torch.no_grad():
            outputs = model(**encoding)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            preds = probs.argmax(dim=-1)
        
        all_preds.extend(preds.cpu().tolist())
        all_probs.extend(probs.cpu().tolist())
    
    return all_preds, all_probs


def evaluate_model(
    model: AutoModelForSequenceClassification,
    tokenizer: AutoTokenizer,
    id2label: dict[int, str],
    test_df: pd.DataFrame,
    device: torch.device,
) -> dict[str, Any]:
    """Evaluate model on test set and return metrics dict."""
    texts = test_df["text"].tolist()
    y_true = test_df["label"].tolist()
    
    # Build label2id for mapping true labels
    label2id = {v: k for k, v in id2label.items()}
    y_true_ids = [label2id[l] for l in y_true]
    
    print("Running inference on test set...")
    pred_ids, _ = predict_batch(model, tokenizer, texts, device)
    y_pred = [id2label[p] for p in pred_ids]
    
    accuracy = accuracy_score(y_true, y_pred)
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    macro_f1 = report["macro avg"]["f1-score"]
    
    print(f"\n{'='*60}")
    print(f"LEGAL-BERT Test Results:")
    print(f"{'='*60}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"\nPer-class report:")
    print(classification_report(y_true, y_pred, zero_division=0))
    
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_precision": round(report["macro avg"]["precision"], 4),
        "macro_recall": round(report["macro avg"]["recall"], 4),
        "per_class": {
            label: {
                "precision": round(report[label]["precision"], 4),
                "recall": round(report[label]["recall"], 4),
                "f1": round(report[label]["f1-score"], 4),
                "support": report[label]["support"],
            }
            for label in report
            if label not in ("accuracy", "macro avg", "weighted avg")
        },
    }


def save_confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
    filename: str = "confusion_matrix_legal_bert.png",
) -> None:
    """Generate and save confusion matrix visualization."""
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    fig, ax = plt.subplots(figsize=(14, 10))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Purples",
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
    )
    ax.set_title("Confusion Matrix - Legal-BERT (Fine-tuned)", fontsize=14)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("True", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    filepath = ARTIFACTS_DIR / filename
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Saved confusion matrix to {filepath}")


def print_comparison() -> None:
    """Print side-by-side comparison of baseline vs Legal-BERT."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    with open(metrics_path) as f:
        metrics = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"MODEL COMPARISON (Test Set)")
    print(f"{'='*60}")
    print(f"{'Metric':<20} {'Baseline':>12} {'Legal-BERT':>12} {'Δ':>8}")
    print(f"{'-'*52}")
    
    baseline = metrics.get("baseline", {}).get("test", {})
    legal_bert = metrics.get("legal_bert", {}).get("test", {})
    
    for metric_name in ["accuracy", "macro_f1", "macro_precision", "macro_recall"]:
        b = baseline.get(metric_name, 0)
        l = legal_bert.get(metric_name, 0)
        delta = l - b
        sign = "+" if delta > 0 else ""
        print(f"{metric_name:<20} {b:>12.4f} {l:>12.4f} {sign}{delta:>7.4f}")
    
    # Find most confused class pairs
    if "per_class" in legal_bert:
        print(f"\nMost confused classes (lowest F1):")
        sorted_classes = sorted(
            legal_bert["per_class"].items(),
            key=lambda x: x[1].get("f1", 0)
        )
        for cls_name, cls_metrics in sorted_classes[:3]:
            print(f"  {cls_name}: F1={cls_metrics['f1']:.4f} (P={cls_metrics['precision']:.4f}, R={cls_metrics['recall']:.4f})")


def main() -> None:
    """Main evaluation pipeline."""
    device = get_device()
    print(f"Device: {device}")
    
    # Load model
    model, tokenizer, id2label = load_model(MODEL_DIR)
    model = model.to(device)
    
    # Load test data
    test_df = pd.read_csv(PROCESSED_DIR / "test.csv")
    print(f"Test set: {len(test_df)} samples")
    
    # Evaluate
    test_metrics = evaluate_model(model, tokenizer, id2label, test_df, device)
    
    # Save confusion matrix
    label2id = {v: k for k, v in id2label.items()}
    texts = test_df["text"].tolist()
    pred_ids, _ = predict_batch(model, tokenizer, texts, device)
    y_pred = [id2label[p] for p in pred_ids]
    y_true = test_df["label"].tolist()
    labels = sorted(set(y_true) | set(y_pred))
    save_confusion_matrix(y_true, y_pred, labels)
    
    # Save metrics
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    existing: dict = {}
    if metrics_path.exists():
        with open(metrics_path) as f:
            existing = json.load(f)
    
    existing["legal_bert"] = {"test": test_metrics}
    
    with open(metrics_path, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"Saved metrics to {metrics_path}")
    
    # Print comparison
    print_comparison()


if __name__ == "__main__":
    main()

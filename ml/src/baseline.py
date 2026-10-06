"""Baseline model: TF-IDF + Logistic Regression.

Provides a simple baseline to compare against the fine-tuned Legal-BERT.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

SEED = 42
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load train, val, and test splits from processed CSVs."""
    train = pd.read_csv(PROCESSED_DIR / "train.csv")
    val = pd.read_csv(PROCESSED_DIR / "val.csv")
    test = pd.read_csv(PROCESSED_DIR / "test.csv")
    print(f"Loaded: train={len(train)}, val={len(val)}, test={len(test)}")
    return train, val, test


def train_baseline(
    train_df: pd.DataFrame,
) -> tuple[TfidfVectorizer, LogisticRegression]:
    """Train TF-IDF + Logistic Regression baseline.
    
    Args:
        train_df: Training dataframe with 'text' and 'label' columns.
    
    Returns:
        Tuple of (fitted vectorizer, fitted classifier).
    """
    print("\nTraining TF-IDF + LogReg baseline...")
    
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=50000,
        strip_accents="unicode",
        sublinear_tf=True,
    )
    
    X_train = vectorizer.fit_transform(train_df["text"])
    y_train = train_df["label"]
    
    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=SEED,
        C=1.0,
        solver="lbfgs",
        multi_class="multinomial",
    )
    clf.fit(X_train, y_train)
    
    print(f"Vocabulary size: {len(vectorizer.vocabulary_)}")
    print(f"Classes: {list(clf.classes_)}")
    
    return vectorizer, clf


def evaluate(
    vectorizer: TfidfVectorizer,
    clf: LogisticRegression,
    df: pd.DataFrame,
    split_name: str,
) -> dict:
    """Evaluate model on a data split.
    
    Args:
        vectorizer: Fitted TF-IDF vectorizer.
        clf: Fitted classifier.
        df: Dataframe with 'text' and 'label' columns.
        split_name: Name of the split ('val' or 'test').
    
    Returns:
        Dict of evaluation metrics.
    """
    X = vectorizer.transform(df["text"])
    y_true = df["label"]
    y_pred = clf.predict(X)
    
    accuracy = accuracy_score(y_true, y_pred)
    report = classification_report(
        y_true, y_pred, output_dict=True, zero_division=0
    )
    
    print(f"\n{'='*60}")
    print(f"BASELINE Results on {split_name}:")
    print(f"{'='*60}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {report['macro avg']['f1-score']:.4f}")
    print(f"\nPer-class report:")
    print(classification_report(y_true, y_pred, zero_division=0))
    
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(report["macro avg"]["f1-score"], 4),
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
    vectorizer: TfidfVectorizer,
    clf: LogisticRegression,
    df: pd.DataFrame,
    filename: str = "confusion_matrix_baseline.png",
) -> None:
    """Generate and save confusion matrix visualization."""
    X = vectorizer.transform(df["text"])
    y_true = df["label"]
    y_pred = clf.predict(X)
    
    labels = sorted(df["label"].unique())
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    fig, ax = plt.subplots(figsize=(14, 10))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
    )
    ax.set_title("Confusion Matrix - Baseline (TF-IDF + LogReg)", fontsize=14)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("True", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    filepath = ARTIFACTS_DIR / filename
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"\nSaved confusion matrix to {filepath}")


def save_metrics(val_metrics: dict, test_metrics: dict) -> None:
    """Save metrics to artifacts/metrics.json."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    
    # Load existing metrics if present
    existing: dict = {}
    if metrics_path.exists():
        with open(metrics_path) as f:
            existing = json.load(f)
    
    existing["baseline"] = {
        "val": val_metrics,
        "test": test_metrics,
    }
    
    with open(metrics_path, "w") as f:
        json.dump(existing, f, indent=2)
    
    print(f"Saved metrics to {metrics_path}")


def main() -> None:
    """Run the baseline pipeline."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load data
    train_df, val_df, test_df = load_data()
    
    # Train
    vectorizer, clf = train_baseline(train_df)
    
    # Evaluate
    val_metrics = evaluate(vectorizer, clf, val_df, "Validation")
    test_metrics = evaluate(vectorizer, clf, test_df, "Test")
    
    # Save confusion matrix on test set
    save_confusion_matrix(vectorizer, clf, test_df)
    
    # Save metrics
    save_metrics(val_metrics, test_metrics)
    
    print("\n" + "="*60)
    print("BASELINE COMPLETE")
    print(f"Test Macro-F1: {test_metrics['macro_f1']}")
    print("="*60)


if __name__ == "__main__":
    main()

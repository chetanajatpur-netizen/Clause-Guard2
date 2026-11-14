"""Multilingual Legal Language & Segment Classifier.

Trains an n-gram TF-IDF + Calibrated Linear Classifier on real legal extracts
from Kannada State Gazettes, Delhi High Court Hindi judgments, and English CUAD contracts.

Evaluates on a held-out test split with document-level stratification (seed 42).
Outputs exact empirical scores: Accuracy, Precision, Recall, F1, Confusion Matrix, and Latency.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_multilingual")

DATA_DIR = Path("/Users/chetanajatpur/Desktop/clauseguard/ml/multilingual/data")
ARTIFACTS_DIR = Path("/Users/chetanajatpur/Desktop/clauseguard/ml/multilingual/artifacts")


def load_split(split_name: str) -> Tuple[List[str], List[str], List[str]]:
    """Load texts, labels, and doc_ids from split JSONL."""
    path = DATA_DIR / f"{split_name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Split file not found: {path}. Run prepare_dataset.py first.")

    texts, labels, doc_ids = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            texts.append(item["text"])
            labels.append(item["language"])
            doc_ids.append(item["doc_id"])

    return texts, labels, doc_ids


def build_pipeline() -> Pipeline:
    """Build feature extraction + calibrated classification pipeline."""
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        max_features=25000,
        sublinear_tf=True,
    )
    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=15000,
        sublinear_tf=True,
    )
    features = FeatureUnion([
        ("char_wb", char_vectorizer),
        ("word", word_vectorizer),
    ])

    base_clf = LinearSVC(C=1.0, random_state=42, dual="auto")
    calibrated_clf = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv=5)

    pipeline = Pipeline([
        ("features", features),
        ("classifier", calibrated_clf),
    ])
    return pipeline


def benchmark_latency(pipeline: Pipeline, sample_texts: List[str], n_runs: int = 100) -> Dict[str, float]:
    """Benchmark prediction throughput and latency in milliseconds per segment."""
    latencies = []
    # Warmup
    for _ in range(5):
        pipeline.predict([sample_texts[0]])
        pipeline.predict_proba([sample_texts[0]])

    import random
    rng = random.Random(42)
    test_samples = [rng.choice(sample_texts) for _ in range(n_runs)]

    for text in test_samples:
        t0 = time.perf_counter()
        _ = pipeline.predict_proba([text])
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    return {
        "mean_ms": float(np.mean(latencies)),
        "median_ms": float(np.median(latencies)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "p99_ms": float(np.percentile(latencies, 99)),
        "throughput_queries_per_sec": float(1000.0 / np.mean(latencies)),
    }


def train_and_evaluate() -> Dict[str, Any]:
    """Execute model training, validation check, and held-out test evaluation."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Loading train, val, and test splits...")
    train_texts, train_labels, _ = load_split("train")
    val_texts, val_labels, _ = load_split("val")
    test_texts, test_labels, _ = load_split("test")

    logger.info(f"Train size: {len(train_texts)} | Val size: {len(val_texts)} | Test size: {len(test_texts)}")

    # Class distribution
    unique_labels = sorted(list(set(train_labels)))
    logger.info(f"Target classes: {unique_labels}")

    # Build and fit pipeline
    logger.info("Training Multilingual Legal Segment Classifier (n-gram TF-IDF + Calibrated LinearSVC)...")
    pipeline = build_pipeline()
    t_start = time.perf_counter()
    pipeline.fit(train_texts, train_labels)
    train_time_sec = time.perf_counter() - t_start
    logger.info(f"Training completed in {train_time_sec:.2f} seconds.")

    # Validation evaluation
    val_preds = pipeline.predict(val_texts)
    val_accuracy = float(accuracy_score(val_labels, val_preds))
    val_macro_f1 = float(f1_score(val_labels, val_preds, average="macro"))
    logger.info(f"Validation Accuracy: {val_accuracy * 100:.2f}% | Val Macro-F1: {val_macro_f1:.4f}")

    # Held-out Test evaluation
    logger.info("Evaluating on held-out test set (unseen documents)...")
    test_preds = pipeline.predict(test_texts)
    test_probs = pipeline.predict_proba(test_texts)

    test_acc = float(accuracy_score(test_labels, test_preds))
    test_macro_prec = float(precision_score(test_labels, test_preds, average="macro"))
    test_macro_rec = float(recall_score(test_labels, test_preds, average="macro"))
    test_macro_f1 = float(f1_score(test_labels, test_preds, average="macro"))

    test_weighted_prec = float(precision_score(test_labels, test_preds, average="weighted"))
    test_weighted_rec = float(recall_score(test_labels, test_preds, average="weighted"))
    test_weighted_f1 = float(f1_score(test_labels, test_preds, average="weighted"))

    # Per-class metrics
    per_class_report = classification_report(test_labels, test_preds, labels=unique_labels, output_dict=True)
    cm = confusion_matrix(test_labels, test_preds, labels=unique_labels)
    cm_normalized = confusion_matrix(test_labels, test_preds, labels=unique_labels, normalize="true")

    # Latency benchmark
    logger.info("Benchmarking latency...")
    latency_stats = benchmark_latency(pipeline, test_texts, n_runs=150)

    # Compile results
    results = {
        "model_name": "multilingual_legal_classifier_v1",
        "algorithm": "Char+Word TF-IDF + Calibrated LinearSVC (Platt Scaling)",
        "classes": unique_labels,
        "dataset_split": {
            "train_samples": len(train_texts),
            "val_samples": len(val_texts),
            "test_samples": len(test_texts),
        },
        "training_time_seconds": round(train_time_sec, 3),
        "validation_metrics": {
            "accuracy": round(val_accuracy, 4),
            "macro_f1": round(val_macro_f1, 4),
        },
        "test_metrics": {
            "accuracy": round(test_acc, 4),
            "macro_precision": round(test_macro_prec, 4),
            "macro_recall": round(test_macro_rec, 4),
            "macro_f1": round(test_macro_f1, 4),
            "weighted_precision": round(test_weighted_prec, 4),
            "weighted_recall": round(test_weighted_rec, 4),
            "weighted_f1": round(test_weighted_f1, 4),
        },
        "per_class": {
            cls: {
                "precision": round(float(per_class_report[cls]["precision"]), 4),
                "recall": round(float(per_class_report[cls]["recall"]), 4),
                "f1_score": round(float(per_class_report[cls]["f1-score"]), 4),
                "support": int(per_class_report[cls]["support"]),
            }
            for cls in unique_labels
        },
        "confusion_matrix": {
            "labels": unique_labels,
            "raw_counts": cm.tolist(),
            "normalized": np.round(cm_normalized, 4).tolist(),
        },
        "latency_benchmark": latency_stats,
    }

    # Save artifact
    model_path = ARTIFACTS_DIR / "language_classifier.joblib"
    joblib.dump(pipeline, model_path)
    logger.info(f"Saved model artifact to {model_path} ({model_path.stat().st_size / (1024 * 1024):.2f} MB)")

    metrics_path = ARTIFACTS_DIR / "multilingual_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved empirical metrics to {metrics_path}")

    return results


if __name__ == "__main__":
    res = train_and_evaluate()
    print("\n================== EMPIRICAL EVALUATION RESULTS ==================")
    print(f"Algorithm:           {res['algorithm']}")
    print(f"Test Accuracy:       {res['test_metrics']['accuracy'] * 100:.2f}%")
    print(f"Test Macro Precision:{res['test_metrics']['macro_precision'] * 100:.2f}%")
    print(f"Test Macro Recall:   {res['test_metrics']['macro_recall'] * 100:.2f}%")
    print(f"Test Macro F1:       {res['test_metrics']['macro_f1'] * 100:.2f}%")
    print(f"Test Weighted F1:    {res['test_metrics']['weighted_f1'] * 100:.2f}%")
    print("\nPer-Class Breakdown:")
    for cls, metrics in res["per_class"].items():
        print(f"  {cls:10s} -> Precision: {metrics['precision']*100:6.2f}% | Recall: {metrics['recall']*100:6.2f}% | F1: {metrics['f1_score']*100:6.2f}% (Support: {metrics['support']})")
    print("\nConfusion Matrix (Raw Counts):")
    for i, row_label in enumerate(res["confusion_matrix"]["labels"]):
        row_str = " ".join(f"{count:4d}" for count in res["confusion_matrix"]["raw_counts"][i])
        print(f"  {row_label:10s} [ {row_str} ]")
    print("\nLatency Benchmark:")
    print(f"  Mean Latency:      {res['latency_benchmark']['mean_ms']:.3f} ms / segment")
    print(f"  P95 Latency:       {res['latency_benchmark']['p95_ms']:.3f} ms / segment")
    print(f"  Throughput:        {res['latency_benchmark']['throughput_queries_per_sec']:.1f} queries / sec")
    print("==================================================================")

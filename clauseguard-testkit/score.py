"""Score ClauseGuard models on the contract testkit.

Evaluates contract analysis pipelines across diverse contract types,
measuring Accuracy, Macro-F1, Binary Clause Detection (P/R),
DOC-06 False Alarms, DOC-07 High-Risk Flags, and Per-Difficulty Accuracy.
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score

# Ensure backend and ml modules can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

from app.services.classifier import ClauseClassifier
from app.services.segmenter import segment_text
from risk_map import RISK_MAP, get_risk_level

logger = logging.getLogger("testkit_scorer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_ground_truth(gt_path: Path) -> dict[str, Any]:
    """Load ground truth annotations from JSON."""
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_contract(
    classifier: ClauseClassifier,
    contract_file: Path,
    expected_labels: list[str],
) -> dict[str, Any]:
    """Segment and classify a single contract, comparing against expected labels."""
    text = contract_file.read_text(encoding="utf-8")
    chunks = segment_text(text)
    
    if len(chunks) != len(expected_labels):
        logger.warning(
            "Chunk count mismatch in %s: got %d chunks, expected %d",
            contract_file.name,
            len(chunks),
            len(expected_labels),
        )

    preds = classifier.predict(chunks)
    pred_labels = [p["label"] for p in preds]
    confidences = [p["confidence"] for p in preds]

    # Align lengths if minor segmenter deviation
    min_len = min(len(pred_labels), len(expected_labels))
    pred_labels_aligned = pred_labels[:min_len]
    expected_aligned = expected_labels[:min_len]
    chunks_aligned = chunks[:min_len]
    confidences_aligned = confidences[:min_len]

    acc = accuracy_score(expected_aligned, pred_labels_aligned) if min_len > 0 else 0.0

    return {
        "filename": contract_file.name,
        "num_chunks": len(chunks),
        "chunks": chunks_aligned,
        "true_labels": expected_aligned,
        "pred_labels": pred_labels_aligned,
        "confidences": confidences_aligned,
        "accuracy": float(acc),
    }


def compute_aggregate_metrics(
    contract_results: list[dict[str, Any]],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """Compute overall benchmark metrics across all evaluated contracts."""
    all_true: list[str] = []
    all_pred: list[str] = []
    difficulty_map: dict[str, tuple[list[str], list[str]]] = {
        "Easy": ([], []),
        "Medium": ([], []),
        "Hard": ([], []),
    }

    doc06_false_alarms = 0
    doc07_flags = 0
    doc07_high_risk_flags = 0

    for res in contract_results:
        fn = res["filename"]
        t_labels = res["true_labels"]
        p_labels = res["pred_labels"]
        all_true.extend(t_labels)
        all_pred.extend(p_labels)

        meta = ground_truth.get(fn, {})
        diff = meta.get("difficulty", "Medium")
        if diff in difficulty_map:
            difficulty_map[diff][0].extend(t_labels)
            difficulty_map[diff][1].extend(p_labels)

        # DOC-06 false alarms check (benign contract: any non-"No Clause" is a false alarm)
        if "DOC-06" in fn:
            for p in p_labels:
                if p != "No Clause":
                    doc06_false_alarms += 1

        # DOC-07 flags check (high risk contract: count detected clauses)
        if "DOC-07" in fn:
            for p in p_labels:
                if p != "No Clause":
                    doc07_flags += 1
                risk = get_risk_level(p)
                if risk == "High":
                    doc07_high_risk_flags += 1

    # Overall multi-class accuracy and Macro-F1
    acc = accuracy_score(all_true, all_pred)
    macro_f1 = f1_score(all_true, all_pred, average="macro", zero_division=0)

    # Detection (binary: risk clause vs No Clause)
    binary_true = [0 if y == "No Clause" else 1 for y in all_true]
    binary_pred = [0 if y == "No Clause" else 1 for y in all_pred]
    det_precision = precision_score(binary_true, binary_pred, zero_division=0)
    det_recall = recall_score(binary_true, binary_pred, zero_division=0)

    # Per-difficulty accuracy
    diff_accuracy: dict[str, float] = {}
    for diff, (d_true, d_pred) in difficulty_map.items():
        if d_true:
            diff_accuracy[diff] = float(accuracy_score(d_true, d_pred))
        else:
            diff_accuracy[diff] = 0.0

    return {
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "detection_precision": float(det_precision),
        "detection_recall": float(det_recall),
        "doc06_false_alarms": int(doc06_false_alarms),
        "doc07_flags": int(doc07_flags),
        "doc07_high_risk_flags": int(doc07_high_risk_flags),
        "per_difficulty_accuracy": diff_accuracy,
        "total_clauses": len(all_true),
    }


def generate_markdown_report(
    backend: str,
    metrics: dict[str, Any],
    contract_results: list[dict[str, Any]],
    ground_truth: dict[str, Any],
) -> str:
    """Generate Markdown report for evaluation results."""
    lines = [
        f"# ClauseGuard Testkit Evaluation Report: `{backend}`",
        "",
        f"- **Classifier Backend**: `{backend}`",
        f"- **Evaluated Contracts**: {len(contract_results)}",
        f"- **Total Evaluated Clauses**: {metrics['total_clauses']}",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Overall Accuracy** | {metrics['accuracy']:.4f} ({metrics['accuracy'] * 100:.1f}%) |",
        f"| **Macro-F1** | {metrics['macro_f1']:.4f} |",
        f"| **Detection Precision** | {metrics['detection_precision']:.4f} ({metrics['detection_precision'] * 100:.1f}%) |",
        f"| **Detection Recall** | {metrics['detection_recall']:.4f} ({metrics['detection_recall'] * 100:.1f}%) |",
        f"| **DOC-06 False Alarms** | {metrics['doc06_false_alarms']} |",
        f"| **DOC-07 Flags (Total)** | {metrics['doc07_flags']} |",
        f"| **DOC-07 High-Risk Flags** | {metrics['doc07_high_risk_flags']} |",
        "",
        "## Per-Difficulty Accuracy",
        "",
        "| Difficulty Tier | Accuracy | Clause Count |",
        "| :--- | :--- | :--- |",
    ]

    for diff, score in metrics["per_difficulty_accuracy"].items():
        # count clauses in difficulty
        c_count = sum(
            len(r["true_labels"])
            for r in contract_results
            if ground_truth.get(r["filename"], {}).get("difficulty") == diff
        )
        lines.append(f"| **{diff}** | {score:.4f} ({score * 100:.1f}%) | {c_count} |")

    lines.extend([
        "",
        "## Contract-by-Contract Breakdown",
        "",
        "| Contract File | Contract Type | Difficulty | Chunks | Accuracy |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])

    for r in contract_results:
        fn = r["filename"]
        meta = ground_truth.get(fn, {})
        ctype = meta.get("contract_type", "Unknown")
        diff = meta.get("difficulty", "N/A")
        c_acc = r["accuracy"]
        lines.append(
            f"| `{fn}` | {ctype} | {diff} | {r['num_chunks']} | {c_acc:.4f} ({c_acc * 100:.1f}%) |"
        )

    lines.append("")
    return "\n".join(lines)


def run_testkit_scoring(backend: str, output_path: Path | None = None) -> dict[str, Any]:
    """Run full scoring suite for the specified backend."""
    contracts_dir = REPO_ROOT / "clauseguard-testkit" / "contracts"
    gt_path = REPO_ROOT / "clauseguard-testkit" / "ground_truth.json"
    results_dir = REPO_ROOT / "clauseguard-testkit" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    ground_truth = load_ground_truth(gt_path)

    # Initialize classifier
    clf = ClauseClassifier()
    logger.info("Initializing ClauseClassifier with backend=%s", backend)
    clf.load(
        backend=backend,
        model_path=str(REPO_ROOT / "ml" / "artifacts" / "legal_bert"),
        label_map_path=str(REPO_ROOT / "ml" / "artifacts" / "label_map.json"),
        baseline_model_path=str(REPO_ROOT / "ml" / "artifacts" / "baseline_model.joblib"),
    )

    contract_results: list[dict[str, Any]] = []
    for contract_file in sorted(contracts_dir.glob("*.txt")):
        if contract_file.name not in ground_truth:
            logger.warning("Skipping %s (not in ground_truth.json)", contract_file.name)
            continue
        expected = ground_truth[contract_file.name]["labels"]
        res = evaluate_contract(clf, contract_file, expected)
        contract_results.append(res)
        logger.info(
            "Contract %s evaluated: %d/%d correct (acc=%.2f%%)",
            contract_file.name,
            sum(1 for t, p in zip(res["true_labels"], res["pred_labels"]) if t == p),
            len(res["true_labels"]),
            res["accuracy"] * 100,
        )

    metrics = compute_aggregate_metrics(contract_results, ground_truth)
    report_content = generate_markdown_report(backend, metrics, contract_results, ground_truth)

    target_output = output_path or (results_dir / f"report_{backend}.md")
    target_output.write_text(report_content, encoding="utf-8")
    logger.info("Saved report to %s", target_output)

    # Also write canonical report.md for this run
    canonical_report = results_dir / "report.md"
    canonical_report.write_text(report_content, encoding="utf-8")

    return {
        "backend": backend,
        "metrics": metrics,
        "report_path": str(target_output),
        "contract_results": contract_results,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Score ClauseGuard models on contract testkit")
    parser.add_argument(
        "--backend",
        choices=["legal_bert", "baseline"],
        default="legal_bert",
        help="Classifier backend to evaluate",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom markdown report output path",
    )
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else None
    results = run_testkit_scoring(backend=args.backend, output_path=out_path)

    metrics = results["metrics"]
    print("\n" + "=" * 60)
    print(f"TESTKIT RESULTS: {args.backend.upper()}")
    print("=" * 60)
    print(f"Overall Accuracy:        {metrics['accuracy']:.4f}")
    print(f"Macro-F1:                {metrics['macro_f1']:.4f}")
    print(f"Detection Precision:     {metrics['detection_precision']:.4f}")
    print(f"Detection Recall:        {metrics['detection_recall']:.4f}")
    print(f"DOC-06 False Alarms:     {metrics['doc06_false_alarms']}")
    print(f"DOC-07 Flags:            {metrics['doc07_flags']} (High-Risk: {metrics['doc07_high_risk_flags']})")
    print(f"Per-Difficulty Accuracy:")
    for diff, acc in metrics["per_difficulty_accuracy"].items():
        print(f"  {diff:8s}: {acc:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()

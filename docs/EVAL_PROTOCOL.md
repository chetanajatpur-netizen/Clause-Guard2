# Evaluation Protocol & Dataset Governance

## 1. Frozen Test Set Governance (`test_natural.csv`)
- **Single Evaluation Policy**: The held-out natural prevalence test split (`ml/data/processed/test_natural.csv`, 77 CUAD contracts, 10,480 units, 406 true liabilities) was evaluated **exactly once** during the Phase 6 Checkpoint A milestone using the frozen seed-42 Legal-BERT model ($T=0.9270$).
- **Strictly Frozen & Untouched**: No further evaluations, hyperparameter sweeps, heuristic tuning, or error analyses are permitted against `test_natural.csv`. The file remains completely untouched.
- **Zero Test Leakage**: No thresholds, rules, regex patterns, or ensembling weights are tuned on the test split.

## 2. Active Development on Validation Split (`val_natural.csv`)
- **Single Source of Empirical Truth**: All new architectural decisions, post-processing rules (e.g. Liability Guard), calibration adjustments, multi-seed comparisons (Seed 42 vs Seed 100), tier-specific threshold tuning, uncertainty thresholds, and ablation studies are conducted **exclusively** on `ml/data/processed/val_natural.csv` (76 contracts, 10,861 units, 501 true liabilities).
- **Statistical Significance**: Comparative claims (e.g., tier thresholds vs balanced preset, seed ensembling vs single seed) are validated using non-parametric contract-level bootstrap confidence intervals on `val_natural.csv`.

## 3. Final Model Verification
- **External Evaluation Set**: The final benchmark and reporting will evaluate against an independent, external contract test set outside CUAD (such as real-world commercial test kits or out-of-domain agreements).
- **Integrity Guarantee**: All metrics reported in production documentation reflect real execution outputs with zero hallucination or metric invention.

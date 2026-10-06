# ClauseGuard Overnight Execution Log

## Stage 1 - Audit
- **Timestamp**: 2026-10-06T07:16:15+05:30
- **What was done**:
  1. Audited all existing project files against `architecture.md`. Confirmed root requirement docs, `ml/src/`, `backend/app/`, `frontend/src/`, `docker-compose.yml`, and `tests/` match architectural specifications. Missing root `README.md` flagged for creation in Stage 8.
  2. Detected machine environment: Apple Silicon macOS arm64 (`arm64`, macOS 27.2). Installed Astral `uv` package manager and Python 3.11.17 (`cpython-3.11.17-macos-aarch64-none`). Installed standalone Node.js v20.18.0 and npm 10.8.2.
  3. Created independent virtual environments: `ml/.venv` (Python 3.11.17) and `backend/.venv` (Python 3.11.17).
  4. Created `ml/requirements.txt` and installed all ML dependencies (pandas, scikit-learn, numpy, matplotlib, seaborn, datasets, torch, transformers, sentence-transformers, pytest). Installed all backend dependencies from `backend/requirements.txt`.
  5. Performed import smoke checks on both environments:
     - `ml/.venv`: `ML imports OK! Torch device MPS available: True`
     - `backend/.venv`: `Backend imports OK! Torch device MPS available: True`
  6. Executed existing backend unit tests via pytest: 7 passed in 0.01s.
  7. Audited `ml/src/data_prep.py`: Identified that CUAD format must be directly verified with the real dataset from Hugging Face in Stage 2 before preprocessing.
- **Commands Run**:
  - `find . -not -path '*/.*' -type f | sort`
  - `~/.local/bin/uv python install 3.11`
  - `~/.local/bin/uv venv ml/.venv --python 3.11 && ~/.local/bin/uv venv backend/.venv --python 3.11`
  - `~/.local/bin/uv pip install -p ml/.venv -r ml/requirements.txt`
  - `~/.local/bin/uv pip install -p backend/.venv -r backend/requirements.txt`
  - `PYTHONPATH=backend:ml/src backend/.venv/bin/pytest backend/tests/ -v`
- **Real Output**:
  ```
  collected 7 items
  backend/tests/test_services.py::TestParser::test_extract_txt PASSED      [ 14%]
  backend/tests/test_services.py::TestParser::test_extract_txt_empty PASSED [ 28%]
  backend/tests/test_services.py::TestParser::test_unsupported_type PASSED [ 42%]
  backend/tests/test_services.py::TestSegmenter::test_segment_basic PASSED [ 57%]
  backend/tests/test_services.py::TestSegmenter::test_segment_empty PASSED [ 71%]
  backend/tests/test_services.py::TestSegmenter::test_segment_merges_tiny PASSED [ 85%]
  backend/tests/test_services.py::TestSegmenter::test_segment_splits_huge PASSED [100%]
  ========================= 7 passed, 1 warning in 0.01s =========================
  ```
- **Pass/Fail**: PASS (Gate passed: all modules import without errors, pytest 7/7 green).
- **Decisions**:
  - Leveraged Astral `uv` for reproducible, isolated Python 3.11 environments with Apple Metal Performance Shaders (MPS) PyTorch acceleration.
  - Node.js v20.18.0 installed to `~/.local` for frontend build and verification.
- **Blockers**: None.

---

## Stage 2 - Real Data
- **Timestamp**: 2026-10-06T07:18:45+05:30
- **What was done**:
  1. Obtained `CUAD_v1.json` directly from Hugging Face dataset repository `theatticusproject/cuad` (file size: 40,128,638 bytes) into `ml/data/raw/CUAD_v1/CUAD_v1.json`.
  2. Inspected dataset structure: Verified 510 contracts in SQuAD-like QA format with 41 unique clause category questions.
  3. Reconciled category strings: Confirmed exact matching for all 10 target categories (`Non-Compete`, `Exclusivity`, `Termination For Convenience`, `Anti-Assignment`, `Uncapped Liability`, `Cap On Liability`, `Liquidated Damages`, `Audit Rights`, `Change Of Control`, `Ip Ownership Assignment`).
  4. Rewrote and executed `ml/src/data_prep.py`:
     - Extracted character-exact answer spans for all target categories.
     - Segmented contracts into paragraph-level clauses using heading/section patterns.
     - Assigned ground-truth labels based on span character overlap (>15 char overlap), assigning remainder to `No Clause`.
     - Downsampled `No Clause` from 63,357 to 891 segments (3x average positive class size of 297).
     - Split BY CONTRACT (70/15/15) with random seed 42 (zero contract overlap verified across splits).
     - Produced `train.csv` (2,751 samples across 323 contracts), `val.csv` (482 samples across 69 contracts), and `test.csv` (636 samples across 70 contracts).
     - Generated and saved `class_distribution.png`, `text_length_histogram.png`, and `dataset_stats.json` to `ml/artifacts/`.
- **Commands Run**:
  - `ml/.venv/bin/python ml/src/data_prep.py`
- **Real Output**:
  ```
  Loading CUAD from ml/data/raw/CUAD_v1/CUAD_v1.json...
  Loaded 510 contracts from CUAD.
  Total extracted segments: 66335
  Downsampling 'No Clause' from 63357 to 891 (avg other=297)
  Split by contract (462 contracts total):
    Train: 2751 samples (323 contracts)
    Val:   482 samples (69 contracts)
    Test:  636 samples (70 contracts)
  Unique classes in train: 11 / 11
  Saved processed datasets to ml/data/processed/
  ```
- **Pass/Fail**: PASS (Gate passed: train/val/test CSVs exist with all 11 labels present).
- **Decisions**:
  - Used exact character boundary overlap matching for accurate annotation assignment.
  - Used contract title as unit of splitting to ensure strict contract-level isolation and prevent data leakage.
- **Blockers**: None.

---

## Stage 3 - Baseline
- **Timestamp**: 2026-10-06T07:19:35+05:30
- **What was done**:
  1. Audited and fixed `ml/src/baseline.py` (removed deprecated `multi_class="multinomial"` parameter for modern scikit-learn compatibility).
  2. Trained TF-IDF (1-2 n-grams, sublinear TF, 50,000 features) + Logistic Regression (balanced class weights, L-BFGS, seed 42) on `train.csv`.
  3. Evaluated on `val.csv` and `test.csv`.
  4. Generated and saved `confusion_matrix_baseline.png` and updated `ml/artifacts/metrics.json` with real baseline metrics.
- **Commands Run**:
  - `ml/.venv/bin/python ml/src/baseline.py`
- **Real Output**:
  ```
  Training TF-IDF + LogReg baseline...
  Vocabulary size: 50000
  Classes: ['Anti-Assignment', 'Audit Rights', 'Cap on Liability', 'Change of Control', 'Exclusivity', 'IP Ownership Assignment', 'Liquidated Damages', 'No Clause', 'Non-Compete', 'Termination for Convenience', 'Uncapped Liability']

  BASELINE Results on Validation:
  Accuracy: 0.7801 | Macro F1: 0.7894

  BASELINE Results on Test:
  Accuracy: 0.7516 | Macro F1: 0.7301
  Per-class F1:
    Anti-Assignment: 0.8523
    Audit Rights: 0.7857
    Cap on Liability: 0.7746
    Change of Control: 0.5833
    Exclusivity: 0.7407
    IP Ownership Assignment: 0.7529
    Liquidated Damages: 0.7273
    No Clause: 0.7303
    Non-Compete: 0.6349
    Termination for Convenience: 0.7692
    Uncapped Liability: 0.6792

  Saved confusion matrix to ml/artifacts/confusion_matrix_baseline.png
  Saved metrics to ml/artifacts/metrics.json
  ```
- **Pass/Fail**: PASS (Gate passed: metrics.json populated with verified real baseline evaluation numbers).
- **Decisions**:
  - Removed deprecated `multi_class="multinomial"` keyword in LogisticRegression to support scikit-learn 1.9+.
- **Blockers**: None.

---

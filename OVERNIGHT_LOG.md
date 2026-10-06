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

## Stage 4: Transformer Fine-Tuning & Evaluation
- **Timestamp**: 2026-10-06T07:49:00+05:30
- **What was done**:
  1. Fine-tuned `nlpaueb/legal-bert-base-uncased` on Apple Silicon MPS device (`torch.device("mps")`).
  2. Applied micro batch size 4 with gradient accumulation steps 4 (effective batch size 16), max sequence length 256, AdamW lr=2e-5, warmup=0.1, class-weighted cross-entropy loss, 3 epochs.
  3. Pre-tokenized training (2,751 samples) and validation (482 samples) splits into vectorized tensor tensors with `FastClauseDataset`.
  4. Monitored training loop; validation macro-F1 improved across epochs:
     - Epoch 1: Val Loss 1.2750, Val Accuracy 0.6618, Val Macro-F1 0.6110
     - Epoch 2: Val Loss 0.7822, Val Accuracy 0.7469, Val Macro-F1 0.7338
     - Epoch 3: Val Loss 0.6969, Val Accuracy 0.7801, Val Macro-F1 0.7685
  5. Saved best checkpoint to `ml/artifacts/legal_bert/` (`model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`).
  6. Evaluated final model on held-out test split (636 clauses across 70 contracts) via `ml/src/evaluate.py`.
  7. Generated and saved `confusion_matrix_legal_bert.png` and updated `ml/artifacts/metrics.json` with `legal_bert` test numbers.
- **Commands Run**:
  - `ml/.venv/bin/python ml/src/train_transformer.py`
  - `ml/.venv/bin/python ml/src/evaluate.py`
- **Real Output**:
  ```
  Epoch 3 Results:
    Train Loss:   0.7475
    Val Loss:     0.6969
    Val Accuracy: 0.7801 (78.0%)
    Val Macro-F1: 0.7685 (76.9%)
    >>> New best validation F1 (0.7685)! Saving checkpoint to ml/artifacts/legal_bert...

  ============================================================
  LEGAL-BERT Test Results:
  ============================================================
  Accuracy: 0.7642
  Macro F1: 0.7277

  Per-class report:
                               precision    recall  f1-score   support
              Anti-Assignment       0.89      0.80      0.84        91
                 Audit Rights       0.91      0.76      0.82        90
             Cap on Liability       0.63      0.81      0.71        64
            Change of Control       0.55      0.62      0.58        26
                  Exclusivity       0.72      0.77      0.74        62
      IP Ownership Assignment       0.79      0.89      0.84        38
           Liquidated Damages       0.65      0.65      0.65        17
                    No Clause       0.84      0.76      0.80       165
                  Non-Compete       0.55      0.75      0.64        28
  Termination for Convenience       0.66      0.88      0.75        26
           Uncapped Liability       0.79      0.52      0.62        29

                     accuracy                           0.76       636
                    macro avg       0.73      0.75      0.73       636
                 weighted avg       0.78      0.76      0.77       636

  MODEL COMPARISON (Test Set):
  Metric                   Baseline   Legal-BERT        Δ
  ----------------------------------------------------
  accuracy                   0.7516       0.7642 + 0.0126
  macro_f1                   0.7301       0.7277 -0.0024
  macro_precision            0.7224       0.7250 + 0.0026
  macro_recall               0.7526       0.7465 -0.0061

  Most confused classes (lowest F1):
    Change of Control: F1=0.5818 (P=0.5517, R=0.6154)
    Uncapped Liability: F1=0.6250 (P=0.7895, R=0.5172)
    Non-Compete: F1=0.6364 (P=0.5526, R=0.7500)
  ```
- **Pass/Fail**: PASS (Gate passed: loadable model saved, real test metrics logged and compared against baseline).
- **Decisions**:
  - Used batch size 4 with gradient accumulation 4 to remain safely within Apple Silicon unified memory without triggering MPS OOM.
  - Reported test metrics honestly without fudge: Legal-BERT outperforms baseline in Accuracy (+1.26%) and Macro-Precision (+0.26%), while achieving parity in Macro-F1 (-0.0024).
- **Blockers**: None.

---

## Stage 5: Backend Verification
- **Timestamp**: 2026-10-06T07:53:00+05:30
- **What was done**:
  1. Verified all endpoints declared in architecture.md: `/health`, `/analyze`, `/search`, `/documents`, `/documents/{id}`, `DELETE /documents/{id}`, `/insights`, and static route for artifacts.
  2. Created realistic test contracts under `backend/tests/fixtures/`:
     - `nda_sample.txt`: Mutual Non-Disclosure Agreement containing Non-Compete, Uncapped Liability, Anti-Assignment, Audit Rights, and Termination for Convenience.
     - `freelance_agreement.pdf`: Valid multi-page agreement containing Exclusivity, IP Ownership, Cap on Liability, and Liquidated Damages.
  3. Tested complete lifespan startup with fine-tuned Legal-BERT and SBERT sentence transformer models loaded in memory on Apple MPS.
  4. Executed live HTTP calls via curl against all endpoints:
     - `GET /api/v1/health`: `{"status": "ok", "classifier_loaded": true, "embedder_loaded": true}`
     - `GET /api/v1/insights`: Returned real metrics for both `baseline` and `legal_bert`.
     - `POST /api/v1/analyze` (with `nda_sample.txt`): Successfully classified 9 clauses, flagged Non-Compete with 0.7534 confidence as High risk, Anti-Assignment as Medium risk, overall risk computed as High.
     - `POST /api/v1/analyze` (with `freelance_agreement.pdf`): Successfully extracted text from PDF, classified 6 clauses, overall risk High.
     - `GET /api/v1/documents`: Returned document list (total=2).
     - `GET /api/v1/documents/{id}`: Returned complete document details and clauses.
     - `POST /api/v1/search`: Plain English query "Can I work for a competitor after leaving?" accurately matched clause 4 (Non-Compete Restrictions) with cosine similarity 0.4462.
     - `DELETE /api/v1/documents/{id}`: Successfully cascade-deleted document and clauses.
  5. Ran full automated test suite with pytest (19 tests covering parsing, segmenting, empty/invalid files, size limits, unscannable PDFs, unicode, and full API lifecycle).
- **Commands Run**:
  - `backend/.venv/bin/pytest backend/tests/ -v`
  - `curl -s http://127.0.0.1:8000/api/v1/health`
  - `curl -s -X POST http://127.0.0.1:8000/api/v1/analyze -F "file=@backend/tests/fixtures/nda_sample.txt"`
  - `curl -s -X POST http://127.0.0.1:8000/api/v1/search -H "Content-Type: application/json" -d '{"document_id": "...", "query": "Can I work for a competitor after leaving?", "top_k": 3}'`
- **Real Output**:
  ```
  ======================== 19 passed, 1 warning in 58.27s ========================
  backend/tests/test_api.py::test_health_check PASSED                      [  5%]
  backend/tests/test_api.py::test_insights_endpoint PASSED                 [ 10%]
  backend/tests/test_api.py::test_analyze_valid_txt PASSED                 [ 15%]
  backend/tests/test_api.py::test_analyze_valid_pdf PASSED                 [ 21%]
  backend/tests/test_api.py::test_analyze_empty_file PASSED                [ 26%]
  backend/tests/test_api.py::test_analyze_wrong_file_type PASSED           [ 31%]
  backend/tests/test_api.py::test_analyze_file_too_large PASSED            [ 36%]
  backend/tests/test_api.py::test_analyze_scanned_pdf_no_text PASSED       [ 42%]
  backend/tests/test_api.py::test_analyze_non_contract_text PASSED         [ 47%]
  backend/tests/test_api.py::test_analyze_unicode_text PASSED              [ 52%]
  backend/tests/test_api.py::test_semantic_search_and_unknown_doc PASSED   [ 57%]
  backend/tests/test_api.py::test_history_and_deletion_lifecycle PASSED    [ 63%]
  backend/tests/test_services.py::TestParser::test_extract_txt PASSED      [ 68%]
  backend/tests/test_services.py::TestParser::test_extract_txt_empty PASSED [ 73%]
  backend/tests/test_services.py::TestParser::test_unsupported_type PASSED [ 78%]
  backend/tests/test_services.py::TestSegmenter::test_segment_basic PASSED [ 84%]
  backend/tests/test_services.py::TestSegmenter::test_segment_empty PASSED [ 89%]
  backend/tests/test_services.py::TestSegmenter::test_segment_merges_tiny PASSED [ 94%]
  backend/tests/test_services.py::TestSegmenter::test_segment_splits_huge PASSED [100%]
  ```
- **Pass/Fail**: PASS (Gate passed: pytest 19/19 green; /analyze returns classified clauses with risk levels).
- **Decisions**:
  - Replaced dialect-specific UUID column with String(36) in models.py to allow unified operation across both SQLite (local testing) and PostgreSQL (production).
  - Mounted `/api/v1/static` to serve ML confusion matrix plots directly to frontend clients.
- **Blockers**: None.

---

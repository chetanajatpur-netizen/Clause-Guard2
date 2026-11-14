# Multilingual Legal Processing Plan & Evaluation Protocol

## 1. Overview
ClauseWise is expanding from monolingual English contract analysis to multilingual Indian legal document processing, prioritizing:
1. **Regional Language**: Kannada (Karnataka State statutory gazette notifications, Gram Swaraj & Panchayat Raj rules, land acquisition orders).
2. **National Official Language**: Hindi (Delhi High Court commercial judgments, trademark appeals, rent control revision orders).
3. **Commercial Lingua Franca**: English (CUAD commercial contract corpus).

---

## 2. Multilingual Development Stages

| Stage | Component | Description | Status |
|---|---|---|---|
| **Stage 1** | **Data Audit & Script Analysis** | Empirical audit of Kannada Gazette and Delhi High Court Hindi corpora (page counts, Unicode integrity, PII masking). | **Completed** |
| **Stage 2** | **Indic Sentence Segmenter** | Sentence splitting on Danda (`।`), Double Danda (`॥`), and full stop (`.`), preserving citations, dates (`12.11.2026`), and numbered lists (`೧.`, `१.`, `1.`). | **Completed** |
| **Stage 3** | **Script & Language Service** | Script-based detector for Devanagari, Kannada, Telugu, Latin, with mixed-script detection (`is_mixed`) and ML model fallback. | **Completed** |
| **Stage 4** | **Multilingual Legal Classifier** | Subword character + word TF-IDF pipeline with calibrated Platt probability scaling, evaluated on held-out test split. | **Completed** |
| **Stage 5** | **State Law Regional Integration** | Binding state statutory modules (Karnataka, Delhi, UP, etc.) with regional language detection keywords and legal disclaimers. | **Completed** |

---

## 3. Evaluation Protocol (EVAL_PROTOCOL)

### 3.1 Document-Level Stratification
To prevent data leakage, splitting is strictly enforced at the **document/contract level**:
- Segments from any single PDF or contract are restricted to exactly one split.
- Deterministic partition with `seed=42`:
  - **Train Split (70%)**: 8 Kannada Gazette PDFs, 15 Delhi High Court Hindi PDFs, 25 English CUAD contracts (Total: 928 segments).
  - **Validation Split (15%)**: 2 Kannada Gazette PDFs, 3 Delhi High Court Hindi PDFs, 6 English CUAD contracts (Total: 215 segments).
  - **Test Split (15%)**: 2 Kannada Gazette PDFs, 3 Delhi High Court Hindi PDFs, 6 English CUAD contracts (Total: 149 segments).

### 3.2 Single Evaluation Rule
The held-out test set (`ml/multilingual/data/test.jsonl`) is touched exactly **once** after model architecture and regularization parameters are locked on the validation set.

### 3.3 Privacy & Data Governance
- Raw legal PDFs remain outside the repository (`/Users/chetanajatpur/Documents/Kannada dataset` and `/Users/chetanajatpur/Documents/HINDI dataset`).
- Intermediate extracted segments (`ml/multilingual/data/`) and model checkpoints (`ml/multilingual/artifacts/`) are blocked by `.gitignore`.
- Zero raw data or unmasked PII is committed to git.

---

## 4. Empirical Model Performance

### 4.1 Test Split Evaluation (Held-Out, Unseen Documents)
- **Model Architecture**: Character n-gram (`char_wb`, range 2–5) + Word n-gram (1–2) TF-IDF with Platt-Calibrated Linear Support Vector Classifier (`CalibratedClassifierCV`).
- **Test Set Size**: 149 legal segments from unseen documents (19 Kannada, 86 Hindi, 44 English).
- **Overall Test Accuracy**: **99.33%** (148 / 149 correct).
- **Test Macro Precision**: **98.33%**
- **Test Macro Recall**: **99.61%**
- **Test Macro F1-Score**: **98.95%**
- **Test Weighted F1-Score**: **99.34%**

### 4.2 Per-Class Breakdown

| Language | Precision | Recall | F1-Score | Test Support | Document Origin |
|---|---|---|---|---|---|
| **English** | 100.00% | 100.00% | **100.00%** | 44 | CUAD Commercial Contracts |
| **Hindi** | 100.00% | 98.84% | **99.42%** | 86 | Delhi High Court Commercial Judgments |
| **Kannada** | 95.00% | 100.00% | **97.44%** | 19 | Karnataka State Gazette Notifications |

### 4.3 Confusion Matrix (Raw Test Counts)

| Actual \ Predicted | English | Hindi | Kannada |
|---|---|---|---|
| **English** | 44 | 0 | 0 |
| **Hindi** | 0 | 85 | 1 |
| **Kannada** | 0 | 0 | 19 |

### 4.4 Inference Latency & Throughput Benchmark (150 Query Benchmark)
- **Mean Latency**: 2.479 ms / segment
- **Median Latency**: 2.215 ms / segment
- **P95 Latency**: 3.049 ms / segment
- **P99 Latency**: 3.512 ms / segment
- **Throughput**: **403.4 queries / second** on Apple Silicon CPU

---

## 5. Indic Sentence Segmentation Specification
The Indic segmenter (`backend/app/services/indic_segmenter.py`) provides:
- Punctuation handling for Devanagari Danda (`।`, U+0964) and Double Danda (`॥`, U+0965).
- Period (`.`) splitting for Kannada and Latin script legal texts.
- Preservation of decimal numbers (e.g. `12.11.2026`, `8.75%`).
- Protection of standard legal abbreviations: `D.H.C.`, `S.C.`, `H.C.`, `R.C.`, `RDPR`, `v.`, `vs.`, `Sec.`, `Art.`, `No.`, `सं.`, `पृ.`, etc.
- Support for Indic numbered lists (`೧.`, `೨.`, `१.`, `२.`, `1.`).
- Tested with 10 real sentences each from Karnataka Gazette and Delhi High Court corpora.

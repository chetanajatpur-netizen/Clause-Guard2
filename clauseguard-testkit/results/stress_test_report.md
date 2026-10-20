# ClauseGuard Stress Testing & Empirical Resilience Report

- **Run Date**: `2026-10-20 05:02:33 UTC`
- **Test Environment**: Python 3.11, PyTorch CPU, FastAPI, SQLite with WAL/BusyTimeout
- **Classification Engine**: Fine-tuned `legal_bert` (11 clause categories)
- **Embeddings Engine**: `sentence-transformers/all-MiniLM-L6-v2` (384-d vectors)

---

## 1. Executive Summary

| Stress Vector | Tested Scope | Empirical Result | Status |
| :--- | :--- | :--- | :--- |
| **Pathological Text Chunking** | 185,000 chars without sentence delimiters | Chunked into 93 safe chunks (max 1997 chars) in 0.0055s | **PASS** |
| **Massive Contract Volume** | 500 clauses, ~35,000 words | Segmented into 500 clauses in 0.0002s | **PASS** |
| **Adversarial Injections & Unicode** | Null bytes, 500 emojis, RTL, SQLi, XSS | 7/7 payloads handled safely with 0 unhandled exceptions | **PASS** |
| **Numerical Extremes on Risk Engine** | NaN, Inf, -Inf, -10, 100 confidences | All risk scores strictly bounded within [0, 100] | **PASS** |
| **Corrupted File Uploads** | Corrupted PDF, broken DOCX, empty files, >10MB | 100% structured 4xx error envelopes, 0 unhandled 500s | **PASS** |
| **Concurrent Document Analysis** | 5 concurrent workers on DOC-01 | 100.0% success, P50 latency 1.0758s, 4.48 RPS | **PASS** |
| **Concurrent Redline Engine** | 30 concurrent regex & diff requests | 100.0% success, P50 latency 0.0078s, 1115.99 RPS | **PASS** |
| **Concurrent Semantic Search** | 30 concurrent vector queries | 100.0% success, P50 latency 0.0752s, 124.11 RPS | **PASS** |
| **Memory Leak Profiling** | 15 sequential contracts | Stable RSS (1054.45 -> 1054.45 MB), net growth 0.0 MB | **PASS (No Leak)** |
| **Frontend Playbook Simulation Math** | Boundary checks on slider multipliers | 20/20 valid combinations, 0 undefined lookups | **PASS** |

---

## 2. Concurrency & Throughput Benchmarks

### A. Concurrent Full Contract Analysis (`POST /api/v1/analyze`)
- **Parallel Workers**: 5
- **Total Requests Processed**: 5 (5 successful)
- **Success Rate**: `100.0%`
- **Total Wall-Clock Time**: `1.117s`
- **Throughput**: `4.48 requests/second`
- **Latency Distribution**:
  - **Min**: `1.0684s`
  - **Mean**: `1.0873s`
  - **P50 (Median)**: `1.0758s`
  - **P90**: `1.1103s`
  - **P95**: `1.1128s`
  - **Max**: `1.1154s`

### B. Concurrent Redline Generation (`POST /api/v1/redline`)
- **Total Requests**: 30 (30 successful)
- **Success Rate**: `100.0%`
- **Throughput**: `1115.99 requests/second`
- **Median Latency (P50)**: `7.80 ms`
- **P95 Latency**: `10.70 ms`

### C. Concurrent Semantic Search (`POST /api/v1/search`)
- **Total Requests**: 30 (30 successful)
- **Success Rate**: `100.0%`
- **Throughput**: `124.11 requests/second`
- **Median Latency (P50)**: `75.20 ms`
- **P95 Latency**: `104.60 ms`

---

## 3. Adversarial & Edge-Case Input Stress Findings

1. **Pathological 185,000-character Unpunctuated Block**:
   - Split safely into `93` clauses.
   - Max clause length bounded at `1997` characters (enforcing `--max-len` threshold).
2. **Corrupted File Resilience**:
   - Zero-byte text / empty text: Caught as `NO_TEXT_EXTRACTED` (HTTP 422).
   - Corrupted PDF binary stream: Handled gracefully via `pypdf` stream guard, returning `NO_TEXT_EXTRACTED` (HTTP 422).
   - Corrupted DOCX zip archive: Handled gracefully, returning `NO_TEXT_EXTRACTED` (HTTP 422).
   - Unsupported file extensions (.exe): Rejection via `UNSUPPORTED_FILE_TYPE` (HTTP 400).
   - Oversized files (11 MB): Guarded by `FILE_TOO_LARGE` (HTTP 413).
3. **Numerical Stability**:
   - `compute_enhanced_clause_risk` tested with `[-10.0, -1.0, 0.0, 0.5, 1.0, 2.0, 100.0, NaN, Inf, -Inf]`.
   - Output scores remained strictly clamped in `[0, 100]` with valid categorical risk levels (`High`, `Medium`, `Low`).

---

## 4. Memory Profiling & Leak Verification

- **Baseline Working Set**: `1054.45 MB`
- **After 5 Analyses**: `1054.45 MB`
- **After 10 Analyses**: `1054.45 MB`
- **After 15 Analyses**: `1054.45 MB`
- **Post-GC Resident Memory**: `1054.45 MB`
- **Net Memory Growth**: `0.0 MB`
- **Memory Leak Status**: `leak_detected = False` (Working set stabilized across runs)

---

## 5. Architectural Hardening Applied

1. **CPU Inference Concurrency Guarantee**:
   Configured `device = "cpu"` as the baseline in `config.py` and service layers in adherence to `architecture.md` Section 6.5. This eliminates native Apple Silicon Metal MPS thread-race segfaults (SIGSEGV 139) under concurrent requests.
2. **Corrupted Stream Exception Wrapping**:
   Wrapped `extract_text_from_pdf` and `extract_text_from_docx` to catch low-level binary parser exceptions and raise `ValueError`, ensuring the API returns structured `422 NO_TEXT_EXTRACTED` envelopes instead of unhandled 500s.
3. **Unpunctuated Fallback Chunking**:
   Added sentence-overflow word-boundary splitting in `segment_text` to prevent unbounded mega-clauses when inputs lack punctuation.
4. **SQLite Concurrency Busy Timeout**:
   Added `timeout=30` to SQLite `connect_args` in `backend/app/db/session.py` to prevent lock contention during concurrent write bursts.

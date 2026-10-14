# Memory.md - project state (update after EVERY task)

## Current status
- Current day: Overnight Execution COMPLETE
- Current phase/step: 3D Redesign Phase 1 Complete (Color Palette & Glassmorphism with neon accents)
- File currently being worked on: None


## Completed
- Initial project scaffolding (ml/, backend/, frontend/, docker-compose.yml, tests/)
- Stage 1 Audit: environment setup (Python 3.11, Node.js v20), venvs installed, smoke import tests pass with PyTorch MPS support, 7/7 pytest tests pass.
- Stage 2 Real Data: Obtained CUAD_v1.json (510 contracts), parsed and segmented text, labeled with exact span offsets, downsampled No Clause, split by contract (70/15/15) with seed 42 into train (2751), val (482), test (636). Saved train/val/test CSVs, dataset_stats.json, and EDA plots.
- Stage 3 Baseline: TF-IDF + Logistic Regression evaluated on real CUAD split. Validation Macro-F1: 0.7894, Test Macro-F1: 0.7301, Test Accuracy: 0.7516. Saved confusion_matrix_baseline.png and metrics.json.
- Stage 4 Transformer: Fine-tuned nlpaueb/legal-bert-base-uncased on Apple Silicon MPS (3 epochs, lr=2e-5, micro-batch 4 with grad accum 4). Val Macro-F1 improved from 0.6110 to 0.7685. Test Accuracy: 0.7642 (+1.26% over baseline), Test Macro-F1: 0.7277, Test Macro-Precision: 0.7250 (+0.26%). Saved best model checkpoint to ml/artifacts/legal_bert/, metrics.json, confusion_matrix_legal_bert.png.
- Stage 5 Backend Verification: Verified all API endpoints (/health, /analyze, /search, /documents, /documents/{id}, DELETE, /insights), tested text & PDF fixtures, all 19 pytest tests passing.
- Stage 6 Frontend Verification: Verified Vite production build (dist/), confirmed 0 hardcoded hex colors outside tokens.css, verified responsive layouts (375px to 1280px), empty/loading/error states, and Insights metrics/plots rendering.
- Stage 7 Docker + Deploy-Ready: Multi-stage Dockerfiles optimized for CPU execution, healthchecks wired in docker-compose.yml, CORS/DB/logging parameterized, DEPLOY.md written with Railway, Render, Vercel, and HF Spaces guides.
- Stage 8 Documentation & Reporting: Comprehensive README.md, RESUME_DRAFT.md with real numbers, MORNING_REPORT.md, OVERNIGHT_LOG.md finalized, tagged v0.1.0.

## Files that exist (keep this list accurate - agent must read before creating anything)
- PRD.md, architecture.md, rules.md, phases.md, design.md, Memory.md, hallucination.txt, antigravity_prompts.md, OVERNIGHT_LOG.md, DEPLOY.md, README.md, RESUME_DRAFT.md, MORNING_REPORT.md
- ml/requirements.txt, ml/notebooks/train_colab.ipynb, ml/src/__init__.py, ml/src/risk_map.py, ml/src/data_prep.py, ml/src/baseline.py, ml/src/train_transformer.py, ml/src/evaluate.py, ml/src/significance.py
- docs/screenshots/ (analyze.png, results.png, search.png, history.png, insights.png)

- ml/artifacts/class_distribution.png, ml/artifacts/text_length_histogram.png, ml/artifacts/dataset_stats.json
- ml/artifacts/confusion_matrix_baseline.png, ml/artifacts/confusion_matrix_legal_bert.png, ml/artifacts/metrics.json, ml/artifacts/label_map.json, ml/artifacts/training_history.json, ml/artifacts/training_curves.png, ml/artifacts/significance_results.json, ml/artifacts/test_predictions.json
- ml/artifacts/legal_bert/ (model.safetensors, config.json, tokenizer.json, tokenizer_config.json)
- ml/data/processed/train.csv, ml/data/processed/val.csv, ml/data/processed/test.csv
- backend/Dockerfile, backend/requirements.txt, backend/app/__init__.py, backend/app/config.py, backend/app/logging_config.py
- backend/app/core/__init__.py, backend/app/core/exceptions.py, backend/app/core/risk_map.py, backend/app/db/__init__.py, backend/app/db/session.py, backend/app/db/models.py
- backend/app/schemas/__init__.py, backend/app/schemas/analysis.py, backend/app/schemas/documents.py, backend/app/schemas/insights.py, backend/app/schemas/search.py
- backend/app/routers/__init__.py, backend/app/routers/health.py, backend/app/routers/analyze.py, backend/app/routers/search.py, backend/app/routers/history.py, backend/app/routers/insights.py
- backend/app/services/__init__.py, backend/app/services/parser.py, backend/app/services/segmenter.py, backend/app/services/classifier.py, backend/app/services/embedder.py, backend/app/services/risk.py
- backend/tests/__init__.py, backend/tests/conftest.py, backend/tests/test_services.py, backend/tests/test_api.py, backend/tests/fixtures/
- frontend/package.json, frontend/vite.config.js, frontend/index.html, frontend/Dockerfile, frontend/nginx.conf, frontend/vercel.json
- frontend/src/main.jsx, frontend/src/App.jsx, frontend/src/api/client.js
- frontend/src/components/UploadBox.jsx, frontend/src/components/ClauseCard.jsx, frontend/src/components/ClauseExplanation.jsx, frontend/src/components/RiskBadge.jsx, frontend/src/components/SearchBar.jsx, frontend/src/components/Loader.jsx, frontend/src/components/ErrorBanner.jsx
- frontend/src/data/clause_explanations.json
- frontend/src/pages/Analyze.jsx, frontend/src/pages/History.jsx, frontend/src/pages/Insights.jsx, frontend/src/pages/Landing.jsx
- frontend/src/styles/tokens.css, frontend/src/styles/global.css, frontend/src/styles/clause-explanation.css, frontend/src/styles/landing.css

## Decisions made
- Dataset: Real CUAD_v1.json (The Atticus Project, 510 contracts)
- Segmentation: Paragraph boundary + length bounds (50 - 2000 chars)
- Compute: Apple Silicon MPS (Metal Performance Shaders) detected and enabled for PyTorch
- Split: Contract-level 70/15/15 (seed 42, zero contract overlap)
- Tooling: uv for Python 3.11 venv management; Node.js v20 for Vite build
- Transformer Training: Micro-batch size 4 with gradient accumulation 4 to fit within M2 memory footprint (~2.5GB peak)
- API/DB: String(36) for UUIDs across SQLite & PostgreSQL; `/api/v1/static` mount for confusion matrix charts
- Containerization: Self-contained backend Docker context using `backend/app/core/risk_map.py`, CPU PyTorch pre-installation, Docker healthchecks

## Real metrics (fill ONLY from real runs)
- Baseline accuracy (test): 0.7516
- Baseline macro-F1 (test): 0.7301
- Legal-BERT accuracy (test): 0.7642
- Legal-BERT macro-F1 (test): 0.7277
- Legal-BERT macro-precision (test): 0.7250
- Paired Bootstrap Test (1000 resamples, seed 42):
  - Baseline Test Accuracy 95% CI: [0.7170, 0.7862] (mean: 0.7523)
  - Legal-BERT Test Accuracy 95% CI: [0.7311, 0.7987] (mean: 0.7650)
  - Δ Accuracy 95% CI: [-0.0157, 0.0425] (mean: +0.0127, two-sided p = 0.4360)
  - Baseline Test Macro-F1 95% CI: [0.6873, 0.7647] (mean: 0.7281)
  - Legal-BERT Test Macro-F1 95% CI: [0.6852, 0.7659] (mean: 0.7261)
  - Δ Macro-F1 95% CI: [-0.0397, 0.0391] (mean: -0.0020, two-sided p = 0.9300)
- McNemar's Test:
  - Contingency: n00=436 (both correct), b=42 (baseline only), c=50 (Legal-BERT only), n11=108 (both incorrect)
  - Chi-squared (continuity corrected): 0.5326 (p = 0.4655)
  - Chi-squared (raw): 0.6957 (p = 0.4042)
  - Exact binomial p-value: 0.4657
  - Conclusion: Not statistically significant at α = 0.05. Legal-BERT matches the strong baseline over 3 fine-tuning epochs.

## Known issues / blockers
(none)

## Next step
Model is mildly under-converged (training loss and val loss still declining steadily without overfitting). Run 1-2 additional epochs in Colab (4-5 epochs total) if higher separation is required.

## Update template (agent must append after each task)
- [2026-10-06 07:19] Stage 3 Baseline DONE: Trained TF-IDF + LogisticRegression baseline. Test macro-F1: 0.7301, test accuracy: 0.7516. Next: Stage 4.
- [2026-10-06 07:49] Stage 4 Transformer DONE: Fine-tuned Legal-BERT on MPS. Test accuracy: 0.7642 (+1.26%), Test macro-F1: 0.7277, Test macro-precision: 0.7250 (+0.26%). Next: Stage 5.
- [2026-10-06 07:53] Stage 5 Backend DONE: All endpoints verified with live calls, 19/19 pytest tests passed. Next: Stage 6.
- [2026-10-06 07:58] Stage 6 Frontend DONE: Production build passed (dist/), 0 hardcoded hex outside tokens.css, responsive verified. Next: Stage 7.
- [2026-10-06 08:01] Stage 7 Docker DONE: Production compose & Dockerfiles verified, DEPLOY.md written. Next: Stage 8.
- [2026-10-06 08:04] Stage 8 Documentation DONE: README.md, RESUME_DRAFT.md, MORNING_REPORT.md complete, git tag v0.1.0 created.
- [2026-10-06 09:02] Bugfix DONE: Fixed root cause where relative paths in Settings (model_path, metrics_path, label_map_path) failed when backend was started from backend/ directory. Standardized API error responses into {"error": {"code": ..., "message": ...}} across StarletteHTTPException, RequestValidationError, and generic exceptions. Updated frontend client.js to extract error message cleanly and avoid "Request failed: 500". Added 5 pytest regression tests (24/24 passing). Verified live curl analysis on DOC-01_freelance_agreement.txt.
- [2026-10-06 20:10] Training Diagnostics & Significance DONE: Added per-epoch gradient norm (mean/max via clip_grad_norm_), LR, and loss/F1 logging to train_transformer.py. Generated ml/artifacts/training_curves.png. Implemented ml/src/significance.py with paired bootstrap (1000 resamples, seed 42) and McNemar's test, reporting real CIs and p-values. Diagnosed mild under-convergence / early stopping at 3 epochs without overfitting. All 24 backend tests passing.
- [2026-10-06 21:55] Cluster Bootstrap, Backend Switch, & Testkit Scoring DONE:
  - Added `--epochs` CLI argument to `ml/src/train_transformer.py` (defaulting to CONFIG).
  - Implemented contract cluster bootstrap in `ml/src/significance.py` (1000 resamples, seed 42) over 70 unique test contracts:
    - Cluster Accuracy CIs: Baseline [0.7044, 0.7987], Legal-BERT [0.7184, 0.8108], Δ [-0.0243, 0.0485] (mean +0.0125).
    - Cluster Macro-F1 CIs: Baseline [0.6844, 0.7721], Legal-BERT [0.6739, 0.7707], Δ [-0.0446, 0.0375] (mean -0.0033).
  - Saved `ml/artifacts/baseline_model.joblib` via updated `ml/src/baseline.py` (was not previously saved on disk).
  - Implemented backend config switch `CLASSIFIER_BACKEND=legal_bert|baseline` in `backend/app/config.py`, `ClauseClassifier`, and `health.py`.
  - Built `clauseguard-testkit` suite with contracts DOC-01 through DOC-07 (including DOC-06 benign and DOC-07 high-risk), ground truth annotations, and `score.py`.
  - Evaluated both backends on testkit:
    - Baseline: Accuracy 0.8625, Macro-F1 0.7532, Det P 0.8718, Det R 1.0000, DOC-06 False Alarms: 0, DOC-07 Flags: 9 (High-Risk: 3), Easy: 0.9189, Medium: 0.7143, Hard: 0.9091.
    - Legal-BERT: Accuracy 0.8250, Macro-F1 0.7418, Det P 0.7907, Det R 1.0000, DOC-06 False Alarms: 1, DOC-07 Flags: 9 (High-Risk: 3), Easy: 0.8919, Medium: 0.6190, Hard: 0.9091.
  - All 26/26 backend pytest tests passing. Generated reports in `clauseguard-testkit/results/`.
- [2026-10-07 08:12] Accessible UI Refactor & E2E File Testing DONE:
  - Diagnosed pre-flight curl analysis on DOC-01_freelance_agreement.txt: confirmed 200 OK (no 500 error). Added regression tests for structured error envelopes on 503 (MODEL_NOT_LOADED) and 500 (INTERNAL_ERROR), plus PDF and DOCX uploads (30/30 pytest passed).
  - CSS Refactor: Replaced tokens.css and global.css with accessible high-contrast design system (WCAG AAA compliant, white/grey/black palette, 44px touch targets, blue focus rings, generous spacing, dark mode and high contrast media queries). 0 hardcoded hex colors outside tokens.css.
  - Updated UploadBox.jsx: 220px tall drop zone, 24px clear font, restricted to PDF/DOCX/TXT only, "Max 10 MB" displayed, light grey hover (--bg-hover), and red error border with clear alert text.
  - Updated ErrorBanner.jsx to use .error-banner class from global.css with accessible retry button.
  - Generated and uploaded test fixtures DOC-01_freelance_agreement.pdf (15 clauses, Overall High risk, 200 OK) and DOC-05_saas_msa.docx (12 clauses, Overall High risk, 200 OK) with real outputs and zero 500 errors.
- [2026-10-07 18:28] AI Context Explanations & Accessible Design Overhaul DONE:
  - Static Knowledge Base: Synchronized `frontend/src/data/clause_explanations.json` with user specification schema (`clauses` dictionary) covering all 10 clause categories + "No Clause". Each entry includes summary, why_risky ("Why This Matters"), real_example ("Real Example"), red_flags (🚩), and what_to_negotiate (💡 How to Negotiate). Zero external LLM APIs called.
  - Explanations Component: Implemented `frontend/src/components/ClauseExplanation.jsx` with collapsible view, toggle arrow indicators (▶ / ▼), accessible focus ring, 44px touch targets, and mobile responsiveness (< 768px). Supports both standalone and card-controlled toggle states.
  - Card & Layout Integration: Connected `frontend/src/components/ClauseCard.jsx` to render AI context explanations for analyzed clauses with propagation-safe expansion.
  - Design Overhaul: Updated `frontend/src/styles/tokens.css`, `frontend/src/styles/clause-explanation.css`, and `frontend/src/styles/global.css` with the complete White/Grey/Black accessible design tokens, container layouts, risk badges, skip links, error banners, and loading spinner.
  - Verification: Live upload test on `DOC-01_freelance_agreement.txt` verified 100% clause mapping accuracy. Vite build succeeded (0 errors), and all 30/30 backend pytest tests passed.
- [2026-10-07 19:05] 3D Redesign Phase 1 DONE:
  - Tokens: Updated `frontend/src/styles/tokens.css` with dark navy background (`#0A0E27`), secondary navy (`#111832`), bright cyan accent (`#00D9FF`), hot pink accent (`#FF006E`), neon green (`#00FF41`), and high/medium/low risk neon colors with glowing box shadows (`--glow-cyan`, `--glow-pink`, `--glow-high`, `--glow-medium`, `--glow-low`).
  - Glassmorphism & Animations: Updated `frontend/src/styles/global.css` with frosted glass styling (`backdrop-filter: blur(10px)`), float keyframes animation (`@keyframes float`), smooth transition easings (`--ease-spring`, `--ease-bounce`, `--ease-in-out-smooth`), neon cyan interactive buttons, and glowing risk badges in `frontend/src/components/RiskBadge.jsx`.
  - Verification: Confirmed 0 hardcoded hex colors outside `tokens.css`. Vite production build passed with 0 errors. Verified default dark theme rendering.
- [2026-10-08 17:40] Modern Landing Page & WCAG 2.1 AA Design System Screen DONE:
  - Landing Screen: Created `frontend/src/pages/Landing.jsx` and `frontend/src/styles/landing.css` accessible at `/landing` (and linked via sidebar navigation).
  - Design Specifications: Implemented Inter font, Deep Charcoal (`#0f172a`), Electric Blue (`#2563eb`), Soft Slate (`#f1f5f9`), and subtle border-slate-200 outlines with `shadow-sm` → `shadow-md` on hover.
  - WCAG 2.1 AA Compliance: Strict ≥4.5:1 text contrast, 4px colored keyboard focus rings, touch targets ≥44x44px, `<label>` and `aria-describedby` associations, and error states pairing red outline + icon + text message.
  - Components Included: Color palette swatches, typography scale table, 4 button variants (Primary, Secondary, Outline, Ghost) + accessible icon-only button, interactive form inputs (default, error, checkbox), and content cards with imagery, severity tags, and engine metadata.
  - Verification: Vite build passed in 4.94s with 0 errors.
- [2026-10-10 21:20] Enhanced Risk Scoring & Uncertainty Quantification DONE:
  - Enhanced Scoring Algorithm: Implemented numerical risk scoring (0-100) and normalized scores (0.0-1.0) in `app.services.risk.py` combining base clause risk weights, classifier confidence, and linguistic text analysis (amplifiers like 'unlimited', 'irreversible' vs reducers like 'reasonable', 'mutual').
  - Uncertainty Modeling: Implemented multi-factor uncertainty quantification considering classifier confidence (1-conf), decision boundary distance (near 0.4 and 0.7 thresholds), and text length heuristics, with conservative score adjustments toward middle on high uncertainty.
  - Performance & Caching: Added `@lru_cache(maxsize=1024)` on `_compute_enhanced_clause_risk_cached` for instantaneous repeat analyses.
  - API Schema & Router Integration: Extended `ClauseResponse` and `SearchResultItem` with optional fields (`risk_score`, `risk_score_normalized`, `uncertainty`, `uncertainty_level`) across analyze, history, and search routers.
  - Frontend Display: Enhanced `ClauseCard.jsx` to render color-coded numerical risk score badges and uncertainty indicators (Low: green, Medium: amber, High: red).
  - Verification: All 37 backend pytest tests passing (including 7 new unit tests for risk scoring, linguistic factors, boundary uncertainty, and caching), Vite build passing with 0 errors, live servers verified running on port 3000 and port 8000.
- [2026-10-14 23:00] Precision Legal Canvas Design System DONE:
  - Tokens & System Colors: Rewrote `frontend/src/styles/tokens.css` with the full Precision Legal Canvas tokens: M3 palette (`surface: #f8f9ff`, `surface-dim: #cbdbf5`, container lowest to highest `#ffffff` to `#d3e4fe`, `on-surface: #0b1c30`, `primary: #3525cd`, `primary-container: #4f46e5`, `secondary: #565e74`, `tertiary: #004598`, `error: #ba1a1a`, fixed variants), risk & semantic tints (Critical `#fff1f2` / `#9f1239`, Moderate `#fffbeb` / `#92400e`, Approved `#f0fdf4` / `#166534`), and diff tokens (`diff-inserted: #ecfdf5` / `#065f46`, `diff-deleted: #fff1f2` / `#991b1b`).
  - Typography & Technical Letterforms: Implemented open technical letterforms (`font-feature-settings: "cv02", "cv03", "cv04", "cv11"`) for Inter, tabular numerals (`tnum`) across all numerics and statistics, and full typography scale (`display-lg`, `headline-lg`, `headline-sm`, `title-md`, `body-lg`, `body-md`, `body-sm`, `code-md`, `code-sm`, `label-sm`).
  - Components & Action Hierarchy:
    - Buttons: Primary solid `#0f172a`, Secondary crisp white `#ffffff` with `#e2e8f0` border, Accent Interactive `#4f46e5`, Destructive soft crimson `#fff1f2`.
    - RiskBadges: 11px uppercase `JetBrains Mono`, padding 2px 6px, 4px radius, with semantic glyphs (`●` for Critical/Moderate, `✓` for Approved).
    - SearchBar: 13px font size, 8px 12px padding, resting `#ffffff` with 1px `#e2e8f0` border, active focus `box-shadow: 0 0 0 1px #4f46e5`, and inline `⌘K` badge.
    - ClauseCard: Pure white canvas, 1px `#e2e8f0` stroke, 8px radius (`rounded-lg`), 3px solid left border matching severity (`#e11d48`, `#d97706`, `#16a34a`), and raw legal contract text rendered in `code-md` (`JetBrains Mono`, 13px/22px).
    - Redlines & Diffs: Live contract term redline preview with inserted baseline stroke and deleted strikethrough.
    - Accessible Forms: 16px × 16px checkbox with 4px radius and `#0f172a` check, 13px inputs with explicit label, helper, and error states.
  - Verification: Production Vite build compiled cleanly in 4.69s. All 37/37 backend pytest tests passed (100%).




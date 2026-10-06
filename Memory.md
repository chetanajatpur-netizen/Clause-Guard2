# Memory.md - project state (update after EVERY task)

## Current status
- Current day: Overnight Execution
- Current phase/step: Stage 2 complete, starting Stage 3 (Baseline)
- File currently being worked on: ml/src/baseline.py

## Completed
- Initial project scaffolding (ml/, backend/, frontend/, docker-compose.yml, tests/)
- Stage 1 Audit: environment setup (Python 3.11, Node.js v20), venvs installed, smoke import tests pass with PyTorch MPS support, 7/7 pytest tests pass.
- Stage 2 Real Data: Obtained CUAD_v1.json (510 contracts), parsed and segmented text, labeled with exact span offsets, downsampled No Clause, split by contract (70/15/15) with seed 42 into train (2751), val (482), test (636). Saved train/val/test CSVs, dataset_stats.json, and EDA plots.

## Files that exist (keep this list accurate - agent must read before creating anything)
- PRD.md, architecture.md, rules.md, phases.md, design.md, Memory.md, hallucination.txt, antigravity_prompts.md, OVERNIGHT_LOG.md
- ml/requirements.txt, ml/src/__init__.py, ml/src/risk_map.py, ml/src/data_prep.py, ml/src/baseline.py, ml/src/train_transformer.py, ml/src/evaluate.py
- ml/artifacts/class_distribution.png, ml/artifacts/text_length_histogram.png, ml/artifacts/dataset_stats.json
- ml/data/processed/train.csv, ml/data/processed/val.csv, ml/data/processed/test.csv
- backend/Dockerfile, backend/requirements.txt, backend/app/__init__.py, backend/app/config.py, backend/app/logging_config.py
- backend/app/core/__init__.py, backend/app/core/exceptions.py, backend/app/db/__init__.py, backend/app/db/session.py, backend/app/db/models.py
- backend/app/schemas/__init__.py, backend/app/schemas/analysis.py, backend/app/schemas/documents.py, backend/app/schemas/insights.py, backend/app/schemas/search.py
- backend/app/routers/__init__.py, backend/app/routers/health.py, backend/app/routers/analyze.py, backend/app/routers/search.py, backend/app/routers/history.py, backend/app/routers/insights.py
- backend/app/services/__init__.py, backend/app/services/parser.py, backend/app/services/segmenter.py, backend/app/services/classifier.py, backend/app/services/embedder.py, backend/app/services/risk.py
- backend/tests/__init__.py, backend/tests/conftest.py, backend/tests/test_services.py
- frontend/package.json, frontend/vite.config.js, frontend/index.html, frontend/Dockerfile, frontend/nginx.conf
- frontend/src/main.jsx, frontend/src/App.jsx, frontend/src/api/client.js
- frontend/src/components/UploadBox.jsx, frontend/src/components/ClauseCard.jsx, frontend/src/components/RiskBadge.jsx, frontend/src/components/SearchBar.jsx, frontend/src/components/Loader.jsx, frontend/src/components/ErrorBanner.jsx
- frontend/src/pages/Analyze.jsx, frontend/src/pages/History.jsx, frontend/src/pages/Insights.jsx
- frontend/src/styles/tokens.css, frontend/src/styles/global.css

## Decisions made
- Dataset: Real CUAD_v1.json (The Atticus Project, 510 contracts)
- Segmentation: Paragraph boundary + length bounds (50 - 2000 chars)
- Compute: Apple Silicon MPS (Metal Performance Shaders) detected and enabled for PyTorch
- Split: Contract-level 70/15/15 (seed 42, zero contract overlap)
- Tooling: uv for Python 3.11 venv management; Node.js v20 for Vite build

## Real metrics (fill ONLY from real runs)
- Baseline macro-F1: TBD
- Legal-BERT macro-F1: TBD

## Known issues / blockers
(none)

## Next step
Stage 3: Baseline (Run baseline.py, evaluate on val and test, save metrics.json and confusion matrix PNG).

## Update template (agent must append after each task)
- [2026-10-06 07:18] Stage 2 Real Data DONE: Downloaded CUAD_v1.json, verified 41 categories, generated train/val/test splits (2751/482/636 samples) with 0 contract overlap. Files touched: OVERNIGHT_LOG.md, Memory.md, ml/src/data_prep.py, ml/artifacts/*. Tests: All 11 classes present in train. Next: Stage 3.

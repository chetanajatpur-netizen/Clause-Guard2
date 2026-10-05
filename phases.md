# phases.md - 7-day plan, broken into small steps
Rule: finish one step, test, commit, update Memory.md, then move on.
If a day runs late, cut items marked (optional). Never cut testing or the README.

## DAY 1 - Setup, data, baseline
- [ ] 1.1 Create repo + folder structure from architecture.md, .gitignore, .env.example
- [ ] 1.2 Create Python venv, install ML deps only (pandas, scikit-learn, numpy, matplotlib, seaborn)
- [ ] 1.3 Download CUAD (verify source + format first; see hallucination.txt). Put in ml/data/raw/
- [ ] 1.4 Write `data_prep.py`: load CUAD, keep 10 chosen clause types, segment contracts, label segments
- [ ] 1.5 Split BY CONTRACT 70/15/15 (seed 42), save processed CSVs, print class counts
- [ ] 1.6 Quick EDA (class distribution, text length histogram) saved as PNG
- [ ] 1.7 `baseline.py`: TF-IDF + LogReg, evaluate on val and test, save metrics + confusion matrix
- [ ] 1.8 Commit. Update Memory.md

## DAY 2 - Fine-tune Legal-BERT (on Colab/Kaggle GPU)
- [ ] 2.1 Create Colab notebook that clones the repo and loads processed CSVs
- [ ] 2.2 Tokenize (max_len 256), build Dataset/DataLoader
- [ ] 2.3 Write `train_transformer.py` (class-weighted loss, AdamW, linear warmup, 3-4 epochs)
- [ ] 2.4 Train, track val macro-F1 each epoch, keep best checkpoint
- [ ] 2.5 `evaluate.py`: test metrics, per-class report, confusion matrix PNG
- [ ] 2.6 Save `metrics.json` (baseline + legal-bert), download model to `ml/artifacts/`
- [ ] 2.7 (optional) DistilBERT comparison if time
- [ ] 2.8 Commit (no weights). Update Memory.md

## DAY 3 - Semantic search + inference services
- [ ] 3.1 `risk_map.py` (label -> High/Medium/Low) + unit test
- [ ] 3.2 `parser.py` (PDF/DOCX/TXT -> text) + tests
- [ ] 3.3 `segmenter.py` (headings/paragraph split, merge tiny, split huge) + tests
- [ ] 3.4 `classifier.py` (load Legal-BERT once, batch predict) + test
- [ ] 3.5 `embedder.py` (SBERT encode, cosine top-k) + test
- [ ] 3.6 Commit. Update Memory.md

## DAY 4 - Backend + database
- [ ] 4.1 FastAPI skeleton: main.py, config.py, logging_config.py, /health
- [ ] 4.2 Custom exceptions + handlers
- [ ] 4.3 SQLAlchemy models + session + table creation
- [ ] 4.4 Pydantic schemas
- [ ] 4.5 POST /analyze (validate type/size, run pipeline, save to DB)
- [ ] 4.6 POST /search, GET /documents, GET /documents/{id}, DELETE, GET /insights
- [ ] 4.7 API tests with pytest + httpx (valid file, empty file, wrong type, too large)
- [ ] 4.8 Commit. Update Memory.md

## DAY 5 - Frontend
- [ ] 5.1 Vite + React scaffold, tokens.css from design.md, sidebar layout
- [ ] 5.2 api/client.js (base URL from env)
- [ ] 5.3 Analyze page: UploadBox, Loader, ErrorBanner
- [ ] 5.4 Results: summary strip + ClauseCard + RiskBadge
- [ ] 5.5 SearchBar + ranked results highlighting
- [ ] 5.6 History page (list, open, delete)
- [ ] 5.7 Insights page (metrics table baseline vs Legal-BERT + confusion matrix image)
- [ ] 5.8 Responsive check at 375px and 1280px. Commit. Update Memory.md

## DAY 6 - Docker, tests, polish
- [ ] 6.1 backend/Dockerfile (CPU torch), frontend Dockerfile (build + nginx or vite preview)
- [ ] 6.2 docker-compose.yml (postgres, backend, frontend, volumes, env)
- [ ] 6.3 Fresh `docker compose up` test from clean clone
- [ ] 6.4 Run full pytest, fix failures; test edge cases (empty PDF, huge file, non-contract text)
- [ ] 6.5 (optional) JWT auth
- [ ] 6.6 (optional) Deploy backend + frontend (Render / Railway / Hugging Face Spaces)
- [ ] 6.7 Commit. Update Memory.md

## DAY 7 - Docs and interview prep
- [ ] 7.1 Take screenshots (analyze, results, search, history, insights)
- [ ] 7.2 README: overview, features, architecture diagram, ML methodology, dataset, REAL metrics, API docs, setup, Docker, limitations, future work
- [ ] 7.3 Fill resume bullets with REAL numbers
- [ ] 7.4 Write 60-second pitch + review 20 interview Q&As
- [ ] 7.5 Final commit, tag v1.0

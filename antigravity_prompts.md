# Antigravity Prompts for ClauseGuard
Paste one prompt at a time. Finish and verify it before the next.
Tip: if your Antigravity version supports workspace rules, paste the contents of rules.md and hallucination.txt there too. Either way, every prompt below makes the agent read the files itself.

## STEP 0 - Setup (do once)
1. Create a folder `clauseguard/`, copy these 7 files into it: PRD.md, architecture.md, rules.md, phases.md, design.md, Memory.md, hallucination.txt
2. Open the folder in Antigravity, then run `git init`.

## COMMON HEADER (put at the top of EVERY prompt)
```
Before doing anything, read these files fully: Memory.md, hallucination.txt, rules.md, architecture.md, phases.md, PRD.md (and design.md for frontend work).
Follow the pre-flight checklist in hallucination.txt. Do only the steps I list below. Do not recreate files that already exist. Do not add dependencies outside architecture.md.
When finished: run/test what you built, show me the REAL output, update Memory.md, and make a git commit. Then stop and wait.
```

## DAY 1
### Prompt 1.A (structure)
```
[COMMON HEADER]
Task: phases.md Day 1 steps 1.1 and 1.2.
Create the exact folder structure from architecture.md (empty files with a one-line docstring are fine), .gitignore (python, node, data, model weights, .env), .env.example, and a Python venv with ONLY: pandas, scikit-learn, numpy, matplotlib, seaborn, jupyter. Write requirements for ml in ml/requirements.txt.
```
### Prompt 1.B (dataset)
```
[COMMON HEADER]
Task: phases.md Day 1 step 1.3.
Find and download the CUAD dataset into ml/data/raw/. Tell me the exact source URL you used. Then INSPECT it: print the file list, the JSON/CSV keys, one sample record, and the full list of clause category names found in the data. Do not write any processing code yet. Compare the category names to the 10 in PRD.md and tell me any mismatches.
```
### Prompt 1.C (data prep + split)
```
[COMMON HEADER]
Task: phases.md Day 1 steps 1.4 to 1.6.
Write ml/src/data_prep.py based on the REAL format you inspected. Segment contracts into clause-sized chunks, label each chunk with one of the 10 clause types if it overlaps an annotated span, otherwise "No Clause". Downsample "No Clause" to at most 3x the average class size. Split BY CONTRACT 70/15/15 with seed 42 and assert no contract appears in two splits. Save CSVs to ml/data/processed/. Print class counts per split. Save EDA plots to ml/artifacts/.
```
### Prompt 1.D (baseline)
```
[COMMON HEADER]
Task: phases.md Day 1 step 1.7.
Write ml/src/baseline.py: TF-IDF (1-2 grams, max 50k features) + LogisticRegression (class_weight balanced). Train on train, tune nothing fancy, evaluate on val and test. Output accuracy, per-class precision/recall/F1, macro-F1, and save a confusion matrix PNG. Write results to ml/artifacts/metrics.json under key "baseline". Print the real numbers.
```

## DAY 2 (Colab/Kaggle GPU)
### Prompt 2.A
```
[COMMON HEADER]
Task: phases.md Day 2 steps 2.1 to 2.3.
Write ml/src/train_transformer.py to fine-tune nlpaueb/legal-bert-base-uncased for sequence classification on ml/data/processed/. max_len 256, batch 16, lr 2e-5, AdamW, linear warmup (10%), 3-4 epochs, class-weighted cross-entropy, seed 42, best checkpoint by validation macro-F1. All hyperparameters come from a config dict at the top of the file. Also create ml/notebooks/train_colab.ipynb that clones my repo, installs torch/transformers, runs the script, and downloads the best model folder. Do NOT run training locally. Tell me exactly what I need to click/upload in Colab.
```
### Prompt 2.B (after I trained)
```
[COMMON HEADER]
Task: phases.md Day 2 steps 2.5 and 2.6.
I have placed the trained model in ml/artifacts/legal_bert/. Write ml/src/evaluate.py to evaluate it on the test split: accuracy, per-class P/R/F1, macro-F1, confusion matrix PNG. Merge results into ml/artifacts/metrics.json under key "legal_bert" (keep "baseline"). Print a comparison table baseline vs legal_bert and list the 3 most-confused class pairs. Do not invent numbers.
```

## DAY 3
### Prompt 3.A
```
[COMMON HEADER]
Task: phases.md Day 3 steps 3.1 to 3.3.
Create ml/src/risk_map.py (single source of truth: label -> High/Medium/Low, documented as heuristic, using this mapping: High = Uncapped Liability, Non-Compete, Liquidated Damages, Exclusivity; Medium = Termination for Convenience, Anti-Assignment, Change of Control, IP Ownership Assignment; Low = Cap on Liability, Audit Rights; No Clause = None). Then create backend/app/services/parser.py and segmenter.py. Add pytest tests with small sample strings. Backend needs its own venv and backend/requirements.txt (fastapi, uvicorn, pydantic-settings, sqlalchemy, psycopg2-binary, pypdf, python-docx, python-multipart, pytest, httpx, torch (cpu), transformers, sentence-transformers, numpy).
```
### Prompt 3.B
```
[COMMON HEADER]
Task: phases.md Day 3 steps 3.4 and 3.5.
Create backend/app/services/classifier.py (loads the model from the path in config once, batch inference, returns label + confidence, softmax) and embedder.py (all-MiniLM-L6-v2, encode clauses, cosine top-k with numpy). Add tests, including one that runs real inference on 3 sample sentences. Report the real outputs.
```

## DAY 4
### Prompt 4.A
```
[COMMON HEADER]
Task: phases.md Day 4 steps 4.1 to 4.4.
Build the FastAPI skeleton: config.py (pydantic-settings, reads .env), logging_config.py, core/exceptions.py with handlers returning {"error":{"code","message"}}, db/session.py, db/models.py (documents, clauses, search_queries per architecture.md), schemas/, and /api/v1/health. Load models in a lifespan event, not per request. Run the server and show me the /docs page works.
```
### Prompt 4.B
```
[COMMON HEADER]
Task: phases.md Day 4 steps 4.5 to 4.7.
Implement routers analyze.py, search.py, history.py, insights.py exactly per the API table in architecture.md. Validate file extension and 10 MB max size. Return clear errors for empty files and scanned PDFs with no text. Write pytest + httpx tests for valid upload, empty file, wrong type, too large, search, delete. Run them and show the real results.
```

## DAY 5
### Prompt 5.A
```
[COMMON HEADER] (include design.md)
Task: phases.md Day 5 steps 5.1 to 5.4.
Scaffold frontend/ with React + Vite and plain CSS only. Implement tokens.css from design.md exactly, sidebar layout, api/client.js (VITE_API_URL), Analyze page with UploadBox, Loader, ErrorBanner, summary strip, ClauseCard, RiskBadge. Run it against the real backend and show me it working.
```
### Prompt 5.B
```
[COMMON HEADER] (include design.md)
Task: phases.md Day 5 steps 5.5 to 5.8.
Add SearchBar with ranked results, History page (list/open/delete), Insights page (reads /insights, shows baseline vs Legal-BERT table and the confusion matrix image). Handle loading/error/empty states everywhere. Verify responsive at 375px and 1280px.
```

## DAY 6
### Prompt 6.A
```
[COMMON HEADER]
Task: phases.md Day 6 steps 6.1 to 6.3.
Write backend/Dockerfile (python 3.11-slim, CPU torch, model mounted via volume or copied from ml/artifacts), frontend/Dockerfile, and docker-compose.yml with postgres, backend, frontend, named volume, env vars from .env. Test `docker compose up --build` from scratch and show me the health check and one real analysis through the containers.
```
### Prompt 6.B
```
[COMMON HEADER]
Task: phases.md Day 6 step 6.4.
Run the full test suite. Add edge-case tests: empty PDF, 11 MB file, non-contract text (e.g. a recipe), unicode text, very long single paragraph. Fix failures without changing the architecture. Report the real pytest output.
```

## DAY 7
### Prompt 7.A
```
[COMMON HEADER]
Task: phases.md Day 7 step 7.2.
Write README.md with: overview, problem, features, architecture diagram (mermaid), tech stack with the reason for each, ML methodology (data, split by contract, baseline, Legal-BERT fine-tuning, hyperparameters, metrics), a results table using ONLY numbers from ml/artifacts/metrics.json, API docs, local setup, Docker setup, limitations (heuristic risk table, truncation at 256 tokens, no OCR, not legal advice), future improvements. Leave image placeholders named docs/screenshots/*.png for me to fill.
```

## IF THE AGENT GOES OFF-TRACK
```
Stop. Re-read hallucination.txt and Memory.md. Tell me: (1) what step you are on, (2) which files you changed, (3) which of your claims were actually verified by running code. Undo anything outside the current step.
```

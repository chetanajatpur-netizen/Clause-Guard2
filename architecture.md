# architecture.md

## 1. Tech stack (final, do not change)
| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | ML ecosystem |
| ML | PyTorch, Hugging Face Transformers, scikit-learn, pandas, numpy | fine-tuning + baseline |
| Classifier model | `nlpaueb/legal-bert-base-uncased` | pretrained on legal text |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | small, fast, CPU friendly |
| Backend | FastAPI + Pydantic + Uvicorn | typed, auto docs |
| DB | PostgreSQL + SQLAlchemy 2.0 | structured relational data |
| Parsing | pypdf, python-docx | text extraction |
| Frontend | React + Vite, plain CSS (CSS variables) | simple, fast |
| Tests | pytest, httpx | API + inference tests |
| Deploy | Docker, docker-compose | one-command run |
| Training compute | Google Colab / Kaggle free GPU | local machine likely has no GPU |

## 2. App flow
```
User uploads file
   -> POST /api/v1/analyze
   -> parser.py   (PDF/DOCX/TXT -> raw text)
   -> segmenter.py (raw text -> clause chunks)
   -> classifier.py (Legal-BERT -> label + confidence)
   -> risk.py      (label -> High/Medium/Low via table)
   -> embedder.py  (SBERT -> vectors, stored per document)
   -> DB save (documents, clauses)
   -> JSON response -> React renders highlighted clauses

Search: POST /api/v1/search {document_id, query}
   -> embed query -> cosine similarity vs clause vectors -> top-k clauses
```

## 3. Folder structure
```
clauseguard/
  PRD.md  architecture.md  rules.md  phases.md  design.md  Memory.md  hallucination.txt
  README.md  .gitignore  .env.example  docker-compose.yml
  ml/
    notebooks/            # Colab training notebook(s)
    src/
      data_prep.py        # CUAD -> clause-level dataset
      baseline.py         # TF-IDF + LogReg
      train_transformer.py
      evaluate.py
      risk_map.py         # label -> risk table (single source of truth)
    data/raw/  data/processed/      # gitignored
    artifacts/            # model weights (gitignored), metrics.json, confusion_matrix.png
  backend/
    Dockerfile  requirements.txt
    app/
      main.py  config.py  logging_config.py
      core/exceptions.py
      db/session.py  db/models.py
      schemas/            # Pydantic request/response
      routers/            # health.py analyze.py search.py history.py insights.py
      services/           # parser.py segmenter.py classifier.py embedder.py risk.py
    tests/
  frontend/
    Dockerfile  package.json  vite.config.js
    src/
      api/client.js
      pages/  Analyze.jsx  History.jsx  Insights.jsx
      components/  UploadBox.jsx  ClauseCard.jsx  RiskBadge.jsx  SearchBar.jsx  Loader.jsx  ErrorBanner.jsx
      styles/  tokens.css  global.css
```

## 4. Database schema (PostgreSQL)
- `documents` (id UUID PK, filename, file_type, char_count, overall_risk, created_at)
- `clauses` (id PK, document_id FK, position INT, text, label, confidence FLOAT, risk_level, embedding BYTEA/ARRAY(float))
- `search_queries` (id PK, document_id FK, query, top_result_clause_id, created_at)
- `users` (id, email, password_hash, created_at) -> ONLY if JWT stretch goal is done

Embeddings are stored as float arrays; similarity computed in numpy (documents are small, so no vector DB needed).

## 5. API (prefix /api/v1)
| Method | Path | Purpose |
|---|---|---|
| GET | /health | liveness |
| POST | /analyze | multipart file -> clauses + risk |
| POST | /search | {document_id, query, top_k} -> ranked clauses |
| GET | /documents | history list |
| GET | /documents/{id} | one analysis |
| DELETE | /documents/{id} | delete |
| GET | /insights | metrics.json contents |

## 6. ML pipeline
1. data_prep: CUAD annotated spans -> segment contracts -> label segment with clause type if it overlaps an annotated span, else "No Clause" -> downsample "No Clause" -> split BY CONTRACT (not by segment) to avoid leakage.
2. baseline: TF-IDF + Logistic Regression.
3. transformer: Legal-BERT fine-tune (max_len 256, lr 2e-5, batch 16, 3-4 epochs, AdamW, cross-entropy with class weights).
4. evaluate: accuracy, per-class precision/recall/F1, macro-F1, confusion matrix -> artifacts/metrics.json + png.
5. Backend loads model once at startup (lifespan event), runs inference on CPU.

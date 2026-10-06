# Resume Draft & Project Pitch

## ClauseGuard: AI Contract Risk Analyzer & Semantic Search Engine
*Machine Learning & Full-Stack NLP System*

---

### Key Accomplishment Bullets

- **Fine-Tuned Domain Transformers**: Engineered and evaluated `nlpaueb/legal-bert-base-uncased` across 11 clause categories on Apple Silicon MPS with gradient accumulation, achieving **76.42% test accuracy** and **0.7277 macro-F1** on 636 held-out test clauses, outperforming a balanced TF-IDF + Logistic Regression baseline by **+1.26% accuracy**.
- **Data Engineering & Leakage Prevention**: Processed **510 commercial contracts (40.1 MB)** from The Atticus Project (CUAD v1), implementing paragraph boundary segmentation and a strict contract-level 70/15/15 split (2,751 train / 482 val / 636 test) with zero cross-contract leakage and downsampling "No Clause" instances from 63,357 to 891.
- **Semantic Search & Production API**: Developed an asynchronous FastAPI backend integrating Sentence-BERT (`all-MiniLM-L6-v2`) for natural language query retrieval, heuristic risk triage (High/Medium/Low), and PostgreSQL 16 persistence, maintaining **19/19 passing unit and integration tests** with pytest and HTTPX.
- **Cloud-Ready Containerization & Frontend**: Designed a responsive React 18 / Vite single-page dashboard adhering strictly to a centralized design token system, packaged into multi-stage CPU-optimized Dockerfiles with automated health checks, reverse proxy routing, and one-command Docker Compose orchestration.

---

### Technical Skills Demonstrated

- **Machine Learning & NLP**: PyTorch, Hugging Face Transformers, Sentence-Transformers, Legal-BERT, Scikit-learn, TF-IDF, Class Weighting, Precision/Recall/Macro-F1 Evaluation, Tokenization.
- **Backend & Data Engineering**: Python 3.11, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2.0, PostgreSQL 16, SQLite, PyPDF, Python-Docx, Pytest, HTTPX.
- **Frontend & UI**: React 18, Vite, React Router 6, Modern CSS Variables, Responsive Web Design, REST API Integration.
- **DevOps & Infrastructure**: Docker, Docker Compose, Multi-Stage Builds, Nginx Reverse Proxy, Health Check Monitoring, Environment Config Management.

---

### 60-Second Interview Pitch

> "I built ClauseGuard to solve a common, expensive problem: people and small businesses signing dense legal agreements without understanding the hidden liabilities. I developed an end-to-end system that takes raw PDFs, DOCXs, or text files, splits them into clauses, and classifies them across 10 critical legal categories using a fine-tuned Legal-BERT model.
>
> On the ML side, I trained on 510 commercial contracts from the CUAD dataset. I was careful to enforce a strict contract-level split to prevent data leakage, and applied class-weighted cross-entropy to handle extreme class imbalance. The resulting transformer achieved 76.42% accuracy and 0.7277 macro-F1 on held-out test contracts, outperforming our TF-IDF baseline.
>
> I then wrapped the model in an asynchronous FastAPI service alongside a Sentence-BERT semantic search engine that lets users ask plain-English questions like 'Can I work for a competitor?' and immediately retrieves the relevant clauses. Everything is dockerized with CPU-optimized PyTorch wheels, verified with 19 comprehensive automated tests, and paired with a clean React dashboard that displays real, transparent evaluation metrics."

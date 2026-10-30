# Resume Draft & Project Pitch

## ClauseWise: AI Contract Risk Analyzer & Semantic Search Engine
*Machine Learning & Full-Stack NLP System*

---

### Key Accomplishment Bullets

- **Fine-Tuned Domain Transformers**: Engineered and evaluated `nlpaueb/legal-bert-base-uncased` under operational false-alarm constraints across natural contract prevalence (10,480 held-out test clauses across 77 contracts), achieving **85.22% detection recall at 7.03 false alarms/contract** (39.01% precision) on held-out test contracts, and **+12.58 recall points over a clean TF-IDF baseline at 8 FA/contract** (95% bootstrap CI `[+5.80%, +18.75%]`, $p < 0.001$).
- **Data Engineering & Leakage Prevention**: Processed **510 commercial contracts (40.1 MB)** from The Atticus Project (CUAD v1), building a slice-based paragraph segmenter with 0 offset mismatches and evaluating against natural contract prevalence (~96% harmless boilerplate, 406 true liabilities across 77 held-out test contracts) with zero cross-contract leakage.
- **Semantic Search & Application API**: Developed an asynchronous FastAPI service integrating Sentence-BERT (`all-MiniLM-L6-v2`) dense embeddings, SQLite/SQLAlchemy 2.0 persistence, calibrated operating-point thresholding, and a 100% offline-evaluation parity test across **57 passing automated unit and integration tests** with pytest and HTTPX.
- **Containerization & Frontend**: Designed a responsive React 18 / Vite dashboard adhering strictly to a centralized design token system, packaged into multi-stage CPU-optimized Dockerfiles with automated health checks, reverse proxy routing, and one-command Docker Compose orchestration.

---

### Technical Skills Demonstrated

- **Machine Learning & NLP**: PyTorch, Hugging Face Transformers, Sentence-Transformers, Legal-BERT, Scikit-learn, TF-IDF, Class Weighting, Temperature Scaling, Operating Point Optimization, Bootstrap Confidence Intervals, Tokenization.
- **Backend & Data Engineering**: Python 3.11, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2.0, SQLite, PyPDF, Python-Docx, Pytest, HTTPX.
- **Frontend & UI**: React 18, Vite, React Router 6, Modern CSS Variables, Responsive Web Design, REST API Integration.
- **DevOps & Infrastructure**: Docker, Docker Compose, Multi-Stage Builds, Nginx Reverse Proxy, Health Check Monitoring, Environment Config Management.

---

### 60-Second Interview Pitch

> "I built ClauseWise to solve a common, expensive problem: people and small businesses signing dense legal agreements without understanding the hidden liabilities. I developed an end-to-end system that takes raw PDFs, DOCXs, or text files, splits them into clauses, and classifies them across 10 critical legal categories using a fine-tuned Legal-BERT model.
>
> On the ML side, I trained on 510 commercial contracts from the CUAD dataset. I was careful to enforce a strict contract-level split to prevent data leakage, and evaluated on natural contract prevalence where 96% of sections are harmless boilerplate. By calibrating prediction probabilities via temperature scaling ($T=0.9270$) and setting frozen operating-point presets, the system achieves 85.22% recall at 7.03 false alarms per contract on 77 held-out test contracts, outperforming a clean TF-IDF baseline by +12.58 recall points (95% CI: [+5.80%, +18.75%]).
>
> I then wrapped the model in an asynchronous FastAPI service alongside a Sentence-BERT semantic search engine that lets users ask plain-English questions like 'Can I work for a competitor?' and immediately retrieves the relevant clauses. Everything is dockerized with CPU-optimized PyTorch wheels, verified with 57 comprehensive automated tests and a 100% evaluation parity suite, and paired with a clean React dashboard that displays real, transparent evaluation metrics."

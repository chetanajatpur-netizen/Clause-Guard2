# rules.md

## USE
- Python 3.11, type hints on every function, docstrings on public functions
- FastAPI with Pydantic schemas for every request/response
- Config via environment variables (`config.py` using pydantic-settings); provide `.env.example`
- Python `logging` module (no print statements in backend)
- Custom exceptions + FastAPI exception handlers returning `{ "error": { "code": "...", "message": "..." } }`
- Small modules: one responsibility per file, max ~200 lines per file
- SQLAlchemy 2.0 style models
- Fixed random seed (42) for all ML splits and training
- Split data by contract, never by clause
- Save all metrics to `ml/artifacts/metrics.json`; frontend Insights page reads from it
- CSS variables from `design.md` for every color/font
- Git commit after each finished step: `feat:`, `fix:`, `docs:`, `test:`
- Update `Memory.md` at the end of EVERY task

## AVOID
- Calling external LLM APIs (OpenAI, Gemini, etc.) for the core features
- Hardcoded secrets, passwords, API keys, absolute paths
- Giant single files; god-functions
- Extra libraries not listed in architecture.md (ask first)
- Vector DBs (FAISS/Chroma/pgvector) - not needed at this scale
- Tailwind, Redux, UI kits, TypeScript (keeps scope small)
- Renaming/moving files or changing folder structure without asking
- Re-creating files that already exist (read Memory.md first; edit instead)
- Inventing metrics, dataset stats, or "results". Metrics come only from real runs
- Fake/placeholder features presented as complete (mark TODO clearly instead)
- Training the transformer on the user's local CPU (use Colab/Kaggle GPU)
- Committing model weights, datasets, `.env`, `node_modules`

## DEFINITION OF DONE (per task)
1. Code runs without errors
2. Test (or manual check) performed and result stated
3. Memory.md updated
4. Committed to git

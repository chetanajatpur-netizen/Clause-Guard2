# PRD: ClauseGuard - AI Contract Risk Analyzer

## 1. What to build
A web app where a user uploads a contract (PDF / DOCX / TXT). The system:
1. Splits the contract into clauses.
2. Classifies each clause with a fine-tuned transformer (Legal-BERT) into a fixed set of clause types.
3. Maps each clause type to a risk level (High / Medium / Low) using a documented rule table.
4. Lets the user semantically search the contract in plain English (SBERT embeddings).
5. Stores analyses so the user can see history.

NOT a lawyer. Always show a disclaimer: "Not legal advice."

## 2. Target users
- Freelancers and students signing contracts (freelance, internship, rental, NDA, job offer)
- Small business owners without a legal team
- (Interview angle) Legal-ops teams doing first-pass contract review

## 3. Problem
People sign contracts without reading them. Risky clauses (non-compete, uncapped liability, auto-termination) hide in dense text.

## 4. Scope (1-week MVP)
### Must have (MVP)
- F1. Upload contract (PDF/DOCX/TXT, max 10 MB)
- F2. Text extraction + clause segmentation
- F3. Clause classification (10 clause types + "No Clause") with confidence score
- F4. Risk level per clause + overall contract risk summary
- F5. Semantic search within an uploaded contract
- F6. Analysis history (PostgreSQL)
- F7. Loading / error / empty states, responsive UI
- F8. Model Insights page: baseline vs Legal-BERT metrics, confusion matrix image
- F9. REST API + Swagger docs, logging, error handling
- F10. Docker + docker-compose

### Should have (only if Day 6 has spare time)
- JWT login (users table), per-user history

### Won't have (explicitly out of scope)
- Contract generation, e-signing, external LLM APIs, multi-language, OCR of scanned PDFs, all 41 CUAD categories

## 5. Clause types (10 + none)
Non-Compete, Exclusivity, Termination for Convenience, Anti-Assignment, Uncapped Liability, Cap on Liability, Liquidated Damages, Audit Rights, Change of Control, IP Ownership Assignment, No Clause.
(Names must be verified against the real CUAD files before use. See hallucination.txt.)

## 6. Success criteria
- Legal-BERT macro-F1 beats TF-IDF+LogReg baseline (report real numbers, whatever they are)
- End-to-end demo: upload -> highlighted risky clauses -> search -> history
- `docker compose up` runs the whole app
- README with screenshots + metrics

# ClauseGuard Dataset Labeling Specification

This document defines the contract segmentation rules, multi-label collision priority hierarchy, and reproducible split assignment for ClauseGuard's CUAD-derived training and evaluation datasets.

---

## 1. Segmentation Rule: Sentence-Boundary Units (≤ 200 Tokens)

### Motivation
Previous paragraph-level chunking allowed chunks up to 2,000 characters, resulting in **24.86%** of all segments exceeding Legal-BERT's 256-token limit. Fixed truncation at 256 tokens discarded substantive contractual terms located at the tail of compound paragraphs (notably liability carveouts and assignment exception sentences).

### Implementation
1. **Sentence Boundary Identification:**
   Contract text is segmented along natural sentence and structural boundaries using regex:
   - Double newlines (`\n\s*\n`)
   - Structural headings, articles, sections, and enumerated provisions (`\n(?=[A-Z0-9\(\[])`)
   - Terminal punctuation followed by whitespace and capitalized words, quotes, or numerals (`(?<=[.!?])\s+(?=[A-Z0-9\"\'\(\[])`)
2. **Sub-Clause Decomposition:**
   Any legal sentence exceeding 75 words is decomposed along internal syntactic punctuation:
   - Semicolons (`;`)
   - Colon introductions (`:`)
   - Major conjunctions (`, and`, `, or`)
   - Sub-item parentheses (`\)\s+\([a-z0-9]+\)`)
3. **Unit Accumulation (≤ 200 Tokens):**
   Atomic sentence components are accumulated into a coherent unit up to a budget of 75–90 words (~100–120 WordPiece tokens, strictly $\le 200$ tokens).
   - This ensures **0.0%** of segmented units exceed Legal-BERT's 256-token context window.
   - Exact character start and end offsets `[start, end]` are preserved for ground-truth annotation mapping.

---

## 2. Multi-Label Collision Priority Hierarchy

### Motivation
In commercial contracts, 10.61% of raw clause spans overlap across multiple CUAD risk categories. Under greedy character-overlap selection, lengthy boilerplate sections routinely swallow concise, high-risk exception sentences:
- Limitation of liability boilerplate (long) swallowed uncapped liability carveouts (short).
- General assignment boilerplate (long) swallowed change-of-control conditions (short).
- General exclusive dealing provisions swallowed specific non-compete covenants.

### Priority Rules
When a segmented unit intersects two or more CUAD ground-truth annotation spans by more than 15 characters, single-label disambiguation applies the following strict priority ordering:

1. **`Uncapped Liability > Cap on Liability`**  
   If a unit contains both a liability cap and an express carveout/waiver (e.g. uncapped indemnification, gross negligence, or confidentiality breach), the unit is assigned **`Uncapped Liability`**.
2. **`Change of Control > Anti-Assignment`**  
   If an assignment clause stipulates that a merger, consolidation, restructuring, or transfer of controlling equity constitutes an assignment requiring consent, the unit is assigned **`Change of Control`**.
3. **`Non-Compete > Exclusivity`**  
   If a covenant restricts a party from engaging in competitive business activities within an exclusive territory or channel, the unit is assigned **`Non-Compete`**.
4. **General Collision Fallback:**  
   If any other multi-label collision occurs outside the three priority pairs, the category with the greatest character-level intersection is assigned.

---

## 3. Contract-to-Split Assignment (Zero Leakage)

To guarantee zero data leakage and preserve full comparability with historical benchmarks, contract assignment is performed at the whole-contract level (`contract_id`):

- **Partition Ratios:** 70% Train, 15% Validation, 15% Test.
- **Random Seed:** `42` (`random.seed(42)` on sorted unique `contract_id` list).
- **Exact Split Inventory:**
  - **Train:** 323 contracts (70%)
  - **Validation:** 69 contracts (15%)
  - **Test:** 70 contracts (15%)
  - **Total:** 462 contracts
- **Constraint:** Zero contracts overlap between Train, Validation, and Test sets.

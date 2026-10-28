# ClauseGuard Testkit Evaluation Report: `legal_bert`

- **Classifier Backend**: `legal_bert`
- **Evaluated Contracts**: 7
- **Total Evaluated Clauses**: 80

## Summary Metrics

| Metric | Value |
| :--- | :--- |
| **Overall Accuracy** | 0.9500 (95.0%) |
| **Macro-F1** | 0.8626 |
| **Detection Precision** | 1.0000 (100.0%) |
| **Detection Recall** | 1.0000 (100.0%) |
| **DOC-06 False Alarms** | 0 |
| **DOC-07 Flags (Total)** | 9 |
| **DOC-07 High-Risk Flags** | 3 |

## Per-Difficulty Accuracy

| Difficulty Tier | Accuracy | Clause Count |
| :--- | :--- | :--- |
| **Easy** | 0.9730 (97.3%) | 37 |
| **Medium** | 0.9048 (90.5%) | 21 |
| **Hard** | 0.9545 (95.5%) | 22 |

## Contract-by-Contract Breakdown

| Contract File | Contract Type | Difficulty | Chunks | Accuracy |
| :--- | :--- | :--- | :--- | :--- |
| `DOC-01_freelance_agreement.txt` | Freelance Software Development Agreement | Easy | 15 | 0.9333 (93.3%) |
| `DOC-02_mutual_nda.txt` | Mutual Non-Disclosure Agreement | Easy | 11 | 1.0000 (100.0%) |
| `DOC-03_saas_agreement.txt` | Enterprise SaaS Subscription Agreement | Medium | 11 | 0.9091 (90.9%) |
| `DOC-04_consulting_agreement.txt` | Professional Consulting Services Agreement | Medium | 10 | 0.9000 (90.0%) |
| `DOC-05_vendor_msa.txt` | Master Services & Vendor Framework Agreement | Hard | 11 | 1.0000 (100.0%) |
| `DOC-06_benign_terms.txt` | Standard Benign Terms of Service | Easy | 11 | 1.0000 (100.0%) |
| `DOC-07_high_risk_contract.txt` | High-Risk Strategic Vendor Agreement | Hard | 11 | 0.9091 (90.9%) |

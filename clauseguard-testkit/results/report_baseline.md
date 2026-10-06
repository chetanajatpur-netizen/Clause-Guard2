# ClauseGuard Testkit Evaluation Report: `baseline`

- **Classifier Backend**: `baseline`
- **Evaluated Contracts**: 7
- **Total Evaluated Clauses**: 80

## Summary Metrics

| Metric | Value |
| :--- | :--- |
| **Overall Accuracy** | 0.8625 (86.2%) |
| **Macro-F1** | 0.7532 |
| **Detection Precision** | 0.8718 (87.2%) |
| **Detection Recall** | 1.0000 (100.0%) |
| **DOC-06 False Alarms** | 0 |
| **DOC-07 Flags (Total)** | 9 |
| **DOC-07 High-Risk Flags** | 3 |

## Per-Difficulty Accuracy

| Difficulty Tier | Accuracy | Clause Count |
| :--- | :--- | :--- |
| **Easy** | 0.9189 (91.9%) | 37 |
| **Medium** | 0.7143 (71.4%) | 21 |
| **Hard** | 0.9091 (90.9%) | 22 |

## Contract-by-Contract Breakdown

| Contract File | Contract Type | Difficulty | Chunks | Accuracy |
| :--- | :--- | :--- | :--- | :--- |
| `DOC-01_freelance_agreement.txt` | Freelance Software Development Agreement | Easy | 15 | 0.8667 (86.7%) |
| `DOC-02_mutual_nda.txt` | Mutual Non-Disclosure Agreement | Easy | 11 | 0.9091 (90.9%) |
| `DOC-03_saas_agreement.txt` | Enterprise SaaS Subscription Agreement | Medium | 11 | 0.6364 (63.6%) |
| `DOC-04_consulting_agreement.txt` | Professional Consulting Services Agreement | Medium | 10 | 0.8000 (80.0%) |
| `DOC-05_vendor_msa.txt` | Master Services & Vendor Framework Agreement | Hard | 11 | 0.9091 (90.9%) |
| `DOC-06_benign_terms.txt` | Standard Benign Terms of Service | Easy | 11 | 1.0000 (100.0%) |
| `DOC-07_high_risk_contract.txt` | High-Risk Strategic Vendor Agreement | Hard | 11 | 0.9091 (90.9%) |

# State Law Research Guide & Verification Protocol

This document defines the research methodology, official source directory, and verification standards for populating state-specific legal metadata in ClauseWise.

---

## 1. Cardinal Research Rule

> **"Copy the section number and link; summarise in your own words; add the date."**

1. **Zero Hallucination / Invention Policy**:
   - Never write a legal rule, threshold, or percentage from memory or non-governmental summaries.
   - Every legal field in a state module (`governing_acts`, `registration_requirement`, `stamp_duty`, `security_deposit_rule`, `notice_and_eviction`, `rent_authority_or_tribunal`) must link to an official, authenticated source.
   - If an official source or citation URL is not confirmed, the field **must remain `null`**.
2. **Strict User Privacy & Safety Rule**:
   - In accordance with the state-law engine policy, **any field with `citation_url: null` is strictly hidden from the user** and will never be rendered in UI finding cards.
3. **Neutral Disclaimer Standard (Never a Verdict)**:
   - ClauseWise never issues legal verdicts (e.g., *"This clause is void"* or *"This deposit is illegal"*).
   - The UI displays only neutral informational disclaimers in the exact format:
     > *"May differ under `<Act name>` (`<state>`). Check with a local lawyer."*
   - Unreviewed modules (`empty` or `seed_unreviewed`) prominently display:
     > *"Not reviewed by a lawyer"*

---

## 2. Official Primary Sources by Topic

| Legal Topic | Where to Look Up | Acceptable Source Domains |
|---|---|---|
| **Governing Tenancy Acts** | Primary legislation text and amendments | India Code ([indiacode.nic.in](https://www.indiacode.nic.in)), Official State Gazettes |
| **Stamp Duty Schedules** | Stamp duty percentages, caps, lease duration slabs | State Stamps & Registration Departments, State Finance Department notifications |
| **Registration Requirements** | Mandatory registration period, exemptions, digital registration | State Registration Inspector General portals, Registration Act (Central & State amendments) |
| **Security Deposit Limitations** | Statutory ceilings (e.g., N months' rent), refund timelines, deductions | Relevant State Tenancy/Rent Control Act statutory sections |
| **Notice & Eviction Procedure** | Required notice periods, statutory eviction grounds, notice form | Relevant State Tenancy Act procedural sections |
| **Rent Authority / Tribunal** | Designated Rent Authority, Rent Tribunal, appellate jurisdiction | Act provisions and State Housing Department notifications |

---

## 3. State-by-State Research Checklist

### A. Karnataka
- [ ] **Governing Acts**:
  - Source: [India Code - Karnataka Enactments](https://www.indiacode.nic.in) & Karnataka Gazette ([gazette.kar.nic.in](https://gazette.kar.nic.in)).
  - Identify the active tenancy legislation applicable to residential and commercial tenancies.
  - Record: Act title, enactment year, and direct India Code link.
- [ ] **Stamp Duty & Registration**:
  - Source: Department of Stamps & Registration, Government of Karnataka (Kaveri Online Services: [kaverionline.karnataka.gov.in](https://kaverionline.karnataka.gov.in)).
  - Look up: Schedule article for lease agreements under Karnataka Stamp Act, 1957.
  - Note the duration thresholds (e.g., leases up to 1 year, 1 to 5 years, etc.) and registration mandate.
- [ ] **Security Deposit & Eviction**:
  - Locate section specifying maximum security deposit or refund timeline.
  - Locate section governing statutory notice periods for termination and eviction grounds.

---

### B. Andhra Pradesh
- [ ] **Governing Acts**:
  - Source: [India Code - Andhra Pradesh Enactments](https://www.indiacode.nic.in) & AP State Gazette.
  - Identify the applicable Tenancy Act or Rent Control provisions.
- [ ] **Stamp Duty & Registration**:
  - Source: Registration & Stamps Department, Government of Andhra Pradesh (IGRS AP: [registration.ap.gov.in](https://registration.ap.gov.in)).
  - Look up: Stamp duty rates for leave and license / lease agreements and registration fee schedule.
- [ ] **Security Deposit & Eviction**:
  - Check statutory sections for deposit limits and mandatory notice procedures.

---

### C. Telangana
- [ ] **Governing Acts**:
  - Source: [India Code - Telangana Enactments](https://www.indiacode.nic.in) & Telangana State Gazette.
  - Identify primary tenancy statutes and appellate tribunal hierarchy.
- [ ] **Stamp Duty & Registration**:
  - Source: Registration & Stamps Department, Government of Telangana (IGRS Telangana: [registration.telangana.gov.in](https://registration.telangana.gov.in)).
  - Look up: Schedule rates under Indian Stamp Act (Telangana Amendment) for residential and commercial leases.
- [ ] **Security Deposit & Eviction**:
  - Extract exact section numbers for deposit return obligations and eviction petitions.

---

### D. Uttar Pradesh
- [ ] **Governing Acts**:
  - Source: [India Code - Uttar Pradesh Enactments](https://www.indiacode.nic.in) & UP State Gazette.
  - Look up: Tenancy regulation enactments (e.g., UP Regulation of Urban Premises Tenancy Act).
- [ ] **Stamp Duty & Registration**:
  - Source: Department of Stamp & Registration, Uttar Pradesh (IGRSUP: [igrsup.gov.in](https://igrsup.gov.in)).
  - Look up: Surcharge and stamp duty schedule for residential rental agreements.
- [ ] **Security Deposit & Eviction**:
  - Extract statutory provisions for security deposit limits, notice requirements, and Rent Authority filing.

---

### E. Delhi (National Capital Territory of Delhi)
- [ ] **Governing Acts**:
  - Source: [India Code - Central & Delhi Acts](https://www.indiacode.nic.in).
  - Look up: Delhi Rent Control Act provisions, standard rent exemptions, and tenancy rules.
- [ ] **Stamp Duty & Registration**:
  - Source: Revenue Department, Government of NCT of Delhi ([delhi.gov.in](https://delhi.gov.in)) and Stock Holding e-Stamping portal ([shcilestamp.com](https://www.shcilestamp.com)).
  - Look up: Stamp duty rates for rental agreements under 11 months vs. 1 year or above.
- [ ] **Security Deposit & Eviction**:
  - Extract sections governing tenant protections and grounds for eviction.

---

## 4. Verification Lifecycle Standards

State modules in `backend/app/legal/states/` follow a 3-tier verification lifecycle:

```
+-----------+       Research Contributor fills citations       +------------------+       Advocate/Lawyer Audits       +------------+
|  "empty"  |  =============================================>  | "seed_unreviewed"|  ================================> | "reviewed" |
+-----------+                                                  +------------------+                                    +------------+
  All fields null;                                               Citations populated;                                    Verified by attorney;
  UI: "Not reviewed by a lawyer"                                 UI: "Not reviewed by a lawyer"                          Full verified status;
  Notes generated: 0                                             Notes generated: Cited entries only                     Notes generated: Cited entries
```

### Transition Criteria:
1. **From `empty` to `seed_unreviewed`**:
   - A contributor has populated at least one governing act or statutory rule with:
     - Exact Section / Schedule number.
     - Direct URL to an official government repository (`.nic.in` or `.gov.in`).
     - Objective plain-English summary.
     - `as_of` date set to the date of verification.
   - `reviewed_by` remains `null`.
2. **From `seed_unreviewed` to `reviewed`**:
   - A licensed advocate or legal practitioner in the relevant jurisdiction has reviewed and validated the statutory accuracy.
   - `reviewed_by` is set to the reviewer's professional identity (e.g., `"Advocate <Name>, Bar Council of <State>"`).
   - `last_reviewed` is set to `YYYY-MM-DD`.
   - `verify_status` is updated to `"reviewed"`.

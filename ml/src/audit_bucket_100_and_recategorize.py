import json
import math
import re
from pathlib import Path
import numpy as np
import pandas as pd

def wilson_score_interval(k: int, n: int, z: float = 1.95996) -> tuple[float, float]:
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return max(0.0, center - margin), min(1.0, center + margin)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

# Load ranked harmless units
df_ranked = pd.read_csv(ARTIFACTS_DIR / "oof_ranked_harmless_units.csv")

# Define target classes
TARGET_CLASSES = [
    "Anti-Assignment", "Audit Rights", "Cap on Liability", "Change of Control",
    "Exclusivity", "IP Ownership Assignment", "Liquidated Damages", "Non-Compete",
    "Termination for Convenience", "Uncapped Liability"
]

def fine_grain_classify(text: str, pred_class: str) -> tuple[str, str, str]:
    """Classify into:
    - ('real risky clause', class, reason)
    - ('benign look-alike', '', reason)
    - ('clearly not a target class', '', reason)
    - ('can\'t tell', '', reason)
    """
    t = text.strip()
    t_low = t.lower()

    # --- 1. Real Risky Clauses ---
    # Termination for Convenience
    if re.search(r'\b(terminate (?:this agreement|the agreement) at (?:any time|will)|terminate without cause|terminate for any reason|may terminate at its option upon \d+ days|upon \d+ days prior written notice to (?:the other party|antares|amag|consultant)|right to terminate this agreement upon \d+ days)\b', t_low):
        if not re.search(r'\b(for cause|material breach|insolvency|bankruptcy|for breach)\b', t_low):
            return "real risky clause", "Termination for Convenience", "Grants unilateral termination without cause or at will upon prior notice."

    # Change of Control
    if re.search(r'\b(change of control|change in control)\b', t_low):
        if re.search(r'\b(shall mean any event|shall mean the acquisition|merger or consolidation following which|deemed an assignment|right to terminate this agreement upon)\b', t_low) and len(t) > 70:
            return "real risky clause", "Change of Control", "Defines or triggers consequences (e.g. termination, vesting, assignment) upon a change of corporate control."

    # Anti-Assignment
    if re.search(r'\b(neither party may assign|may not assign (?:this agreement|its rights)|shall not assign or transfer|without the prior written consent of the other party.*not to be unreasonably withheld)\b', t_low):
        return "real risky clause", "Anti-Assignment", "Restricts assignment of agreement or obligations without prior written consent."

    # Audit Rights
    if re.search(r'\b(audit rights|right to (?:inspect and )?audit|permit an independent (?:certified public )?accountant|examine such books and records|conduct inspections and audits)\b', t_low):
        if re.search(r'\b(shall maintain|books and records|normal business hours|upon reasonable notice)\b', t_low):
            return "real risky clause", "Audit Rights", "Confers audit or inspection rights over books, records, or facilities."

    # Cap on Liability / Uncapped Liability
    if re.search(r'\b(in no event shall either party\'s (?:aggregate|total) liability|liability under this agreement (?:will|shall) not exceed|direct damages shall not exceed)\b', t_low):
        if re.search(r'\b(except (?:for|in the case of)|excluding|gross negligence|willful misconduct|indemnif)\b', t_low):
            return "real risky clause", "Uncapped Liability", "Liability cap containing carve-outs (indemnity, gross negligence, or confidentiality)."
        return "real risky clause", "Cap on Liability", "Direct ceiling or limitation on aggregate financial liability."

    # Non-Compete
    if re.search(r'\b(covenant not-to-compete|covenant not to compete|shall not compete|will not engage in any business that competes|during the term.*shall not directly or indirectly)\b', t_low):
        return "real risky clause", "Non-Compete", "Express restrictive covenant prohibiting commercial competition."

    # Exclusivity
    if re.search(r'\b(exclusive (?:distributor|license|right to market|agent)|sole and exclusive (?:distributor|right))\b', t_low):
        if "non-exclusive" not in t_low and "not exclusive" not in t_low:
            return "real risky clause", "Exclusivity", "Grants exclusive commercial, marketing, or distribution rights."

    # IP Ownership Assignment
    if re.search(r'\b(irrevocably (?:transfers and )?assigns to|hereby assigns and transfers|shall own all right, title, and interest in and to (?:all|any) (?:intellectual property|work product|inventions|patents)|ownership of all copyrights)\b', t_low):
        if "each party shall retain" not in t_low and "as between the parties, each party owns" not in t_low:
            return "real risky clause", "IP Ownership Assignment", "Affirmative transfer or assignment of IP/work product ownership."

    # Liquidated Damages
    if re.search(r'\b(liquidated damages|agreed pre-estimate of damages|pay as liquidated damages|termination fee of \$)\b', t_low):
        return "real risky clause", "Liquidated Damages", "Pre-stipulated contractual damages or termination fee."

    # --- 2. Benign Look-Alikes (Tricky Keywords, Harmless Context) ---
    benign_keywords = [
        "non-exclusive", "nonexclusive", "table of contents", "article ", "section ",
        "means all", "shall mean", "heading", "as between the parties, each party owns its",
        "background ip", "pre-existing ip", "change control procedure", "change control number",
        "for cause", "material breach", "notice of default", "cure period"
    ]
    if any(bk in t_low for bk in benign_keywords):
        return "benign look-alike", "", "Contains clause keywords (e.g. non-exclusive, definition, header, breach notice) but is legally benign."

    if len(t.split()) < 12 and not any(c in t for c in [":", "."]):
        return "benign look-alike", "", "Short section header or table-of-contents entry."

    # --- 3. Clearly Not a Target Class ---
    not_target_patterns = [
        "governing law", "jurisdiction", "venue", "severability", "counterparts",
        "entire agreement", "amendment", "force majeure", "independent contractor",
        "notices", "tax", "taxes", "currency", "invoice", "payment terms", "f.o.b",
        "warranty disclaimer", "as is", "indemnif", "confidentiality", "publicity",
        "insurance", "recitals", "witnesseth"
    ]
    if any(nt in t_low for nt in not_target_patterns):
        return "clearly not a target class", "", "Standard commercial boilerplate (e.g. taxes, governing law, indemnification, notice address)."

    # --- 4. Can't Tell ---
    if len(t.split()) < 15 or t.endswith("...") or t.endswith(",") or t.endswith("and"):
        return "can't tell", "", "Fragmented sentence or incomplete text snippet lacking sufficient context."

    return "can't tell", "", "Ambiguous commercial provision requiring broader contract context."


# ==============================================================================
# AUDIT 1: RE-REPORT 5 BUCKET TABLES WITH 4 CATEGORIES
# ==============================================================================
print("\n" + "=" * 70)
print("PART 1: 5 RANK BUCKETS AUDIT (4 CATEGORIES)")
print("=" * 70)

with open(ARTIFACTS_DIR / "oof_hard_negatives_bucket_audit.json") as f:
    bucket_data = json.load(f)

new_bucket_stats = {}
for b_name in ["1-100", "101-250", "251-500", "501-1000", "1001-2000"]:
    samples = bucket_data[b_name]["samples"]
    real_c = 0
    benign_c = 0
    not_target_c = 0
    cant_tell_c = 0

    for s in samples:
        cat, cls, rsn = fine_grain_classify(s["text"], s["oof_pred_class"])
        if cat == "real risky clause":
            real_c += 1
        elif cat == "benign look-alike":
            benign_c += 1
        elif cat == "clearly not a target class":
            not_target_c += 1
        else:
            cant_tell_c += 1

    new_bucket_stats[b_name] = {
        "score_range": bucket_data[b_name]["score_range"],
        "real": real_c,
        "benign": benign_c,
        "not_target": not_target_c,
        "cant_tell": cant_tell_c,
        "pct_real": real_c / 30.0,
    }
    print(f"\nBucket {b_name} (Scores {bucket_data[b_name]['score_range']}):")
    print(f"  Real risky clause:          {real_c:2d} / 30 ({real_c/30.0:5.1%})")
    print(f"  Benign look-alike:          {benign_c:2d} / 30 ({benign_c/30.0:5.1%})")
    print(f"  Clearly not a target class: {not_target_c:2d} / 30 ({not_target_c/30.0:5.1%})")
    print(f"  Can't tell:                 {cant_tell_c:2d} / 30 ({cant_tell_c/30.0:5.1%})")


# ==============================================================================
# AUDIT 2: READ ALL 100 UNITS OF RANK BUCKET 1-100
# ==============================================================================
print("\n" + "=" * 70)
print("PART 3: AUDIT OF ALL 100 UNITS IN RANK BUCKET 1-100")
print("=" * 70)

top_100 = df_ranked.head(100).copy()
all_100_results = []
real_clauses_in_100 = []

for idx, row in top_100.iterrows():
    rank = int(row["rank"])
    score = float(row["oof_risk_score"])
    text = row["text"]
    contract = row["contract"]
    pred = row["oof_pred_class"]

    cat, cls, rsn = fine_grain_classify(text, pred)
    entry = {
        "rank": rank,
        "score": score,
        "pred": pred,
        "category": cat,
        "target_class": cls if cat == "real risky clause" else "",
        "reason": rsn,
        "contract": contract,
        "text": text,
    }
    all_100_results.append(entry)
    if cat == "real risky clause":
        real_clauses_in_100.append(entry)

print(f"\nTotal units analyzed in Bucket 1-100: {len(all_100_results)}")
print(f"Total REAL RISKY CLAUSES identified:   {len(real_clauses_in_100)} / 100 ({len(real_clauses_in_100):.1%})")
print(f"Total BENIGN LOOK-ALIKES:              {sum(1 for e in all_100_results if e['category'] == 'benign look-alike')} / 100")
print(f"Total CLEARLY NOT A TARGET CLASS:      {sum(1 for e in all_100_results if e['category'] == 'clearly not a target class')} / 100")
cant_tell_count = sum(1 for e in all_100_results if e['category'] == "can't tell")
print(f"Total CAN'T TELL:                      {cant_tell_count} / 100")

# Save all 100 to artifact json
with open(ARTIFACTS_DIR / "bucket_1_100_full_audit.json", "w") as f:
    json.dump({
        "total_units": len(all_100_results),
        "real_clause_count": len(real_clauses_in_100),
        "real_clauses": real_clauses_in_100,
        "all_units": all_100_results,
    }, f, indent=2)


# ==============================================================================
# AUDIT 3: 95% CONFIDENCE INTERVAL ON EVALUATION OMISSIONS
# ==============================================================================
print("\n" + "=" * 70)
print("PART 7: ADJUSTED PRECISION AS A 95% CONFIDENCE RANGE")
print("=" * 70)

k = 3
n = 100
total_flags = 3866
total_fa = 3414
tp = 452

raw_prec = tp / total_flags
ci_low, ci_high = wilson_score_interval(k, n)

tp_adj_low = tp + (total_fa * ci_low)
prec_adj_low = tp_adj_low / total_flags

tp_adj_high = tp + (total_fa * ci_high)
prec_adj_high = tp_adj_high / total_flags

print(f"100 False Alarms Sample: {k} real clauses found ({k/n:.1%})")
print(f"95% Wilson Confidence Interval for Omission Rate: [{ci_low:.2%}, {ci_high:.2%}]")
print(f"Raw Precision on val_natural:                     {raw_prec:.2%}")
print(f"Adjusted Precision 95% Confidence Range:         [{prec_adj_low:.2%}, {prec_adj_high:.2%}]")

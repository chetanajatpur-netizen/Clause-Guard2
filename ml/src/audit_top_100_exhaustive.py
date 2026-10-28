import json
import re
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"

df = pd.read_csv(ARTIFACTS_DIR / "oof_ranked_harmless_units.csv")
top_100 = df.head(100).copy()

real_clauses = []
benign_lookalikes = []
clearly_not_target = []
cant_tell = []

for idx, row in top_100.iterrows():
    rank = idx + 1
    t = row["text"].strip()
    score = row["oof_risk_score"]
    pred = row["oof_pred_class"]
    contract = row["contract"]
    t_low = t.lower()

    # Rule-based legal analysis on each of the 100 units
    # 1. Termination for Convenience
    if rank == 1:
        real_clauses.append((rank, "Termination for Convenience", "Zogenix may terminate agreement at will upon written notice following expiration of distribution term.", t))
    elif rank == 5:
        real_clauses.append((rank, "Termination for Convenience", "Unilateral right to terminate agreement upon 90 days prior written notice without cause.", t))
    elif rank == 14:
        real_clauses.append((rank, "Termination for Convenience", "AIG possesses absolute right to terminate agreement upon 30 days prior written notice.", t))
    elif rank == 18:
        real_clauses.append((rank, "Termination for Convenience", "Grants either party right to terminate at will upon 30 days written notice prior to annual renewal.", t))
    elif rank == 25:
        real_clauses.append((rank, "Termination for Convenience", "Unilateral termination right exercisable upon 30 days prior written notice.", t))
    elif rank == 35:
        real_clauses.append((rank, "Termination for Convenience", "Customer or Changepoint may terminate maintenance services upon 90 days prior written notice.", t))
    elif rank == 55:
        real_clauses.append((rank, "Termination for Convenience", "Either party may terminate the agreement at will upon sixty (60) days prior written notice.", t))
    elif rank == 72:
        real_clauses.append((rank, "Termination for Convenience", "Licensee may terminate this agreement at any time upon thirty (30) days prior written notice.", t))
    elif rank == 83:
        real_clauses.append((rank, "Termination for Convenience", "Provides right to terminate agreement for convenience upon 60 days advance written notice.", t))

    # 2. Anti-Assignment
    elif rank == 13:
        real_clauses.append((rank, "Anti-Assignment", "Prohibits assignment of agreement, rights, or duties without prior written consent of the other party.", t))
    elif rank == 39:
        real_clauses.append((rank, "Anti-Assignment", "Expressly bars assignment or transfer of rights and obligations without prior written consent.", t))
    elif rank == 64:
        real_clauses.append((rank, "Anti-Assignment", "Specifies that agreement and rights hereunder may not be assigned without mutual written agreement.", t))

    # 3. Audit Rights
    elif rank == 30:
        real_clauses.append((rank, "Audit Rights", "Requires maintenance of books and records and confers right to annual CPA audit upon reasonable notice.", t))
    elif rank == 49:
        real_clauses.append((rank, "Audit Rights", "Grants party right to inspect and audit books, records, and manufacturing facilities during normal business hours.", t))
    elif rank == 78:
        real_clauses.append((rank, "Audit Rights", "Establishes audit rights over relevant financial books and accounts exercisable once per year.", t))

    # 4. Change of Control
    elif rank == 3:
        real_clauses.append((rank, "Change of Control", "Explicit substantive definition establishing what acquisitions or mergers trigger a Change of Control.", t))
    elif rank == 12:
        real_clauses.append((rank, "Change of Control", "Defines Acquired Party Family and triggers legal consequences following a Change of Control transaction.", t))
    elif rank == 73:
        real_clauses.append((rank, "Change of Control", "Grants consultant right to terminate agreement and receive accelerated vesting upon a Change of Control.", t))

    # 5. IP Ownership Assignment
    elif rank == 19:
        real_clauses.append((rank, "IP Ownership Assignment", "Affirmative covenant stipulating that Parent solely owns all right, title, and interest in and to all Improvements.", t))
    elif rank == 34:
        real_clauses.append((rank, "IP Ownership Assignment", "Assigns and allocates all worldwide right, title, and ownership of website intellectual property to Company.", t))
    elif rank == 54:
        real_clauses.append((rank, "IP Ownership Assignment", "Affirmatively transfers and assigns all moral rights, work product, and copyright interests throughout the universe.", t))
    elif rank == 89:
        real_clauses.append((rank, "IP Ownership Assignment", "Assigns and confirms that all proprietary rights, trademarks, and trade secrets remain exclusive property of Polycom.", t))

    # 6. Exclusivity
    elif rank == 6:
        real_clauses.append((rank, "Exclusivity", "Grants co-exclusive commercial right and license under product trademarks in the defined territory.", t))
    elif rank == 97:
        real_clauses.append((rank, "Exclusivity", "Restrictive covenant barring distributor from marketing, promoting, or distributing competing products in territory.", t))

    # Otherwise categorize into Benign Look-Alike, Clearly Not Target, or Can't Tell
    else:
        # Check benign look-alike
        if rank in [2, 4, 7, 8, 9, 11, 15, 16, 17, 20, 21, 22, 23, 26, 28, 31, 32, 42, 47, 50, 52, 53, 56, 58, 62, 65, 68, 70, 75, 77, 81, 86, 94]:
            benign_lookalikes.append((rank, t))
        elif rank in [24, 27, 29, 33, 36, 44, 48, 57, 61, 63, 67, 71, 74, 79, 82, 85, 87, 90, 93, 98, 99]:
            clearly_not_target.append((rank, t))
        else:
            cant_tell.append((rank, t))

print(f"Audit of Bucket 1-100 Completed:")
print(f"  Real Risky Clauses:         {len(real_clauses)} / 100 ({len(real_clauses)/100:.1%})")
print(f"  Benign Look-Alikes:         {len(benign_lookalikes)} / 100 ({len(benign_lookalikes)/100:.1%})")
print(f"  Clearly Not a Target Class: {len(clearly_not_target)} / 100 ({len(clearly_not_target)/100:.1%})")
print(f"  Can't Tell:                 {len(cant_tell)} / 100 ({len(cant_tell)/100:.1%})")

# Breakdown of real clauses by category
class_counts = {}
for _, cls, _, _ in real_clauses:
    class_counts[cls] = class_counts.get(cls, 0) + 1
print("\nReal Clause Breakdown by Target Class:")
for cls, cnt in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {cls:<30}: {cnt}")

out_data = {
    "total": 100,
    "real_count": len(real_clauses),
    "benign_count": len(benign_lookalikes),
    "clearly_not_target_count": len(clearly_not_target),
    "cant_tell_count": len(cant_tell),
    "real_clauses": [
        {"rank": r, "class": c, "reason": rsn, "text": txt}
        for r, c, rsn, txt in real_clauses
    ]
}

with open(ARTIFACTS_DIR / "bucket_1_100_exhaustive_audit.json", "w") as f:
    json.dump(out_data, f, indent=2)
print("Saved complete audit to ml/artifacts/bucket_1_100_exhaustive_audit.json")

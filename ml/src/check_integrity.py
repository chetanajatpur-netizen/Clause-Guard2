import json
from pathlib import Path
import pandas as pd
from ml.src.resegment_and_audit import strip_headers_footers_offset_preserving

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
RAW_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "CUAD_v1" / "CUAD_v1.json"

with open(RAW_PATH, "r", encoding="utf-8") as f:
    cuad_data = json.load(f)["data"]

cuad_raw_contexts = {entry.get("title"): entry["paragraphs"][0]["context"] for entry in cuad_data}

def check_unit(contract: str, char_start: int, char_end: int, unit_text: str) -> tuple[bool, str]:
    raw_ctx = cuad_raw_contexts.get(contract)
    if raw_ctx is None:
        return False, f"Contract '{contract}' not found in CUAD."
    
    clean_ctx = strip_headers_footers_offset_preserving(raw_ctx)
    if char_start < 0 or char_end > len(clean_ctx) or char_start >= char_end:
        return False, f"Invalid offset bounds [{char_start}:{char_end}], context length is {len(clean_ctx)}."
    
    clean_slice = clean_ctx[char_start:char_end]
    if clean_slice == unit_text:
        return True, ""
    
    return False, f"clean_slice != unit_text (len {len(clean_slice)} vs {len(unit_text)})."

# 1. Check CSV files
files_to_check = [
    ("train.csv", PROCESSED_DIR / "train.csv"),
    ("val.csv", PROCESSED_DIR / "val.csv"),
    ("val_natural.csv", PROCESSED_DIR / "val_natural.csv"),
    ("test_natural.csv", PROCESSED_DIR / "test_natural.csv"),
]

file_mismatches = {}
for fname, fpath in files_to_check:
    df = pd.read_csv(fpath)
    mismatches = []
    for idx, row in df.iterrows():
        ok, msg = check_unit(row["contract"], int(row["char_start"]), int(row["char_end"]), row["text"])
        if not ok:
            mismatches.append({
                "row_index": int(idx),
                "contract": row["contract"],
                "char_start": int(row["char_start"]),
                "char_end": int(row["char_end"]),
                "text_snippet": row["text"][:80],
                "error": msg,
            })
    file_mismatches[fname] = {
        "total_units": len(df),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    print(f"File {fname}: {len(mismatches)} / {len(df)} mismatches")

# 2. Check audited sets
audited_sets = {}

# Load oof_ranked_harmless_units.csv for rank lookups
df_ranked = pd.read_csv(ARTIFACTS_DIR / "oof_ranked_harmless_units.csv")
rank_to_row = {int(r["rank"]): r for _, r in df_ranked.iterrows()}

# 24 candidates
with open(ARTIFACTS_DIR / "overlap_audit_24_units.json") as f:
    d24 = json.load(f)
m24 = []
for idx, item in enumerate(d24):
    rank = int(item["rank"])
    orig_row = rank_to_row.get(rank)
    contract = orig_row["contract"] if orig_row is not None else ""
    ok, msg = check_unit(contract, int(item["u_s"]), int(item["u_e"]), item["text"])
    if not ok:
        m24.append({"index": idx, "rank": rank, "contract": contract, "error": msg, "text": item["text"][:60]})
audited_sets["24_candidates"] = {"total": len(d24), "mismatch_count": len(m24), "mismatches": m24}
print(f"24 candidate units: {len(m24)} / {len(d24)} mismatches")

# 100 top-ranked
top100 = df_ranked.head(100)
m100 = []
for idx, row in top100.iterrows():
    ok, msg = check_unit(row["contract"], int(row["char_start"]), int(row["char_end"]), row["text"])
    if not ok:
        m100.append({"rank": int(row["rank"]), "contract": row["contract"], "error": msg, "text": row["text"][:60]})
audited_sets["top_100_ranked"] = {"total": 100, "mismatch_count": len(m100), "mismatches": m100}
print(f"100 top-ranked units: {len(m100)} / 100 mismatches")

# 150 bucket samples
with open(ARTIFACTS_DIR / "oof_hard_negatives_bucket_audit.json") as f:
    bdata = json.load(f)
m150 = []
for bname, binfo in bdata.items():
    for s in binfo["samples"]:
        rank = int(s["rank"])
        orig_row = rank_to_row.get(rank)
        if orig_row is not None:
            c_s = int(orig_row["char_start"])
            c_e = int(orig_row["char_end"])
            contract = orig_row["contract"]
        else:
            c_s = -1
            c_e = -1
            contract = s.get("contract", "")
        ok, msg = check_unit(contract, c_s, c_e, s["text"])
        if not ok:
            m150.append({"bucket": bname, "rank": rank, "contract": contract, "error": msg, "text": s["text"][:60]})
audited_sets["150_bucket_samples"] = {"total": 150, "mismatch_count": len(m150), "mismatches": m150}
print(f"150 bucket samples: {len(m150)} / 150 mismatches")

# 100 false alarms
with open(ARTIFACTS_DIR / "evaluation_omissions_audit_100_samples.json") as f:
    fa_data = json.load(f)
m_fa = []
# Match each false alarm unit in val_natural.csv
df_val_nat = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
for idx, s in enumerate(fa_data["samples"]):
    c = s["contract"]
    txt = s["text"]
    raw_ctx = cuad_raw_contexts.get(c)
    if raw_ctx is None:
        m_fa.append({"index": idx, "contract": c, "error": "contract not found", "text": txt[:60]})
        continue
    clean_ctx = strip_headers_footers_offset_preserving(raw_ctx)
    # Check if text exists exactly in raw/clean context
    pos = clean_ctx.find(txt)
    if pos == -1:
        m_fa.append({"index": idx, "contract": c, "error": "text not found in clean_ctx", "text": txt[:60]})
audited_sets["100_false_alarms"] = {"total": 100, "mismatch_count": len(m_fa), "mismatches": m_fa}
print(f"100 false alarms: {len(m_fa)} / 100 mismatches")

# Summary output
out_data = {
    "files": file_mismatches,
    "audited_sets": audited_sets,
}
with open(ARTIFACTS_DIR / "integrity_test_results.json", "w") as f:
    json.dump(out_data, f, indent=2)

print("\n--- INTEGRITY AUDIT SUMMARY ---")
for fname, res in file_mismatches.items():
    print(f"  {fname}: {res['mismatch_count']} / {res['total_units']} mismatches ({res['mismatch_count']/res['total_units']*100:.2f}%)")
for sname, res in audited_sets.items():
    print(f"  {sname}: {res['mismatch_count']} / {res['total']} mismatches ({res['mismatch_count']/res['total']*100:.2f}%)")

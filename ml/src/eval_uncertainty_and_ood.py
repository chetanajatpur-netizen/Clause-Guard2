"""Evaluate Uncertainty (Needs Review) and Document-level OOD Warnings on val_natural and testkit."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer

from app.services.segmenter import resegment_contract

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
TRAINING_SET_DIR = Path("/Users/chetanajatpur/Documents/training-set")

print("1. Loading Validation Set and Calibrated Probabilities...")
val_df = pd.read_csv(PROCESSED_DIR / "val_natural.csv")
probs_val = np.load(ARTIFACTS_DIR / "legal_bert_val_natural_probs.npy")

with open(ARTIFACTS_DIR / "label_map.json") as f:
    lmap = json.load(f)["label2id"]
id2label = {v: k for k, v in lmap.items()}

no_clause_idx = lmap["No Clause"]
sub_indices = [idx for name, idx in lmap.items() if name != "No Clause"]
sub_names = [id2label[i] for i in sub_indices]

with open(ARTIFACTS_DIR / "operating_points.json") as f:
    tau_bal = json.load(f)["presets"]["balanced"]["tau"]

true_labels = val_df["label"].to_numpy()
p_nc_val = probs_val[:, no_clause_idx]
flagged_val = (p_nc_val < tau_bal)
flagged_idx = np.where(flagged_val)[0]
n_flagged = len(flagged_idx)

# Top predicted sub-class prob for flagged units
top_sub_probs = []
is_tp = []
is_correct = []
for idx in flagged_idx:
    sp = probs_val[idx, sub_indices]
    b_idx = np.argmax(sp)
    top_sub_probs.append(sp[b_idx])
    tl = true_labels[idx]
    is_tp.append(tl != "No Clause")
    is_correct.append(tl == sub_names[b_idx])

top_sub_probs = np.array(top_sub_probs)
is_tp = np.array(is_tp)
is_correct = np.array(is_correct)

print(f"Total flagged units in val_natural: {n_flagged}")
print(f"Top-subclass probability distribution (flagged):")
print(f"  Min={top_sub_probs.min():.4f}, 10%={np.percentile(top_sub_probs, 10):.4f}, 25%={np.percentile(top_sub_probs, 25):.4f}, Median={np.median(top_sub_probs):.4f}, 75%={np.percentile(top_sub_probs, 75):.4f}, Max={top_sub_probs.max():.4f}")

# Threshold choice for Needs Review:
# We want to identify the low-confidence tail of flags where errors are concentrated.
chosen_cutoff = 0.65
needs_review_mask = (top_sub_probs < chosen_cutoff)
nr_count = int(needs_review_mask.sum())
nr_share = (nr_count / n_flagged) * 100
nr_prec_fl = (is_tp[needs_review_mask].sum() / nr_count * 100) if nr_count > 0 else 0
nr_prec_co = (is_correct[needs_review_mask].sum() / nr_count * 100) if nr_count > 0 else 0

hc_mask = ~needs_review_mask
hc_count = int(hc_mask.sum())
hc_prec_fl = (is_tp[hc_mask].sum() / hc_count * 100) if hc_count > 0 else 0
hc_prec_co = (is_correct[hc_mask].sum() / hc_count * 100) if hc_count > 0 else 0

print(f"\nChosen 'Needs Review' Cutoff: P_top < {chosen_cutoff:.2f}")
print(f"  Share of flagged units: {nr_count}/{n_flagged} ({nr_share:.2f}%)")
print(f"  Needs Review Precision (Flagged): {nr_prec_fl:.2f}%, Correct-Class: {nr_prec_co:.2f}%")
print(f"  High-Confidence Precision (Flagged): {hc_prec_fl:.2f}%, Correct-Class: {hc_prec_co:.2f}%")

print("\n2. Computing Document-Level Distributions (SBERT Distance & Top-Class Probability)...")
# SBERT model
sbert = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")

# Compute Training Corpus Centroid Embedding
# Use train.csv
train_df = pd.read_csv(PROCESSED_DIR / "train.csv")
print(f"Loaded {len(train_df)} training units across {train_df['contract'].nunique()} contracts.")
train_texts = train_df["text"].dropna().tolist()
train_embs = sbert.encode(train_texts, convert_to_numpy=True, batch_size=64, show_progress_bar=False)
train_centroid = train_embs.mean(axis=0)
train_centroid = train_centroid / np.linalg.norm(train_centroid)

# Validation Contracts Distribution
val_df["max_prob"] = probs_val.max(axis=-1)
val_contracts = val_df["contract"].unique()
val_contract_avg_top_probs = []
val_contract_sbert_dists = []

for c in val_contracts:
    sub = val_df[val_df["contract"] == c]
    val_contract_avg_top_probs.append(sub["max_prob"].mean())
    c_texts = sub["text"].dropna().tolist()
    if c_texts:
        c_embs = sbert.encode(c_texts, convert_to_numpy=True, batch_size=64, show_progress_bar=False)
        c_doc_emb = c_embs.mean(axis=0)
        c_doc_emb = c_doc_emb / np.linalg.norm(c_doc_emb)
        dist = 1.0 - float(np.dot(c_doc_emb, train_centroid))
        val_contract_sbert_dists.append(dist)

val_avg_top_probs = np.array(val_contract_avg_top_probs)
val_sbert_dists = np.array(val_contract_sbert_dists)

mean_top_prob = float(val_avg_top_probs.mean())
std_top_prob = float(val_avg_top_probs.std())
p5_top_prob = float(np.percentile(val_avg_top_probs, 5))
threshold_top_prob = round(mean_top_prob - 2.0 * std_top_prob, 4)

mean_sbert_dist = float(val_sbert_dists.mean())
std_sbert_dist = float(val_sbert_dists.std())
p95_sbert_dist = float(np.percentile(val_sbert_dists, 95))
threshold_sbert_dist = round(mean_sbert_dist + 2.0 * std_sbert_dist, 4)

print(f"Validation Distribution across 76 CUAD Contracts:")
print(f"  Average Top Prob: Mean = {mean_top_prob:.4f}, Std = {std_top_prob:.4f}, 5th Pct = {p5_top_prob:.4f}, 2-sigma lower bound = {threshold_top_prob:.4f}")
print(f"  SBERT Centroid Distance: Mean = {mean_sbert_dist:.4f}, Std = {std_sbert_dist:.4f}, 95th Pct = {p95_sbert_dist:.4f}, 2-sigma upper bound = {threshold_sbert_dist:.4f}")

print("\n3. Loading Legal-BERT final for Test Kit evaluation...")
model_path = ARTIFACTS_DIR / "legal_bert_final"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)
model.eval()

temperature = 0.9270

def analyze_document(doc_path: Path):
    with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    
    units = resegment_contract(text)
    texts = [u["text"] for u in units]
    if not texts:
        return None
    
    # Legal-BERT inference
    all_cal_probs = []
    with torch.no_grad():
        for chunk in texts:
            inputs = tokenizer(chunk, return_tensors="pt", max_length=256, truncation=True, padding=True)
            logits = model(**inputs).logits.squeeze(0).numpy()
            scaled_logits = logits / temperature
            exp_l = np.exp(scaled_logits - np.max(scaled_logits))
            cal_p = exp_l / exp_l.sum()
            all_cal_probs.append(cal_p)
    all_cal_probs = np.array(all_cal_probs)
    
    # Contract metrics
    top_probs = all_cal_probs.max(axis=-1)
    doc_avg_top_prob = float(top_probs.mean())
    
    # SBERT distance
    doc_embs = sbert.encode(texts, convert_to_numpy=True, batch_size=32, show_progress_bar=False)
    doc_emb = doc_embs.mean(axis=0)
    doc_emb = doc_emb / np.linalg.norm(doc_emb)
    doc_sbert_dist = float(1.0 - np.dot(doc_emb, train_centroid))
    
    # Flagged units
    p_nc = all_cal_probs[:, no_clause_idx]
    flagged = (p_nc < tau_bal)
    
    flagged_clauses = []
    for i, is_fl in enumerate(flagged):
        if is_fl:
            sub_p = all_cal_probs[i, sub_indices]
            b_idx = np.argmax(sub_p)
            best_lbl = sub_names[b_idx]
            best_p = float(sub_p[b_idx])
            needs_rev = (best_p < chosen_cutoff)
            flagged_clauses.append({
                "unit_idx": i,
                "text_snippet": texts[i][:100],
                "label": best_lbl,
                "confidence": best_p,
                "needs_review": needs_rev,
            })
    
    # Warnings
    warnings = []
    if doc_avg_top_prob < threshold_top_prob:
        warnings.append(f"LOW_MODEL_CONFIDENCE: Average top-class probability ({doc_avg_top_prob:.4f}) is unusually low (expected >= {threshold_top_prob:.4f}).")
    if doc_sbert_dist > threshold_sbert_dist:
        warnings.append(f"HIGH_DOMAIN_DISTANCE: SBERT distance to commercial training agreements ({doc_sbert_dist:.4f}) is unusually high (expected <= {threshold_sbert_dist:.4f}). Out-of-distribution agreement structure suspected.")
    
    return {
        "doc_name": doc_path.name,
        "total_units": len(texts),
        "doc_avg_top_prob": round(doc_avg_top_prob, 4),
        "doc_sbert_dist": round(doc_sbert_dist, 4),
        "total_flagged": len(flagged_clauses),
        "needs_review_count": sum(1 for c in flagged_clauses if c["needs_review"]),
        "warnings": warnings,
        "flagged_clauses": flagged_clauses,
    }

print("\n4. Evaluating Test Kit Documents...")
test_docs = [
    TRAINING_SET_DIR / "DOC-01_freelance_agreement.txt",
    TRAINING_SET_DIR / "DOC-02_mutual_nda.txt",
    TRAINING_SET_DIR / "DOC-03_residential_lease.txt",
    TRAINING_SET_DIR / "DOC-04_employment_offer.txt",
    TRAINING_SET_DIR / "DOC-05_saas_msa.txt",
    TRAINING_SET_DIR / "DOC-06_consulting_traps.txt",
    TRAINING_SET_DIR / "DOC-07_not_a_contract.txt",
    TRAINING_SET_DIR / "DOC-08_partnership_compound.txt",
]

results = {}
for doc_path in test_docs:
    if doc_path.exists():
        res = analyze_document(doc_path)
        results[doc_path.name] = res
        print(f"\n--- {doc_path.name} ({res['total_units']} units) ---")
        print(f"  Avg Top Prob: {res['doc_avg_top_prob']:.4f} (Threshold: < {threshold_top_prob:.4f})")
        print(f"  SBERT Dist:   {res['doc_sbert_dist']:.4f} (Threshold: > {threshold_sbert_dist:.4f})")
        print(f"  Flags:        {res['total_flagged']} (Needs Review: {res['needs_review_count']})")
        if res["warnings"]:
            for w in res["warnings"]:
                print(f"  ⚠️  WARNING: {w}")
        else:
            print("  ✅ Status: In-distribution commercial agreement.")
        for fc in res["flagged_clauses"]:
            nr_tag = " [NEEDS REVIEW]" if fc["needs_review"] else ""
            print(f"     • {fc['label']} (conf: {fc['confidence']:.4f}){nr_tag} -> \"{fc['text_snippet']}...\"")

with open(ARTIFACTS_DIR / "uncertainty_and_ood_results.json", "w") as f:
    json.dump({
        "validation_stats": {
            "chosen_cutoff": chosen_cutoff,
            "needs_review_count": nr_count,
            "needs_review_share": nr_share,
            "needs_review_precision_flagged": nr_prec_fl,
            "needs_review_precision_correct": nr_prec_co,
            "high_conf_precision_flagged": hc_prec_fl,
            "high_conf_precision_correct": hc_prec_co,
            "threshold_top_prob": threshold_top_prob,
            "threshold_sbert_dist": threshold_sbert_dist,
            "mean_top_prob": mean_top_prob,
            "std_top_prob": std_top_prob,
            "mean_sbert_dist": mean_sbert_dist,
            "std_sbert_dist": std_sbert_dist,
        },
        "documents": results,
    }, f, indent=2)

print("\nSaved full evaluation to ml/artifacts/uncertainty_and_ood_results.json")

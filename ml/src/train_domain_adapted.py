"""Domain adaptation and fine-tuning on 2023 legal corpus with model drift tracking.

Pipeline:
1. Ingest all 400 PDF case law judgment files from /Users/chetanajatpur/Desktop/2023.
2. Continual pre-training (Masked Language Modeling) on Legal-BERT tracking gradient norms & loss.
3. Fine-tuning on CUAD contract risk classification tracking gradients and validation F1.
4. Comprehensive evaluation and model drift quantification against baseline Legal-BERT.
"""
import glob
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
from pypdf import PdfReader
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoConfig,
    AutoModelForMaskedLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    get_linear_schedule_with_warmup,
)

# ---------------------------------------------------------------------------
# Directories & Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
CORPUS_DIR = Path("/Users/chetanajatpur/Desktop/2023")
BACKBONE_DIR = ARTIFACTS_DIR / "legal_bert_adapted_backbone"
ADAPTED_MODEL_DIR = ARTIFACTS_DIR / "legal_bert_adapted"
BASELINE_MODEL_DIR = ARTIFACTS_DIR / "legal_bert"

SEED = 42


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Device: CUDA ({torch.cuda.get_device_name(0)})", flush=True)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Device: Apple Silicon Metal Performance Shaders (MPS)", flush=True)
    else:
        device = torch.device("cpu")
        print("Device: CPU", flush=True)
    return device


# ---------------------------------------------------------------------------
# Step 1: Ingestion & Text Extraction from 400 PDFs
# ---------------------------------------------------------------------------
def extract_corpus_passages(corpus_dir: Path, max_passages_per_doc: int = 6) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract representative legal passages from EVERY single PDF in corpus."""
    files = sorted(glob.glob(str(corpus_dir / "*.PDF")))
    print(f"\n[Ingestion] Scanning {len(files)} Indian Supreme Court 2023 judgment files...", flush=True)
    
    all_passages: list[dict[str, Any]] = []
    ood_test_passages: list[dict[str, Any]] = []
    
    start_time = time.time()
    for doc_idx, file_path in enumerate(files):
        doc_name = Path(file_path).name
        try:
            reader = PdfReader(file_path)
            num_pages = len(reader.pages)
            doc_passages: list[str] = []
            
            # Extract text page by page
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                # Split roughly into paragraphs/passages
                paras = re.split(r"\n\s*\n|\n(?=[0-9]{1,3}\.\s)", text)
                for p in paras:
                    clean = " ".join(p.split())
                    # Keep substantive legal paragraphs (between 120 and 800 characters)
                    if 120 <= len(clean) <= 900:
                        # Exclude pure header/court title noise
                        if not any(header in clean.lower() for header in ["reportable", "criminal appellate jurisdiction", "arising out of s.l.p."]):
                            doc_passages.append(clean)
            
            if doc_passages:
                # Sample diverse passages across the document
                step = max(1, len(doc_passages) // max_passages_per_doc)
                selected = doc_passages[::step][:max_passages_per_doc]
                
                # Assign 1 held-out passage for out-of-distribution drift testing
                if len(selected) > 1:
                    ood_test_passages.append({
                        "doc_name": doc_name,
                        "text": selected[-1],
                        "page_count": num_pages,
                    })
                    train_selected = selected[:-1]
                else:
                    train_selected = selected
                
                for p_idx, text in enumerate(train_selected):
                    all_passages.append({
                        "doc_name": doc_name,
                        "passage_idx": p_idx,
                        "text": text,
                    })
        except Exception as e:
            print(f"Warning: Failed reading {doc_name}: {e}", flush=True)
            
        if (doc_idx + 1) % 50 == 0 or (doc_idx + 1) == len(files):
            print(f"  Ingested [{doc_idx + 1:3d}/{len(files)}] files | Collected {len(all_passages)} training passages, {len(ood_test_passages)} OOD test passages", flush=True)
            
    dur = time.time() - start_time
    print(f"[Ingestion Complete] Ingested all {len(files)} files in {dur:.2f}s.", flush=True)
    print(f"  Total MLM training passages: {len(all_passages)}")
    print(f"  Total held-out OOD test passages: {len(ood_test_passages)}\n", flush=True)
    return all_passages, ood_test_passages


# ---------------------------------------------------------------------------
# Step 2: Continual Pre-Training with Masked Language Modeling
# ---------------------------------------------------------------------------
class TextMLMDataset(Dataset):
    """Dataset for MLM pre-training."""
    def __init__(self, texts: list[str], tokenizer: AutoTokenizer, max_len: int = 128):
        self.encodings = tokenizer(
            texts,
            max_length=max_len,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

    def __len__(self) -> int:
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
        }


def train_mlm_domain_adaptation(
    passages: list[dict[str, Any]],
    tokenizer: AutoTokenizer,
    device: torch.device,
    epochs: int = 2,
    batch_size: int = 8,
    grad_accum_steps: int = 2,
    lr: float = 3e-5,
) -> dict[str, Any]:
    """Train Masked Language Model on the 2023 legal corpus, tracking gradients."""
    print("=" * 70, flush=True)
    print("PHASE 1: Continual Pre-training (Masked Language Modeling) on 2023 Legal Cases", flush=True)
    print("=" * 70, flush=True)
    
    random.shuffle(passages)
    val_split = max(100, int(len(passages) * 0.1))
    train_texts = [p["text"] for p in passages[:-val_split]]
    val_texts = [p["text"] for p in passages[-val_split:]]
    print(f"MLM Train samples: {len(train_texts)}, MLM Val samples: {len(val_texts)}", flush=True)
    
    train_ds = TextMLMDataset(train_texts, tokenizer, max_len=128)
    val_ds = TextMLMDataset(val_texts, tokenizer, max_len=128)
    
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=True, mlm_probability=0.15)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=data_collator)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=data_collator)
    
    print("Initializing AutoModelForMaskedLM from nlpaueb/legal-bert-base-uncased...", flush=True)
    mlm_model = AutoModelForMaskedLM.from_pretrained("nlpaueb/legal-bert-base-uncased")
    mlm_model.to(device)
    
    optimizer = torch.optim.AdamW(mlm_model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = (len(train_loader) // grad_accum_steps) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(total_steps * 0.1), num_training_steps=total_steps)
    
    history: dict[str, list[Any]] = {
        "step_loss": [],
        "step_grad_norm": [],
        "epoch_train_loss": [],
        "epoch_val_loss": [],
        "epoch_val_perplexity": [],
    }
    
    start_time = time.time()
    for epoch in range(epochs):
        mlm_model.train()
        running_loss = 0.0
        epoch_grad_norms = []
        optimizer.zero_grad()
        
        print(f"\n--- MLM Epoch {epoch + 1}/{epochs} ---", flush=True)
        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            
            outputs = mlm_model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            loss_to_backward = loss / grad_accum_steps
            loss_to_backward.backward()
            
            running_loss += loss.item()
            
            if (step + 1) % grad_accum_steps == 0 or (step + 1) == len(train_loader):
                grad_norm = torch.nn.utils.clip_grad_norm_(mlm_model.parameters(), max_norm=1.0)
                norm_val = float(grad_norm.item() if hasattr(grad_norm, "item") else grad_norm)
                epoch_grad_norms.append(norm_val)
                history["step_loss"].append(float(loss.item()))
                history["step_grad_norm"].append(norm_val)
                
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                
            if (step + 1) % 40 == 0 or (step + 1) == len(train_loader):
                avg_so_far = running_loss / (step + 1)
                last_norm = epoch_grad_norms[-1] if epoch_grad_norms else 0.0
                current_lr = scheduler.get_last_lr()[0]
                print(f"  Step [{step + 1:4d}/{len(train_loader):4d}] MLM Loss: {loss.item():.4f} | Running Avg: {avg_so_far:.4f} | Grad Norm: {last_norm:.4f} | LR: {current_lr:.2e}", flush=True)
                
        # Validation Perplexity
        mlm_model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = mlm_model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                val_loss += outputs.loss.item()
                
        avg_train_loss = running_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)
        val_perplexity = math.exp(min(avg_val_loss, 20.0))
        
        history["epoch_train_loss"].append(avg_train_loss)
        history["epoch_val_loss"].append(avg_val_loss)
        history["epoch_val_perplexity"].append(val_perplexity)
        
        print(f"MLM Epoch {epoch + 1} Summary: Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Perplexity: {val_perplexity:.2f}", flush=True)
        
    total_time = time.time() - start_time
    print(f"\n[MLM Complete] Continual pre-training finished in {total_time:.1f}s ({total_time / 60:.1f} min).", flush=True)
    
    # Save adapted backbone weights & config
    BACKBONE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving adapted backbone to {BACKBONE_DIR}...", flush=True)
    mlm_model.bert.save_pretrained(BACKBONE_DIR)
    tokenizer.save_pretrained(BACKBONE_DIR)
    
    # Clean memory
    del mlm_model
    if device.type == "mps":
        torch.mps.empty_cache()
        
    return history


# ---------------------------------------------------------------------------
# Step 3: Classifier Fine-Tuning with Adapted Backbone
# ---------------------------------------------------------------------------
class FastClauseDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer: AutoTokenizer, max_len: int = 256):
        encodings = tokenizer(texts, max_length=max_len, padding="max_length", truncation=True, return_tensors="pt")
        self.input_ids = encodings["input_ids"]
        self.attention_mask = encodings["attention_mask"]
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "label": self.labels[idx],
        }


def fine_tune_classifier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    label2id: dict[str, int],
    tokenizer: AutoTokenizer,
    device: torch.device,
    epochs: int = 3,
    batch_size: int = 8,
    grad_accum_steps: int = 2,
    lr: float = 2e-5,
) -> tuple[dict[str, Any], Path]:
    """Fine-tune classification head on top of the domain-adapted Legal-BERT backbone."""
    print("\n" + "=" * 70, flush=True)
    print("PHASE 2: Fine-Tuning Domain-Adapted Legal-BERT on Contract Clause Risk Dataset", flush=True)
    print("=" * 70, flush=True)
    
    # Compute inverse-frequency class weights
    counts = train_df["label"].value_counts()
    total = len(train_df)
    num_classes = len(label2id)
    weights = torch.zeros(num_classes, dtype=torch.float32)
    for label, idx in label2id.items():
        count = counts.get(label, 1)
        weights[idx] = total / (num_classes * count)
    weights = weights / weights.sum() * num_classes
    class_weights = weights.to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    
    print(f"Building DataLoaders (Train: {len(train_df)}, Val: {len(val_df)})...", flush=True)
    train_ds = FastClauseDataset(train_df["text"].tolist(), [label2id[l] for l in train_df["label"]], tokenizer)
    val_ds = FastClauseDataset(val_df["text"].tolist(), [label2id[l] for l in val_df["label"]], tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    
    print(f"Loading adapted backbone from {BACKBONE_DIR} into AutoModelForSequenceClassification...", flush=True)
    config = AutoConfig.from_pretrained("nlpaueb/legal-bert-base-uncased", num_labels=num_classes)
    model = AutoModelForSequenceClassification.from_pretrained(
        "nlpaueb/legal-bert-base-uncased",
        config=config,
    )
    # Load adapted bert encoder weights into classifier
    adapted_bert_state = torch.load(BACKBONE_DIR / "pytorch_model.bin", map_location="cpu") if (BACKBONE_DIR / "pytorch_model.bin").exists() else None
    if adapted_bert_state is None and (BACKBONE_DIR / "model.safetensors").exists():
        from safetensors.torch import load_file
        adapted_bert_state = load_file(BACKBONE_DIR / "model.safetensors")
        
    if adapted_bert_state:
        # Filter keys to match model.bert
        bert_keys = {k.replace("bert.", ""): v for k, v in adapted_bert_state.items() if not k.startswith("cls.")}
        msg = model.bert.load_state_dict(bert_keys, strict=False)
        print(f"Loaded adapted weights into model.bert: {len(bert_keys)} parameters loaded ({msg})", flush=True)
        
    model.to(device)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = (len(train_loader) // grad_accum_steps) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(total_steps * 0.1), num_training_steps=total_steps)
    
    history: dict[str, list[Any]] = {
        "step_loss": [],
        "step_grad_norm": [],
        "epoch_train_loss": [],
        "epoch_val_loss": [],
        "epoch_val_f1": [],
        "epoch_val_acc": [],
    }
    
    best_val_f1 = -1.0
    ADAPTED_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        epoch_grad_norms = []
        optimizer.zero_grad()
        
        print(f"\n--- Classifier Fine-Tuning Epoch {epoch + 1}/{epochs} ---", flush=True)
        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = criterion(outputs.logits, labels)
            loss_to_backward = loss / grad_accum_steps
            loss_to_backward.backward()
            
            running_loss += loss.item()
            
            if (step + 1) % grad_accum_steps == 0 or (step + 1) == len(train_loader):
                grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                norm_val = float(grad_norm.item() if hasattr(grad_norm, "item") else grad_norm)
                epoch_grad_norms.append(norm_val)
                history["step_loss"].append(float(loss.item()))
                history["step_grad_norm"].append(norm_val)
                
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                
            if (step + 1) % 50 == 0 or (step + 1) == len(train_loader):
                avg_so_far = running_loss / (step + 1)
                last_norm = epoch_grad_norms[-1] if epoch_grad_norms else 0.0
                current_lr = scheduler.get_last_lr()[0]
                print(f"  Step [{step + 1:4d}/{len(train_loader):4d}] Loss: {loss.item():.4f} | Running Avg: {avg_so_far:.4f} | Grad Norm: {last_norm:.4f} | LR: {current_lr:.2e}", flush=True)
                
        # Validation
        model.eval()
        val_loss = 0.0
        val_preds, val_targets = [], []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["label"].to(device)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = criterion(outputs.logits, labels)
                val_loss += loss.item()
                preds = outputs.logits.argmax(dim=-1).cpu().tolist()
                val_preds.extend(preds)
                val_targets.extend(labels.cpu().tolist())
                
        avg_train_loss = running_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)
        val_acc = float(accuracy_score(val_targets, val_preds))
        val_f1 = float(f1_score(val_targets, val_preds, average="macro", zero_division=0))
        
        history["epoch_train_loss"].append(avg_train_loss)
        history["epoch_val_loss"].append(avg_val_loss)
        history["epoch_val_f1"].append(val_f1)
        history["epoch_val_acc"].append(val_acc)
        
        print(f"Epoch {epoch + 1} Eval: Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:.4f} | Val Macro-F1: {val_f1:.4f}", flush=True)
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            print(f"--> New best model found (Macro-F1 {val_f1:.4f}). Saving to {ADAPTED_MODEL_DIR}...", flush=True)
            model.save_pretrained(ADAPTED_MODEL_DIR)
            tokenizer.save_pretrained(ADAPTED_MODEL_DIR)
            
    print(f"\n[Fine-Tuning Complete] Best Validation Macro-F1: {best_val_f1:.4f}", flush=True)
    return history, ADAPTED_MODEL_DIR


# ---------------------------------------------------------------------------
# Step 4: Rigorous Evaluation & Model Drift Analysis
# ---------------------------------------------------------------------------
def compute_entropy(probs: np.ndarray) -> np.ndarray:
    """Compute Shannon entropy H(p) in bits."""
    eps = 1e-12
    p_clamped = np.clip(probs, eps, 1.0)
    return -np.sum(p_clamped * np.log2(p_clamped), axis=-1)


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Compute mean Kullback-Leibler divergence D_KL(P || Q) in bits."""
    eps = 1e-12
    p_c = np.clip(p, eps, 1.0)
    q_c = np.clip(q, eps, 1.0)
    return float(np.mean(np.sum(p_c * np.log2(p_c / q_c), axis=-1)))


def run_model_inference(
    model: AutoModelForSequenceClassification,
    tokenizer: AutoTokenizer,
    texts: list[str],
    device: torch.device,
    batch_size: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """Return predicted class IDs and softmax probability matrix."""
    model.eval()
    all_preds = []
    all_probs = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        encodings = tokenizer(batch, max_length=256, padding=True, truncation=True, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**encodings).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            preds = np.argmax(probs, axis=-1)
            all_preds.extend(preds)
            all_probs.extend(probs)
            
    return np.array(all_preds), np.array(all_probs)


def evaluate_and_measure_drift(
    test_df: pd.DataFrame,
    ood_passages: list[dict[str, Any]],
    label2id: dict[str, int],
    id2label: dict[int, str],
    device: torch.device,
    mlm_history: dict[str, Any],
    cls_history: dict[str, Any],
) -> dict[str, Any]:
    """Run rigorous benchmark evaluation and quantify model drift against baseline."""
    print("\n" + "=" * 70, flush=True)
    print("PHASE 3: Comprehensive Benchmark Evaluation & Model Drift Quantification", flush=True)
    print("=" * 70, flush=True)
    
    # 1. Load models
    tokenizer = AutoTokenizer.from_pretrained(BASELINE_MODEL_DIR)
    print(f"Loading Baseline Legal-BERT from {BASELINE_MODEL_DIR}...", flush=True)
    baseline_model = AutoModelForSequenceClassification.from_pretrained(BASELINE_MODEL_DIR).to(device)
    
    print(f"Loading Adapted Legal-BERT from {ADAPTED_MODEL_DIR}...", flush=True)
    adapted_model = AutoModelForSequenceClassification.from_pretrained(ADAPTED_MODEL_DIR).to(device)
    
    test_texts = test_df["text"].tolist()
    test_true = [label2id[l] for l in test_df["label"]]
    
    # 2. Run inference on CUAD test set
    print("Evaluating Baseline Legal-BERT on CUAD test set...", flush=True)
    b_preds, b_probs = run_model_inference(baseline_model, tokenizer, test_texts, device)
    
    print("Evaluating Domain-Adapted Legal-BERT on CUAD test set...", flush=True)
    a_preds, a_probs = run_model_inference(adapted_model, tokenizer, test_texts, device)
    
    # Calculate Test Metrics
    classes = [id2label[i] for i in range(len(label2id))]
    
    b_acc = float(accuracy_score(test_true, b_preds))
    b_f1 = float(f1_score(test_true, b_preds, average="macro", zero_division=0))
    b_prec = float(precision_score(test_true, b_preds, average="macro", zero_division=0))
    b_rec = float(recall_score(test_true, b_preds, average="macro", zero_division=0))
    
    a_acc = float(accuracy_score(test_true, a_preds))
    a_f1 = float(f1_score(test_true, a_preds, average="macro", zero_division=0))
    a_prec = float(precision_score(test_true, a_preds, average="macro", zero_division=0))
    a_rec = float(recall_score(test_true, a_preds, average="macro", zero_division=0))
    
    a_report = classification_report(test_true, a_preds, target_names=classes, output_dict=True, zero_division=0)
    
    # 3. In-Domain Model Drift Metrics (CUAD Test Set)
    test_agreement = float(np.mean(b_preds == a_preds))
    test_kl = kl_divergence(b_probs, a_probs)
    b_test_entropy = float(np.mean(compute_entropy(b_probs)))
    a_test_entropy = float(np.mean(compute_entropy(a_probs)))
    b_test_conf = float(np.mean(np.max(b_probs, axis=-1)))
    a_test_conf = float(np.mean(np.max(a_probs, axis=-1)))
    
    # 4. Out-of-Distribution Drift Evaluation on 2023 Supreme Court Opinions
    print(f"\nRunning Out-of-Distribution (OOD) Drift Analysis on {len(ood_passages)} held-out 2023 court passages...", flush=True)
    ood_texts = [p["text"] for p in ood_passages]
    b_ood_preds, b_ood_probs = run_model_inference(baseline_model, tokenizer, ood_texts, device)
    a_ood_preds, a_ood_probs = run_model_inference(adapted_model, tokenizer, ood_texts, device)
    
    ood_agreement = float(np.mean(b_ood_preds == a_ood_preds))
    ood_kl = kl_divergence(b_ood_probs, a_ood_probs)
    b_ood_entropy = float(np.mean(compute_entropy(b_ood_probs)))
    a_ood_entropy = float(np.mean(compute_entropy(a_ood_probs)))
    b_ood_conf = float(np.mean(np.max(b_ood_probs, axis=-1)))
    a_ood_conf = float(np.mean(np.max(a_ood_probs, axis=-1)))
    
    # Court case opinions do not contain commercial contract liabilities.
    # Therefore, classifying judicial text as high-risk contract clauses (like Non-Compete, Uncapped Liability) represents false positive drift.
    no_clause_id = label2id.get("No Clause", 0)
    b_ood_no_clause_pct = float(np.mean(b_ood_preds == no_clause_id))
    a_ood_no_clause_pct = float(np.mean(a_ood_preds == no_clause_id))
    
    # High risk classes: Uncapped Liability, Non-Compete, Liquidated Damages
    high_risk_ids = [label2id[c] for c in ["Uncapped Liability", "Non-Compete", "Liquidated Damages"] if c in label2id]
    b_ood_high_risk_false_alarms = float(np.mean(np.isin(b_ood_preds, high_risk_ids)))
    a_ood_high_risk_false_alarms = float(np.mean(np.isin(a_ood_preds, high_risk_ids)))
    
    # Results dictionary
    results = {
        "benchmark_evaluation": {
            "test_samples": len(test_df),
            "baseline": {
                "accuracy": round(b_acc, 4),
                "macro_f1": round(b_f1, 4),
                "macro_precision": round(b_prec, 4),
                "macro_recall": round(b_rec, 4),
            },
            "domain_adapted": {
                "accuracy": round(a_acc, 4),
                "macro_f1": round(a_f1, 4),
                "macro_precision": round(a_prec, 4),
                "macro_recall": round(a_rec, 4),
            },
            "delta": {
                "accuracy_change": round(a_acc - b_acc, 4),
                "macro_f1_change": round(a_f1 - b_f1, 4),
                "macro_precision_change": round(a_prec - b_prec, 4),
                "macro_recall_change": round(a_rec - b_rec, 4),
            },
            "per_class": {
                cls_name: {
                    "precision": round(a_report[cls_name]["precision"], 4),
                    "recall": round(a_report[cls_name]["recall"], 4),
                    "f1": round(a_report[cls_name]["f1-score"], 4),
                    "support": int(a_report[cls_name]["support"]),
                }
                for cls_name in classes
            },
        },
        "model_drift_analysis": {
            "in_domain_covenant_test": {
                "prediction_agreement_rate": round(test_agreement, 4),
                "kl_divergence_bits": round(test_kl, 4),
                "baseline_mean_entropy": round(b_test_entropy, 4),
                "adapted_mean_entropy": round(a_test_entropy, 4),
                "baseline_mean_confidence": round(b_test_conf, 4),
                "adapted_mean_confidence": round(a_test_conf, 4),
            },
            "out_of_distribution_2023_court_corpus": {
                "ood_samples_evaluated": len(ood_passages),
                "prediction_agreement_rate": round(ood_agreement, 4),
                "kl_divergence_bits": round(ood_kl, 4),
                "baseline_mean_entropy": round(b_ood_entropy, 4),
                "adapted_mean_entropy": round(a_ood_entropy, 4),
                "baseline_mean_confidence": round(b_ood_conf, 4),
                "adapted_mean_confidence": round(a_ood_conf, 4),
                "baseline_no_clause_rate": round(b_ood_no_clause_pct, 4),
                "adapted_no_clause_rate": round(a_ood_no_clause_pct, 4),
                "baseline_high_risk_false_alarm_rate": round(b_ood_high_risk_false_alarms, 4),
                "adapted_high_risk_false_alarm_rate": round(a_ood_high_risk_false_alarms, 4),
            },
        },
        "training_gradients_and_losses": {
            "mlm_mean_step_loss": round(float(np.mean(mlm_history["step_loss"])), 4),
            "mlm_mean_grad_norm": round(float(np.mean(mlm_history["step_grad_norm"])), 4),
            "mlm_max_grad_norm": round(float(np.max(mlm_history["step_grad_norm"])), 4),
            "classifier_mean_step_loss": round(float(np.mean(cls_history["step_loss"])), 4),
            "classifier_mean_grad_norm": round(float(np.mean(cls_history["step_grad_norm"])), 4),
            "classifier_max_grad_norm": round(float(np.max(cls_history["step_grad_norm"])), 4),
        },
    }
    
    # Save JSON report
    drift_report_path = ARTIFACTS_DIR / "drift_report.json"
    with open(drift_report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved drift report to {drift_report_path}", flush=True)
    
    # Update metrics.json
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            full_metrics = json.load(f)
    else:
        full_metrics = {}
    full_metrics["legal_bert_domain_adapted"] = {
        "test": results["benchmark_evaluation"]["domain_adapted"],
        "delta_vs_baseline": results["benchmark_evaluation"]["delta"],
        "per_class": results["benchmark_evaluation"]["per_class"],
        "drift": results["model_drift_analysis"],
    }
    with open(metrics_path, "w") as f:
        json.dump(full_metrics, f, indent=2)
    print(f"Updated {metrics_path} with domain-adapted metrics.", flush=True)
    
    # 5. Visual Plots: Training Loss & Gradient Norms
    plt.figure(figsize=(14, 5))
    
    plt.subplot(1, 2, 1)
    plt.plot(mlm_history["step_loss"], label="MLM Step Loss", color="#0284c7", alpha=0.6)
    # Moving average
    window = min(30, len(mlm_history["step_loss"]))
    if window > 1:
        ma = np.convolve(mlm_history["step_loss"], np.ones(window) / window, mode="valid")
        plt.plot(range(window - 1, len(mlm_history["step_loss"])), ma, label="Moving Avg Loss", color="#0369a1", linewidth=2)
    plt.title("Continual Pre-training (MLM) Loss", fontsize=12, fontweight="bold")
    plt.xlabel("Optimization Steps")
    plt.ylabel("Cross-Entropy Loss")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    
    plt.subplot(1, 2, 2)
    plt.plot(mlm_history["step_grad_norm"], label="Gradient L2 Norm", color="#d97706", alpha=0.7)
    plt.axhline(1.0, color="red", linestyle="--", label="Grad Clip Threshold (1.0)")
    plt.title("MLM Gradient L2 Norm Tracking", fontsize=12, fontweight="bold")
    plt.xlabel("Optimization Steps")
    plt.ylabel("Norm Value")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    
    plt.tight_layout()
    plot_path = ARTIFACTS_DIR / "mlm_gradient_loss_curve.png"
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"Saved gradient loss curve to {plot_path}", flush=True)
    
    # Visual Plots: Confusion Matrix
    cm = confusion_matrix(test_true, a_preds)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=classes, yticklabels=classes)
    plt.title("Confusion Matrix - Domain-Adapted Legal-BERT", fontsize=14, fontweight="bold")
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    cm_path = ARTIFACTS_DIR / "confusion_matrix_domain_adapted.png"
    plt.savefig(cm_path, dpi=200)
    plt.close()
    print(f"Saved confusion matrix to {cm_path}", flush=True)
    
    return results


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    set_seed(SEED)
    device = get_device()
    
    print("\n" + "=" * 70)
    print("CLAUSEGUARD: LEGAL-BERT DOMAIN ADAPTATION & MODEL DRIFT PIPELINE")
    print("Corpus: 400 Indian Supreme Court 2023 Judgment Files")
    print("=" * 70)
    
    # Check data files
    train_csv = PROCESSED_DIR / "train.csv"
    val_csv = PROCESSED_DIR / "val.csv"
    test_csv = PROCESSED_DIR / "test.csv"
    label_map_file = ARTIFACTS_DIR / "label_map.json"
    
    if not (train_csv.exists() and val_csv.exists() and test_csv.exists() and label_map_file.exists()):
        print("Error: Missing processed contract dataset or label map in data/processed or artifacts/.")
        sys.exit(1)
        
    train_df = pd.read_csv(train_csv)
    val_df = pd.read_csv(val_csv)
    test_df = pd.read_csv(test_csv)
    with open(label_map_file) as f:
        lmap = json.load(f)
    label2id = {k: int(v) for k, v in lmap["label2id"].items()}
    id2label = {int(k): v for k, v in lmap["id2label"].items()}
    
    # 1. Extract passages from all 400 files
    passages, ood_passages = extract_corpus_passages(CORPUS_DIR, max_passages_per_doc=6)
    
    # 2. Continual Pre-Training with Masked Language Modeling
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    mlm_history = train_mlm_domain_adaptation(
        passages=passages,
        tokenizer=tokenizer,
        device=device,
        epochs=2,
        batch_size=8,
        grad_accum_steps=2,
        lr=3e-5,
    )
    
    # 3. Fine-Tuning Classifier
    cls_history, _ = fine_tune_classifier(
        train_df=train_df,
        val_df=val_df,
        label2id=label2id,
        tokenizer=tokenizer,
        device=device,
        epochs=3,
        batch_size=8,
        grad_accum_steps=2,
        lr=2e-5,
    )
    
    # 4. Rigorous Evaluation & Drift Quantification
    results = evaluate_and_measure_drift(
        test_df=test_df,
        ood_passages=ood_passages,
        label2id=label2id,
        id2label=id2label,
        device=device,
        mlm_history=mlm_history,
        cls_history=cls_history,
    )
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS SUMMARY")
    print("=" * 70)
    bench = results["benchmark_evaluation"]
    print(f"Accuracy:        {bench['domain_adapted']['accuracy'] * 100:.2f}% (Baseline: {bench['baseline']['accuracy'] * 100:.2f}%, Delta: {bench['delta']['accuracy_change'] * 100:+.2f}%)")
    print(f"Macro-F1 Score:  {bench['domain_adapted']['macro_f1'] * 100:.2f}% (Baseline: {bench['baseline']['macro_f1'] * 100:.2f}%, Delta: {bench['delta']['macro_f1_change'] * 100:+.2f}%)")
    print(f"Macro-Precision: {bench['domain_adapted']['macro_precision'] * 100:.2f}% (Baseline: {bench['baseline']['macro_precision'] * 100:.2f}%, Delta: {bench['delta']['macro_precision_change'] * 100:+.2f}%)")
    print(f"Macro-Recall:    {bench['domain_adapted']['macro_recall'] * 100:.2f}% (Baseline: {bench['baseline']['macro_recall'] * 100:.2f}%, Delta: {bench['delta']['macro_recall_change'] * 100:+.2f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()

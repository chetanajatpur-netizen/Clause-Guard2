"""Clause classification using fine-tuned Legal-BERT."""
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.core.risk_map import RISK_MAP

logger = logging.getLogger(__name__)

# Scoped Liability Guard Rule:
# Within one sentence, the word 'liability' (or 'liable') within 150 characters of any of:
# 'not be subject to any limit', 'without limitation as to amount', 'unlimited liability'.
# Excludes 'including but not limited to' and 'without limiting'.
SCOPED_UNLIMITED_PHRASES = [
    "not be subject to any limit",
    "without limitation as to amount",
    "unlimited liability",
]
RESTRICTED_LIABILITY_PHRASES = SCOPED_UNLIMITED_PHRASES


def apply_liability_guard(
    pred_label: str, text: str, enabled: Optional[bool] = None
) -> str:
    """If predicted as Cap on Liability, check for explicit waivers of liability limits."""
    if enabled is None:
        try:
            from app.config import settings

            enabled = getattr(settings, "enable_liability_guard", True)
        except Exception:
            enabled = True

    if not enabled or pred_label != "Cap on Liability":
        return pred_label

    sentences = re.split(r"(?<=[.!?])\s+", str(text))
    for sent in sentences:
        # Exclude boilerplate non-limiting clauses
        cleaned = re.sub(r"(?i)\bincluding\s*,?\s*but\s+not\s+limited\s+to\b", " ", sent)
        cleaned = re.sub(r"(?i)\bwithout\s+limiting\b", " ", cleaned)

        liab_matches = list(re.finditer(r"(?i)\b(liability|liable)\b", cleaned))
        if not liab_matches:
            continue

        for phrase in SCOPED_UNLIMITED_PHRASES:
            for p_match in re.finditer(re.escape(phrase), cleaned, re.IGNORECASE):
                for l_match in liab_matches:
                    if abs(l_match.start() - p_match.start()) <= 150:
                        return "Uncapped Liability"
    return pred_label


class ClauseClassifier:
    """Singleton classifier using fine-tuned Legal-BERT or TF-IDF+LogReg baseline.
    
    Loaded once at app startup via FastAPI lifespan.
    """

    def __init__(self) -> None:
        self.backend: str = "legal_bert"
        self.model: AutoModelForSequenceClassification | None = None
        self.tokenizer: AutoTokenizer | None = None
        self.id2label: dict[int, str] = {}
        self.label2id: dict[str, int] = {}
        self.no_clause_idx: int = 0
        self.sub_indices: list[int] = []
        self.sub_names: list[str] = []
        self.device: torch.device = torch.device("cpu")
        self.temperature: float = 0.9270
        self.presets: dict[str, Any] = {
            "strict": {"target_fa_per_contract": 3, "tau": 0.012957},
            "balanced": {"target_fa_per_contract": 8, "tau": 0.035452},
            "thorough": {"target_fa_per_contract": 12, "tau": 0.071850},
        }
        self.default_sensitivity: str = "balanced"
        self.vectorizer: Any = None
        self.clf: Any = None
        self.classes: list[str] = []
        self._loaded = False

    def load(
        self,
        model_path: str = "ml/artifacts/legal_bert_final",
        label_map_path: str = "ml/artifacts/label_map.json",
        backend: str = "legal_bert",
        baseline_model_path: str = "ml/artifacts/baseline_model.joblib",
        temperature: float = 0.9270,
        operating_points_path: str = "ml/artifacts/operating_points.json",
    ) -> None:
        """Load model, tokenizer, label map, and operating point presets from disk.
        
        Args:
            model_path: Path to saved Legal-BERT model directory.
            label_map_path: Path to label_map.json.
            backend: Classifier backend ('legal_bert' or 'baseline').
            baseline_model_path: Path to baseline_model.joblib.
            temperature: Calibration temperature T.
            operating_points_path: Path to operating_points.json.
        """
        self.backend = backend.lower()
        self.temperature = float(temperature)

        # Load operating points presets if available
        op_path = self._resolve_file_path(operating_points_path)
        if op_path and op_path.exists():
            try:
                with open(op_path) as f:
                    op_data = json.load(f)
                if "presets" in op_data:
                    self.presets = op_data["presets"]
                if "temperature" in op_data:
                    self.temperature = float(op_data["temperature"])
                logger.info("Loaded operating points presets from %s (T=%.4f)", op_path, self.temperature)
            except Exception as e:
                logger.warning("Failed to load operating points from %s: %s", op_path, e)

        if self.backend == "baseline":
            self._load_baseline(baseline_model_path)
        else:
            self._load_legal_bert(model_path, label_map_path)

    @staticmethod
    def _resolve_file_path(path_str: str) -> Optional[Path]:
        p = Path(path_str)
        if p.exists():
            return p
        candidate = Path(__file__).resolve().parent.parent.parent.parent / path_str
        if candidate.exists():
            return candidate
        return p

    def _load_baseline(self, baseline_model_path: str) -> None:
        import joblib

        bm_path = self._resolve_file_path(baseline_model_path)
        bm_path_str = str(bm_path.resolve()) if bm_path and bm_path.exists() else baseline_model_path
        logger.info("Loading baseline classifier from %s", bm_path_str)
        if not Path(bm_path_str).exists():
            raise FileNotFoundError(f"Baseline model not found at {bm_path_str}")

        data = joblib.load(bm_path_str)
        self.vectorizer = data["vectorizer"]
        self.clf = data["classifier"]
        self.classes = list(data.get("classes", self.clf.classes_))
        self._loaded = True
        logger.info("Baseline classifier loaded: %d classes", len(self.classes))

    def _load_legal_bert(self, model_path: str, label_map_path: str) -> None:
        m_path = self._resolve_file_path(model_path)
        lm_path = self._resolve_file_path(label_map_path)

        model_path_str = str(m_path.resolve()) if m_path and m_path.exists() else model_path
        label_map_str = str(lm_path.resolve()) if lm_path and lm_path.exists() else label_map_path

        logger.info("Loading classifier model from %s", model_path_str)
        
        self.device = self._get_device()
        self.tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path_str)
        self.model.to(self.device)
        self.model.eval()
        
        # Load label map
        with open(label_map_str) as f:
            label_data = json.load(f)
        self.id2label = {int(k): v for k, v in label_data["id2label"].items()}
        self.label2id = {v: int(k) for k, v in self.id2label.items()}
        self.no_clause_idx = self.label2id.get("No Clause", 0)
        self.sub_indices = [i for i in range(len(self.id2label)) if i != self.no_clause_idx]
        self.sub_names = [self.id2label[i] for i in self.sub_indices]

        self._loaded = True
        logger.info(
            "Classifier loaded: %d labels, device=%s, T=%.4f",
            len(self.id2label),
            self.device,
            self.temperature,
        )

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._loaded

    def predict(
        self,
        texts: list[str],
        sensitivity: str = "balanced",
        max_len: int = 256,
        batch_size: int = 16,
    ) -> list[dict[str, Any]]:
        """Classify a list of text chunks with calibrated operating point thresholding.
        
        Args:
            texts: List of clause texts to classify.
            sensitivity: Operating point preset ('strict', 'balanced', or 'thorough').
            max_len: Maximum token length.
            batch_size: Inference batch size.
        
        Returns:
            List of dicts with 'flagged', 'label', 'risk_tier', 'calibrated_probability', 'confidence'.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        if not texts:
            return []

        preset = self.presets.get(sensitivity.lower(), self.presets.get("balanced", {"tau": 0.035452}))
        tau = preset["tau"]

        if self.backend == "baseline":
            return self._predict_baseline(texts, tau=tau)
        else:
            return self._predict_legal_bert(texts, tau=tau, max_len=max_len, batch_size=batch_size)

    def _predict_baseline(self, texts: list[str], tau: float = 0.035452) -> list[dict[str, Any]]:
        X = self.vectorizer.transform(texts)
        probs = self.clf.predict_proba(X)
        results: list[dict[str, Any]] = []

        no_clause_col = self.classes.index("No Clause") if "No Clause" in self.classes else -1

        for idx_text, p in enumerate(probs):
            if no_clause_col >= 0:
                p_no_clause = float(p[no_clause_col])
                flagged = bool(p_no_clause < tau)
                if flagged:
                    # Pick max among non-No Clause
                    sub_p = [(c, float(prob)) for c, prob in zip(self.classes, p) if c != "No Clause"]
                    pred_label, conf = max(sub_p, key=lambda x: x[1])
                    pred_label = apply_liability_guard(pred_label, texts[idx_text])
                    risk_tier = RISK_MAP.get(pred_label, "None")
                else:
                    pred_label = "No Clause"
                    conf = p_no_clause
                    risk_tier = "None"
            else:
                pred_idx = int(p.argmax())
                pred_label = self.classes[pred_idx]
                conf = float(p[pred_idx])
                pred_label = apply_liability_guard(pred_label, texts[idx_text])
                flagged = pred_label != "No Clause"
                risk_tier = RISK_MAP.get(pred_label, "None")

            results.append({
                "flagged": flagged,
                "label": pred_label,
                "risk_tier": risk_tier,
                "calibrated_probability": round(conf, 4),
                "confidence": round(conf, 4),
                "type_uncertain": bool(flagged and conf < 0.65),
            })
        logger.info("Classified %d clauses with baseline", len(results))
        return results

    def _predict_legal_bert(
        self,
        texts: list[str],
        tau: float = 0.035452,
        max_len: int = 256,
        batch_size: int = 16,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            encoding = self.tokenizer(
                batch,
                max_length=max_len,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**encoding)
                scaled_logits = outputs.logits / self.temperature
                probs = torch.nn.functional.softmax(scaled_logits, dim=-1)
            
            probs_cpu = probs.cpu().numpy()
            for j, row in enumerate(probs_cpu):
                p_no_clause = float(row[self.no_clause_idx])
                flagged = bool(p_no_clause < tau)

                if flagged:
                    sub_vals = row[self.sub_indices]
                    pred_sub_idx = int(sub_vals.argmax())
                    pred_label = self.sub_names[pred_sub_idx]
                    cal_prob = float(sub_vals[pred_sub_idx])

                    # Apply liability guard
                    pred_label = apply_liability_guard(pred_label, batch[j])
                    risk_tier = RISK_MAP.get(pred_label, "None")
                else:
                    pred_label = "No Clause"
                    risk_tier = "None"
                    cal_prob = p_no_clause

                results.append({
                    "flagged": flagged,
                    "label": pred_label,
                    "risk_tier": risk_tier,
                    "calibrated_probability": round(cal_prob, 4),
                    "confidence": round(cal_prob, 4),
                    "type_uncertain": bool(flagged and cal_prob < 0.65),
                })
        
        logger.info("Classified %d clauses with legal_bert (tau=%.6f)", len(results), tau)
        return results

    @staticmethod
    def _get_device() -> torch.device:
        """Get inference device respecting architecture.md CPU rule and config settings."""
        try:
            from app.config import settings
            configured = getattr(settings, "device", "cpu").lower()
            if configured == "cuda" and torch.cuda.is_available():
                return torch.device("cuda")
            if configured == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
        except Exception:  # noqa: BLE001
            pass
        return torch.device("cpu")


# Singleton instance
classifier = ClauseClassifier()

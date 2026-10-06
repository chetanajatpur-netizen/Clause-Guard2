"""Clause classification using fine-tuned Legal-BERT."""
import json
import logging
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class ClauseClassifier:
    """Singleton classifier using fine-tuned Legal-BERT.
    
    Loaded once at app startup via FastAPI lifespan.
    """

    def __init__(self) -> None:
        self.model: AutoModelForSequenceClassification | None = None
        self.tokenizer: AutoTokenizer | None = None
        self.id2label: dict[int, str] = {}
        self.device: torch.device = torch.device("cpu")
        self._loaded = False

    def load(self, model_path: str, label_map_path: str) -> None:
        """Load model, tokenizer, and label map from disk.
        
        Args:
            model_path: Path to saved model directory.
            label_map_path: Path to label_map.json.
        """
        # Resolve path relative to project root if not found in CWD
        m_path = Path(model_path)
        if not m_path.exists():
            candidate = Path(__file__).resolve().parent.parent.parent.parent / model_path
            if candidate.exists():
                m_path = candidate
        
        lm_path = Path(label_map_path)
        if not lm_path.exists():
            candidate = Path(__file__).resolve().parent.parent.parent.parent / label_map_path
            if candidate.exists():
                lm_path = candidate

        model_path_str = str(m_path.resolve()) if m_path.exists() else model_path
        label_map_str = str(lm_path.resolve()) if lm_path.exists() else label_map_path

        logger.info("Loading classifier model from %s", model_path_str)
        
        self.device = self._get_device()
        self.tokenizer = AutoTokenizer.from_pretrained(model_path_str)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path_str)
        self.model.to(self.device)
        self.model.eval()
        
        # Load label map
        with open(label_map_str) as f:
            label_data = json.load(f)
        self.id2label = {int(k): v for k, v in label_data["id2label"].items()}

        
        self._loaded = True
        logger.info(
            "Classifier loaded: %d labels, device=%s",
            len(self.id2label),
            self.device,
        )

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._loaded

    def predict(
        self,
        texts: list[str],
        max_len: int = 256,
        batch_size: int = 16,
    ) -> list[dict[str, Any]]:
        """Classify a list of text chunks.
        
        Args:
            texts: List of clause texts to classify.
            max_len: Maximum token length.
            batch_size: Inference batch size.
        
        Returns:
            List of dicts with 'label' and 'confidence' keys.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        
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
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                pred_ids = probs.argmax(dim=-1)
                confidences = probs.max(dim=-1).values
            
            for pred_id, conf in zip(pred_ids.cpu().tolist(), confidences.cpu().tolist()):
                results.append({
                    "label": self.id2label[pred_id],
                    "confidence": round(conf, 4),
                })
        
        logger.info("Classified %d clauses", len(results))
        return results

    @staticmethod
    def _get_device() -> torch.device:
        """Auto-detect best available device."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")


# Singleton instance
classifier = ClauseClassifier()

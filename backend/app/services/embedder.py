"""Semantic search using SBERT embeddings."""
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ClauseEmbedder:
    """Sentence-BERT embedder for semantic search and document-level domain distance.
    
    Loaded once at app startup via FastAPI lifespan.
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.train_centroid: np.ndarray | None = None
        self._loaded = False

    def load(self, model_name: str) -> None:
        """Load the SBERT model and training centroid.
        
        Args:
            model_name: HuggingFace model name or path.
        """
        from sentence_transformers import SentenceTransformer
        try:
            from app.config import settings
            device = getattr(settings, "device", "cpu")
        except Exception:  # noqa: BLE001
            device = "cpu"
        
        logger.info("Loading SBERT model: %s on device=%s", model_name, device)
        self.model = SentenceTransformer(model_name, device=device)
        
        # Load training corpus centroid if available
        candidate_paths = [
            Path("/app/model_artifacts/train_sbert_centroid.npy"),
            Path(__file__).resolve().parent.parent.parent.parent / "ml" / "artifacts" / "train_sbert_centroid.npy",
            Path(__file__).resolve().parent.parent.parent / "ml" / "artifacts" / "train_sbert_centroid.npy",
            Path("ml/artifacts/train_sbert_centroid.npy"),
        ]
        centroid_path = next((p for p in candidate_paths if p.exists()), None)
        if centroid_path:
            try:
                self.train_centroid = np.load(centroid_path)
                logger.info("Loaded training SBERT centroid from %s (shape: %s)", centroid_path, self.train_centroid.shape)
            except Exception as e:
                logger.warning("Could not load train_sbert_centroid: %s", e)
                self.train_centroid = None
        else:
            logger.warning("train_sbert_centroid.npy not found in candidate paths: %s", candidate_paths)
            self.train_centroid = None

        self._loaded = True
        logger.info("SBERT model loaded successfully")

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts into embeddings.
        
        Args:
            texts: List of texts to encode.
        
        Returns:
            numpy array of shape (n_texts, embedding_dim).
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        logger.info("Encoded %d texts -> shape %s", len(texts), embeddings.shape)
        return embeddings

    def compute_document_distance(self, clause_embeddings: np.ndarray) -> float:
        """Compute cosine distance from document mean embedding to commercial training centroid.
        
        Args:
            clause_embeddings: Array of clause embeddings (n_clauses, embedding_dim).
            
        Returns:
            Cosine distance in [0, 2].
        """
        if self.train_centroid is None or len(clause_embeddings) == 0:
            return 0.0
        doc_emb = clause_embeddings.mean(axis=0)
        norm = np.linalg.norm(doc_emb)
        if norm > 0:
            doc_emb = doc_emb / norm
        c = self.train_centroid
        c_norm = np.linalg.norm(c)
        if c_norm > 0:
            c = c / c_norm
        dist = float(1.0 - np.dot(doc_emb, c))
        return max(0.0, dist)

    def search(
        self,
        query: str,
        clause_texts: list[str],
        clause_embeddings: np.ndarray,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for most similar clauses to a query.
        
        Args:
            query: Search query in plain English.
            clause_texts: List of clause texts.
            clause_embeddings: Pre-computed embeddings for clauses.
            top_k: Number of results to return.
        
        Returns:
            List of dicts with 'index' and 'similarity' keys, sorted by similarity.
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        
        # Cosine similarity
        similarities = self._cosine_similarity(query_embedding, clause_embeddings)[0]
        
        # Top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "index": int(idx),
                "similarity": round(float(similarities[idx]), 4),
            })
        
        logger.info("Search returned %d results for query: '%s...'", len(results), query[:50])
        return results

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between two sets of vectors."""
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
        return np.dot(a_norm, b_norm.T)


# Singleton instance
embedder = ClauseEmbedder()

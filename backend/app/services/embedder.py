"""Semantic search using SBERT embeddings."""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ClauseEmbedder:
    """Sentence-BERT embedder for semantic search.
    
    Loaded once at app startup via FastAPI lifespan.
    """

    def __init__(self) -> None:
        self.model: Any = None
        self._loaded = False

    def load(self, model_name: str) -> None:
        """Load the SBERT model.
        
        Args:
            model_name: HuggingFace model name or path.
        """
        from sentence_transformers import SentenceTransformer
        
        logger.info("Loading SBERT model: %s", model_name)
        self.model = SentenceTransformer(model_name)
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

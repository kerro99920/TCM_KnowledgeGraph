"""Embedding model for semantic similarity and retrieval."""

from pathlib import Path
from typing import Any

import numpy as np

from tcm_kgraph.core.exceptions import EmbeddingError
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class EmbeddingModel:
    """
    Embedding model wrapper for text vectorization.

    Uses BGE-M3 or compatible sentence-transformers models
    for generating dense embeddings.
    """

    def __init__(
        self,
        model_path: Path | str,
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        """
        Initialize embedding model.

        Args:
            model_path: Path to model directory or HuggingFace model name
            device: Device to run model on ('cpu', 'cuda', 'cuda:0', etc.)
            normalize: Whether to L2-normalize embeddings
        """
        self._model_path = Path(model_path) if isinstance(model_path, str) else model_path
        self._device = device
        self._normalize = normalize
        self._model: Any = None
        self._dimension: int | None = None

    def _load_model(self) -> None:
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            model_str = str(self._model_path)
            logger.info(f"Loading embedding model from {model_str}")

            self._model = SentenceTransformer(
                model_str,
                device=self._device,
            )
            self._dimension = self._model.get_sentence_embedding_dimension()

            logger.info(
                f"Embedding model loaded: dim={self._dimension}, device={self._device}"
            )
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load embedding model: {e}",
                details={"model_path": str(self._model_path), "device": self._device},
            ) from e

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return self._dimension or 0

    def encode(
        self,
        texts: str | list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode texts to embeddings.

        Args:
            texts: Single text or list of texts to encode
            batch_size: Batch size for encoding
            show_progress: Show progress bar

        Returns:
            NumPy array of embeddings (shape: [n_texts, dimension])

        Raises:
            EmbeddingError: If encoding fails
        """
        self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                normalize_embeddings=self._normalize,
            )
            return np.array(embeddings)
        except Exception as e:
            raise EmbeddingError(
                f"Failed to encode texts: {e}",
                details={"num_texts": len(texts)},
            ) from e

    def similarity(
        self,
        embeddings1: np.ndarray,
        embeddings2: np.ndarray,
    ) -> np.ndarray:
        """
        Compute cosine similarity between embeddings.

        Args:
            embeddings1: First set of embeddings (shape: [n1, dim])
            embeddings2: Second set of embeddings (shape: [n2, dim])

        Returns:
            Similarity matrix (shape: [n1, n2])
        """
        # Normalize if not already normalized
        if not self._normalize:
            norm1 = np.linalg.norm(embeddings1, axis=1, keepdims=True)
            norm2 = np.linalg.norm(embeddings2, axis=1, keepdims=True)
            embeddings1 = embeddings1 / norm1
            embeddings2 = embeddings2 / norm2

        return embeddings1 @ embeddings2.T

    def find_similar(
        self,
        query: str,
        candidates: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float, str]]:
        """
        Find most similar texts to query.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of results to return

        Returns:
            List of (index, score, text) tuples sorted by similarity
        """
        query_emb = self.encode(query)
        candidate_embs = self.encode(candidates)

        similarities = self.similarity(query_emb, candidate_embs)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append((int(idx), float(similarities[idx]), candidates[idx]))

        return results

    def encode_for_neo4j(
        self,
        texts: str | list[str],
    ) -> list[list[float]]:
        """
        Encode texts for storage in Neo4j.

        Args:
            texts: Single text or list of texts

        Returns:
            List of embedding vectors as Python lists
        """
        embeddings = self.encode(texts)
        return embeddings.tolist()

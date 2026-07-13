"""Embedding generation abstractions and concrete providers."""

from __future__ import annotations
from abc import ABC, abstractmethod
import logging

from config.settings import EmbeddingSettings


class EmbeddingProvider(ABC):
    """Abstract interface for dense vector generation.

    The vector pipeline orchestration layer depends exclusively on this
    interface to transform text chunks into semantic embeddings, ensuring
    the pipeline remains completely agnostic to the underlying ML model.
    """

    @abstractmethod
    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate dense vector embeddings for a batch of strings.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of float lists, where each inner list represents the
            dense vector embedding of the corresponding input text.
            The dimensionality depends on the concrete model being used.
            Must be deterministic for identical inputs.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the generated vectors."""
        pass


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Concrete embedding provider using the sentence-transformers library.

    Designed to run models locally (e.g., BAAI/bge-m3).
    Lazy-loads the model on first use to speed up application startup.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._dimension = None
        self._logger = logging.getLogger(__name__)

    @classmethod
    def from_settings(cls, settings: EmbeddingSettings) -> SentenceTransformerEmbeddingProvider:
        """Create a provider using the model name configured in application settings."""
        return cls(model_name=settings.model_name)

    def _load_model(self) -> None:
        if self._model is None:
            # Import here to avoid slow startup for components that don't need it
            from sentence_transformers import SentenceTransformer

            self._logger.info(f"Loading embedding model: {self._model_name}")
            # Normalize embeddings to enable inner product (cosine similarity equivalent)
            self._model = SentenceTransformer(self._model_name)
            
            # Determine dimensionality
            dummy_embed = self._model.encode(["test"])
            self._dimension = len(dummy_embed[0])
            self._logger.info(f"Model loaded. Dimensionality: {self._dimension}")

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._dimension

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
            
        self._load_model()
        
        # Determine if normalize_embeddings parameter is accepted.
        # sentence-transformers encode method accepts normalize_embeddings.
        # This guarantees vectors are normalized, which is best practice.
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        
        # Convert numpy arrays to Python float lists
        return [emb.tolist() for emb in embeddings]

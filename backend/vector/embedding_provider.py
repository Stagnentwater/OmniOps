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

    def _resolve_model_path(self) -> str:
        """Resolve model name or local directory path for offline execution.
        
        Searches local model directories before falling back to model name,
        ensuring on-premise air-gapped deployments never perform external network calls.
        """
        import os
        name = self._model_name
        
        # Candidate directories to inspect for a pre-downloaded local model
        candidates = [
            name,
            os.path.abspath(name),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", name),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "all-MiniLM-L6-v2"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "embedding_model"),
            os.path.join(os.getcwd(), "models", name),
            os.path.join(os.getcwd(), "models", "all-MiniLM-L6-v2"),
            os.path.join(os.getcwd(), "models", "embedding_model"),
            os.path.join(os.getcwd(), "backend", "models", name),
            os.path.join(os.getcwd(), "backend", "models", "all-MiniLM-L6-v2"),
        ]
        
        for candidate in candidates:
            if os.path.isdir(candidate):
                if os.path.exists(os.path.join(candidate, "modules.json")) or os.path.exists(os.path.join(candidate, "config.json")):
                    self._logger.info(f"Resolved offline local model path: {candidate}")
                    return candidate
                    
        return name

    def _load_model(self) -> None:
        if self._model is None:
            import os
            # Enforce offline flags for air-gapped on-premise environments
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

            # Import here to avoid slow startup for components that don't need it
            from sentence_transformers import SentenceTransformer

            target_path = self._resolve_model_path()
            self._logger.info(f"Loading embedding model: {target_path} (offline mode)")

            try:
                # First attempt strictly offline using local_files_only
                self._model = SentenceTransformer(target_path, local_files_only=True)
            except Exception as exc:
                self._logger.warning(
                    f"Offline local_files_only load raised {type(exc).__name__}: {exc}. "
                    "Falling back to standard initialization with offline environment."
                )
                self._model = SentenceTransformer(target_path)
            
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

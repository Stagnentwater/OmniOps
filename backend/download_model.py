"""Utility to pre-download the embedding model for offline or faster startup.

This script downloads the configured embedding model from Hugging Face
and caches it using sentence-transformers' default cache directory.
No local filesystem path is used — the model is loaded by name at runtime.

Usage:
    python download_model.py
"""

import os
from sentence_transformers import SentenceTransformer


def main() -> None:
    # Use the same default as config/settings.py EmbeddingSettings
    model_name = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    print(f"Downloading/Loading '{model_name}'...")
    print("This might take a few minutes if it hasn't been cached yet.")

    # Downloads from Hugging Face if not cached, otherwise loads from cache.
    # The model will be stored in the default sentence-transformers cache
    # directory (~/.cache/torch/sentence_transformers/).
    model = SentenceTransformer(model_name)

    dim = model.get_sentence_embedding_dimension()
    print(f"\nModel '{model_name}' successfully loaded and cached!")
    print(f"Embedding dimensionality: {dim}")
    print(f"\nThe model will be loaded by name at runtime via:")
    print(f'  EMBEDDING_MODEL_NAME="{model_name}"')


if __name__ == "__main__":
    main()

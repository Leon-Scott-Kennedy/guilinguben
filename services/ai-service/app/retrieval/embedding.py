from __future__ import annotations

import csv
import os

# Python 3.13 + transformers/sentence-transformers may fail while scanning installed
# package metadata because the default csv field size is too small for some dist-info files.
# Increase it before importing the embedding stack.
field_limit = csv.field_size_limit()
if field_limit < 2**31 - 1:
    csv.field_size_limit(2**31 - 1)

# Prevent sentence-transformers from trying to connect to Hugging Face Hub
os.environ["HF_HUB_OFFLINE"] = "1"

from langchain_community.embeddings import HuggingFaceEmbeddings

from app.config import settings


class LocalEmbeddingProvider:
    """Thin wrapper around the local BGE model used by FAISS and retrieval."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or settings.embedding_model_path
        self._embeddings: HuggingFaceEmbeddings | None = None

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            # Use a direct absolute path to ensure the model is found locally
            import os
            from pathlib import Path
            
            # Resolve the path to avoid any relative path issues
            # Note: settings.embedding_model_path is already absolute, but let's ensure it's resolved
            model_path = Path(self.model_path).resolve()
            
            if not model_path.exists():
                raise FileNotFoundError(f"Model path does not exist: {model_path}")

            # Ensure we are using the correct path format for sentence-transformers
            # Sometimes it prefers forward slashes or specific formats on Windows
            model_path_str = str(model_path)

            try:
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=model_path_str,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
            except OSError as e:
                if "couldn't connect" in str(e) or "LocalEntryNotFoundError" in str(e):
                    # Retry with local_files_only=True if the first attempt failed due to network issues
                    self._embeddings = HuggingFaceEmbeddings(
                        model_name=model_path_str,
                        model_kwargs={"device": "cpu", "local_files_only": True},
                        encode_kwargs={"normalize_embeddings": True},
                    )
                else:
                    raise
            
        return self._embeddings

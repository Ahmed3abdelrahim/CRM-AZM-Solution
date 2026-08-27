from __future__ import annotations

from functools import lru_cache

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


def resolve_device(configured: str) -> str:
    """Settings.EMBEDDING_DEVICE — never hardcoded (this run's explicit instruction). "auto"
    (the default) probes CUDA availability and falls back to CPU; "cuda"/"cpu" are honored
    literally. The same code path runs unchanged on a CPU-only laptop and on GPU hardware later
    (docs/architecture/stack.md) — only the setting differs."""
    if configured != "auto":
        return configured
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001 — a probe failure must fall back, never crash embedding use
        return "cpu"


class EmbeddingModel:
    """BAAI/bge-m3 (1024-dim — matches kb_article_chunks.embedding's fixed vector(1024) column,
    data-model.md §1.22) via sentence-transformers. The underlying model is loaded lazily, on
    first use, so importing this module (or constructing the module-level singleton below) never
    triggers a multi-GB download/load on its own."""

    def __init__(self, model_name: str, device_setting: str) -> None:
        self.model_name = model_name
        self.device = resolve_device(device_setting)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("embedding_model_loading", model=self.model_name, device=self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("embedding_model_loaded", model=self.model_name, device=self.device)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]


@lru_cache
def get_embedding_model() -> EmbeddingModel:
    return EmbeddingModel(settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)

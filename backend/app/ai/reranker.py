from __future__ import annotations

from functools import lru_cache

import structlog

from app.ai.embeddings import resolve_device
from app.config import settings

logger = structlog.get_logger(__name__)


class Reranker:
    """bge-reranker-v2-m3, gated by Settings.KB_RERANK_ENABLED (default off — research.md/
    stack.md: "Enable behind a feature flag. When disabled, reciprocal-rank-fused order is
    returned" — already FR-043's documented fallback). Shares EmbeddingModel's device-resolution
    rule: EMBEDDING_DEVICE, never hardcoded."""

    def __init__(self, model_name: str, device_setting: str) -> None:
        self.model_name = model_name
        self.device = resolve_device(device_setting)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("reranker_model_loading", model=self.model_name, device=self.device)
            self._model = CrossEncoder(self.model_name, device=self.device)
            logger.info("reranker_model_loaded", model=self.model_name, device=self.device)
        return self._model

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        model = self._load()
        scores = model.predict([(query, document) for document in documents])
        return [float(score) for score in scores]


@lru_cache
def get_reranker() -> Reranker:
    return Reranker(settings.KB_RERANK_MODEL, settings.EMBEDDING_DEVICE)

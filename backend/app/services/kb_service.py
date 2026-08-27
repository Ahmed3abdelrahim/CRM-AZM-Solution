from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import chunk_text
from app.ai.embeddings import get_embedding_model
from app.ai.reranker import get_reranker
from app.config import settings
from app.core.audit import audited
from app.core.errors import NotFoundError, ValidationError
from app.core.permissions import CurrentActor, require_permission
from app.models.kb_article import KbArticle, KbArticleChunk
from app.repositories.kb_repository import KbArticleRepository
from app.repositories.scoped_repository import TenantScope
from app.schemas.kb_article import KbArticleCreate, KbArticleUpdate, KbSearchResult

logger = structlog.get_logger(__name__)

_BODY_FIELDS = ("title_ar", "title_en", "body_ar", "body_en")


class KbService:
    """plan.md §Service Classes — `KbService`. `list`/`get` are plain delegations to
    `KbArticleRepository` (the "composes AdminCrudService's list/get for the plain-CRUD parts"
    plan.md describes, written inline here rather than via a second class — F01's
    `CustomerService` uses the identical shape for the same reason: chunking/publish-validation
    make this a bespoke service, not a Generic CRUD Pattern subclass)."""

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None:
        self.session = session
        self.scope = scope
        self.repository = KbArticleRepository(session, scope)

    def _not_found(self, id: UUID) -> NotFoundError:
        return NotFoundError(f"المقالة غير موجودة: {id}", f"Article not found: {id}")

    @require_permission("kb_article.read")
    async def list(self, actor: CurrentActor, limit: int = 50, offset: int = 0) -> list[KbArticle]:
        return await self.repository.list(limit=limit, offset=offset)

    @require_permission("kb_article.read")
    async def get(self, actor: CurrentActor, id: UUID) -> KbArticle:
        article = await self.repository.get(id)
        if article is None:
            raise self._not_found(id)
        return article

    @require_permission("kb_article.create")
    async def create_article(self, actor: CurrentActor, data: KbArticleCreate) -> KbArticle:
        return await self._create_audited(actor, None, data)

    @audited("kb_article", "create")
    async def _create_audited(self, actor: CurrentActor, id: None, data: KbArticleCreate) -> KbArticle:
        values = data.model_dump()
        values["created_by"] = actor.user_id
        article = await self.repository.create(values)
        await self._rechunk_and_embed(article)
        return article

    @require_permission("kb_article.create")
    async def update_article(self, actor: CurrentActor, id: UUID, data: KbArticleUpdate) -> KbArticle:
        existing = await self.repository.get(id)
        if existing is None:
            raise self._not_found(id)
        return await self._update_audited(actor, id, data)

    @audited("kb_article", "update")
    async def _update_audited(self, actor: CurrentActor, id: UUID, data: KbArticleUpdate) -> KbArticle:
        """Re-chunks and re-embeds both locales on any body/title change (plan.md
        `update_article`) — an update that touches neither leaves the existing chunks alone."""
        values = data.model_dump(exclude_unset=True)
        values["updated_by"] = actor.user_id
        article = await self.repository.update(id, values)
        if any(field in values for field in _BODY_FIELDS):
            await self._rechunk_and_embed(article)
        return article

    @require_permission("kb_article.publish")
    async def publish_article(self, actor: CurrentActor, id: UUID) -> KbArticle:
        article = await self.repository.get(id)
        if article is None:
            raise self._not_found(id)
        if not (article.title_ar and article.title_en and article.body_ar and article.body_en):
            raise ValidationError(
                "لا يمكن النشر: يجب تعبئة العنوان والنص بكلا اللغتين",
                "Cannot publish: title and body are required in both languages",
            )
        return await self._publish_audited(actor, id)

    @audited("kb_article", "publish")
    async def _publish_audited(self, actor: CurrentActor, id: UUID) -> KbArticle:
        return await self.repository.update(id, {"is_published": True, "updated_by": actor.user_id})

    async def _rechunk_and_embed(self, article: KbArticle) -> None:
        """~500 tokens / 50 overlap per locale (plan.md `update_article`), embedded via the fixed
        BAAI/bge-m3 model (Settings.EMBEDDING_MODEL). Wrapped so that an embedding-pipeline
        failure (model not yet downloaded, OOM, etc.) never blocks article authoring — it leaves
        the article temporarily unsearchable via the semantic half only, not un-creatable."""
        await self.session.execute(delete(KbArticleChunk).where(KbArticleChunk.kb_article_id == article.id))
        try:
            model = get_embedding_model()
            created_by = article.updated_by or article.created_by
            for locale, body in (("ar", article.body_ar), ("en", article.body_en)):
                chunks = chunk_text(body, settings.KB_CHUNK_TOKENS, settings.KB_CHUNK_OVERLAP_TOKENS)
                if not chunks:
                    continue
                vectors = model.embed(chunks)
                for index, (content, vector) in enumerate(zip(chunks, vectors)):
                    self.session.add(
                        KbArticleChunk(
                            kb_article_id=article.id,
                            locale=locale,
                            chunk_index=index,
                            content=content,
                            embedding=vector,
                            created_by=created_by,
                        )
                    )
            await self.session.flush()
        except Exception as exc:  # noqa: BLE001 — indexing must never block article authoring
            logger.warning("kb_article_embedding_failed", article_id=str(article.id), error=str(exc))

    @require_permission("kb_article.read")
    async def search(self, actor: CurrentActor, query: str, limit: int = 10) -> list[KbSearchResult]:
        """FR-042/FR-043 — hybrid trigram + vector search, RRF-fused, optionally reranked. Never
        raises: an unavailable embedding model degrades to lexical-only (FR-043 / spec.md Story 6
        Acceptance Scenario 4); an unavailable/disabled reranker simply skips reranking."""
        query_embedding: list[float] | None = None
        try:
            model = get_embedding_model()
            [query_embedding] = model.embed([query])
        except Exception as exc:  # noqa: BLE001 — degrade to lexical-only, never fail the search
            logger.warning("kb_query_embedding_failed", error=str(exc))
            query_embedding = None

        results = await self.repository.hybrid_search(query, query_embedding, limit=limit)

        if settings.KB_RERANK_ENABLED and results:
            results = await self._rerank(query, results)

        return [
            KbSearchResult(article=article, score=score, matched_locale=locale)
            for article, score, locale in results
        ]

    async def _rerank(
        self, query: str, results: list[tuple[KbArticle, float, str]]
    ) -> list[tuple[KbArticle, float, str]]:
        try:
            reranker = get_reranker()
            documents = [article.body_ar if locale == "ar" else article.body_en for article, _score, locale in results]
            scores = reranker.rerank(query, documents)
            reranked = sorted(zip(results, scores), key=lambda pair: pair[1], reverse=True)
            return [(article, float(new_score), locale) for (article, _old_score, locale), new_score in reranked]
        except Exception as exc:  # noqa: BLE001 — reranking is a refinement, never a hard dependency
            logger.warning("kb_rerank_failed", error=str(exc))
            return results

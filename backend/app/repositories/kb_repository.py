from __future__ import annotations

from uuid import UUID

from sqlalchemy import func

from app.models.kb_article import KbArticle, KbArticleChunk
from app.repositories.scoped_repository import ScopedRepository, ScopingMode


class KbArticleRepository(ScopedRepository[KbArticle]):
    """`ScopedRepository[KbArticle]` (S2 — research.md Part 2) plus the hybrid search query
    builder: `pg_trgm` lexical half + `pgvector` cosine semantic half, reciprocal-rank-fused.
    Never overrides `_scoped_select` — every method below starts from it, same as
    `TicketRepository`."""

    model = KbArticle
    scoping_mode = ScopingMode.S2_BRANCH_DEPT_OPTIONAL
    has_soft_delete = False

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float] | None,
        limit: int = 10,
        candidate_k: int = 20,
    ) -> list[tuple[KbArticle, float, str]]:
        """F06 — returns `(article, fused_score, matched_locale)` tuples, best first, restricted
        to published articles within scope. `query_embedding` is `None` when the local embedding
        model is unavailable (e.g. stopped, or never downloaded) — the semantic half is then
        simply skipped, and the fused order degrades to lexical-only (FR-043, spec.md Story 6
        Acceptance Scenario 4) rather than raising.

        Lexical half: `pg_trgm` `similarity()` over `body_ar`/`body_en` — the two columns
        data-model.md §1.21 explicitly indexes as "lexical half of hybrid search (F06)".
        Semantic half: cosine distance over `kb_article_chunks.embedding`, joined transitively
        through `kb_articles` (S4, data-model.md §1.22) — never a second, independent scope
        filter.

        Both ranked lists are fused via Reciprocal Rank Fusion (k=60): each list contributes
        `1 / (60 + rank + 1)` per article, summed across lists. RRF combines *ranks*, not raw
        scores, deliberately — trigram similarity (0..1) and cosine distance are on unrelated
        scales, so blending them directly would be meaningless.
        """

        published = self._scoped_select().where(KbArticle.is_published.is_(True))

        ar_similarity = func.similarity(KbArticle.body_ar, query)
        en_similarity = func.similarity(KbArticle.body_en, query)
        lexical_stmt = (
            published.add_columns(ar_similarity.label("ar_similarity"), en_similarity.label("en_similarity"))
            .order_by(func.greatest(ar_similarity, en_similarity).desc())
            .limit(candidate_k)
        )
        lexical_rows = (await self.session.execute(lexical_stmt)).all()
        lexical_ranked: list[tuple[KbArticle, str]] = [
            (article, "ar" if (ar_sim or 0) >= (en_sim or 0) else "en")
            for article, ar_sim, en_sim in lexical_rows
        ]

        semantic_ranked: list[tuple[KbArticle, str]] = []
        if query_embedding is not None:
            distance = KbArticleChunk.embedding.cosine_distance(query_embedding)
            semantic_stmt = (
                published.join(KbArticleChunk, KbArticleChunk.kb_article_id == KbArticle.id)
                .add_columns(KbArticleChunk.locale, distance.label("distance"))
                .order_by(distance.asc())
                .limit(candidate_k)
            )
            semantic_rows = (await self.session.execute(semantic_stmt)).all()
            seen: set[UUID] = set()
            for article, locale, _distance in semantic_rows:
                if article.id in seen:
                    continue
                seen.add(article.id)
                semantic_ranked.append((article, locale))

        rrf_k = 60
        fused: dict[UUID, float] = {}
        articles: dict[UUID, KbArticle] = {}
        locales: dict[UUID, str] = {}
        for rank, (article, locale) in enumerate(lexical_ranked):
            fused[article.id] = fused.get(article.id, 0.0) + 1.0 / (rrf_k + rank + 1)
            articles[article.id] = article
            locales.setdefault(article.id, locale)
        for rank, (article, locale) in enumerate(semantic_ranked):
            fused[article.id] = fused.get(article.id, 0.0) + 1.0 / (rrf_k + rank + 1)
            articles[article.id] = article
            locales[article.id] = locale  # the semantic match is the more precise locale signal

        ranked_ids = sorted(fused, key=lambda article_id: fused[article_id], reverse=True)[:limit]
        return [(articles[article_id], fused[article_id], locales[article_id]) for article_id in ranked_ids]


class KbArticleChunkRepository(ScopedRepository[KbArticleChunk]):
    model = KbArticleChunk
    scoping_mode = ScopingMode.S4_TRANSITIVE
    parent_model = KbArticle
    parent_fk_column = "kb_article_id"

# Technology Stack — CRM-AZM-Solution

**Revision 2** — recalibrated for CPU-only laptop development. Changes from rev 1 are marked ⚠ and each carries a repayment trigger in `docs/DEBT.md`.

Authoritative. `/speckit.plan` references this file directly. Any dependency not listed here requires a justification entry in `research.md`.

---

## Runtime target

| | Sprint (now) | Production (later) |
|---|---|---|
| Host | Developer laptop, CPU only, no GPU | On-premise server with GPU |
| Orchestration | Docker Compose, single host | Docker Compose → Kubernetes |
| Network | Outbound allowed for the LLM provider | Air-gapped, self-hosted models |

The architecture is identical across both. Only configuration differs. That property is the entire point of the LiteLLM gateway and must not be compromised for convenience.

---

## Backend

| Component | Choice | Version |
|---|---|---|
| Language | Python | 3.12 |
| API framework | FastAPI | ^0.115 |
| ORM | SQLAlchemy (2.0 style, async) | ^2.0 |
| Migrations | Alembic | ^1.14 |
| Validation | Pydantic | ^2.9 |
| Server | Uvicorn (standard extras) | ^0.32 |
| Job queue | ARQ | ^0.26 |
| HTTP client | httpx | ^0.27 |

Business logic lives in service classes under `app/services/`. Route handlers validate, delegate, serialize — nothing else. The repository layer under `app/repositories/` is the only place that constructs queries, and is where branch/department scoping is enforced.

## Data

| Component | Choice | Version |
|---|---|---|
| Primary DB | PostgreSQL | 16 |
| Vector search | `pgvector` extension | ^0.7 |
| Fuzzy/trigram search | `pg_trgm` extension | built-in |
| Cache & queue broker | Redis | 7 |
| Object storage | MinIO (S3 API) | latest stable |

One datastore for OLTP, full-text, and vectors. No separate vector database.

Arabic search uses `pg_trgm` similarity plus dense semantic search. **Do not rely on PostgreSQL's Arabic text-search configuration** — its stemming is inadequate for Arabic morphology.

---

## AI layer ⚠ REVISED

Split by compute profile. Embeddings run locally on CPU; generative work runs on a remote endpoint.

### Gateway — unchanged and non-negotiable

**LiteLLM.** Every generative call routes through it. No vendor SDK imports anywhere in application code. Model names come from configuration:

```
LITELLM_MODEL_CHAT=<configured>
LITELLM_MODEL_CLASSIFY=<configured>
LITELLM_API_BASE=<configured>
LITELLM_API_KEY=<configured>
```

Migrating from a remote provider to self-hosted vLLM changes these four values and nothing else.

### Generative — remote endpoint ⚠

| Capability | Model family | Notes |
|---|---|---|
| Summary, suggested reply | Qwen3-32B (or 30B-A3B) via OpenRouter / Together | Same family as the eventual self-hosted target |
| Auto-categorization | Qwen3-4B or Qwen3-8B | Short output; cheapest tier is sufficient |

**Use the Qwen3 family, not GPT or Claude.** Prompts tuned against Qwen3 now transfer unchanged to self-hosted Qwen3 later. A different family means re-tuning all four prompts when the hardware arrives.

Generative inference on laptop CPU is not viable: 8–15 tok/s means a 200-token reply takes 20–30 seconds. Rejected.

### Embeddings — local CPU ⚠

Choose by available laptop RAM. **Fix this before batch 4g** — the `pgvector` column dimension is set at migration time and is not casually changed mid-build.

| Laptop RAM | Model | Params | Dimension | Loaded size |
|---|---|---|---|---|
| ≥ 16 GB | `BAAI/bge-m3` (ONNX int8) | 568M | **1024** | ~600 MB |
| < 16 GB | `intfloat/multilingual-e5-small` | 118M | **384** | ~120 MB |

Run via `sentence-transformers` with ONNX runtime, or `fastembed`. One forward pass per query is 200–400 ms on CPU — acceptable for interactive search. Indexing 10 seeded articles takes a few seconds, one time.

### Reranking — local CPU, optional ⚠

`bge-reranker-v2-m3` on CPU adds 300–800 ms per query. Enable behind a feature flag. When disabled, reciprocal-rank-fused order is returned — already the documented fallback in `PLAN.md` F06.

### Observability ⚠ Langfuse removed

Current Langfuse requires its own Postgres, ClickHouse, and S3. On a laptop already running PG, Redis, MinIO, the API, and a Next dev server, that is the component that makes startup unusable.

Replaced by an `llm_calls` table:

```
id, ticket_id (nullable), capability, model, prompt_version,
input_tokens, output_tokens, latency_ms, fallback_used,
error (nullable), correlation_id, created_at
```

Written by the LiteLLM wrapper on every call, success or failure. Same telemetry story, zero infrastructure cost. Langfuse returns when the stack moves to a server.

### Fallbacks — unchanged

Every AI feature stays deterministic when the model is unreachable. Categorization → `NULL` suggestion, agent picks manually. Summary → first 300 characters. Suggested reply → empty composer. Suggested solution → panel does not render. **With the LLM endpoint unreachable, every screen remains fully usable.** This is a hard acceptance criterion, and it now also covers loss of internet connectivity — which matters, because the demo machine is no longer self-contained.

---

## Frontend

| Component | Choice | Version |
|---|---|---|
| Framework | Next.js (App Router) | ^15 |
| Language | TypeScript | ^5.6 |
| Styling | Tailwind CSS | ^3.4 |
| Components | shadcn/ui | latest |
| i18n | next-intl | ^3 |
| Data fetching | TanStack Query | ^5 |
| Forms | react-hook-form + zod | latest |

**RTL is structural.** Tailwind logical properties only — `ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`. Never `ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*`. One stylesheet serves both directions; `dir` is set on `<html>` from the active locale. No separate Arabic stylesheet, no mirroring build step.

Arabic typography: IBM Plex Sans Arabic, Noto Sans Arabic, or Cairo. A Latin-only stack falling back to system Arabic rendering looks broken.

## Auth & security

| Component | Choice | Notes |
|---|---|---|
| Authentication | FastAPI + JWT (access 15 min, refresh 7 days) | Keycloak is the production target; deferred as documented debt |
| Password hashing | Argon2 via passlib | |
| Authorization | Role + permission checks in service layer | UI hiding is cosmetic only |
| Machine clients | API keys, scoped, stored hashed | Tier S integrations |

## Logging

structlog, JSON output, correlation id propagated end to end from ingestion through response. Full OpenTelemetry and Prometheus/Grafana are Phase 2 — correlation ids exist from the first commit so instrumenting later does not require touching every call site.

## Testing

| Scope | Approach |
|---|---|
| Business rules with branching logic | pytest — status transition legality, permission checks, SLA computation, tenant scoping |
| CRUD passthroughs | No tests |
| AI features | Bilingual golden set of 20 tickets, scored by script |
| API contracts | Schemathesis against OpenAPI — only if time permits |

---

## Laptop resource budget

Approximate steady-state footprint. Verify against available RAM before batch 4a.

| Service | RAM |
|---|---|
| PostgreSQL 16 | ~250 MB |
| Redis 7 | ~50 MB |
| MinIO | ~200 MB |
| FastAPI + embedding model | ~900 MB (BGE-M3 int8) / ~400 MB (e5-small) |
| ARQ worker | ~200 MB |
| Next.js dev server | ~600 MB |
| **Total** | **~2.2 GB** / ~1.7 GB |

If this is tight: run the frontend outside Docker with `npm run dev`, and drop MinIO in favour of a mounted volume behind the same storage interface.

---

## Explicitly not in this stack

Keycloak, Kubernetes, Qdrant, Celery, RabbitMQ, Elasticsearch, a separate vector database, GraphQL, Langfuse, local vLLM, or any ORM other than SQLAlchemy. If the plan or the implementation reaches for one of these, it is a deviation requiring justification in `research.md`.

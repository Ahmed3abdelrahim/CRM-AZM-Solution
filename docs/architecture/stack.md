# Technology Stack — CRM-AZM-Solution

Authoritative. `/speckit.plan` references this file directly. Any dependency not listed here requires a justification entry in `research.md`.

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

Business logic lives in service classes under `app/services/`. Route handlers validate, delegate, serialize — nothing else. Repository layer under `app/repositories/` is the only place that constructs queries, and it is where branch/department scoping is enforced.

## Data

| Component | Choice | Version |
|---|---|---|
| Primary DB | PostgreSQL | 16 |
| Vector search | `pgvector` extension | ^0.7 |
| Fuzzy/trigram search | `pg_trgm` extension | built-in |
| Cache & queue broker | Redis | 7 |
| Object storage | MinIO (S3 API) | latest stable |

One datastore for OLTP, full-text, and vectors. No separate vector database in this sprint — `pgvector` at expected volume is not the bottleneck, and operating a second system on-prem is not free.

Arabic search uses `pg_trgm` similarity plus BGE-M3 semantic search. Do **not** rely on PostgreSQL's Arabic text-search configuration alone; its stemming is weak for Arabic morphology.

## AI layer

| Component | Choice | Notes |
|---|---|---|
| Gateway | LiteLLM | **Every** model call routes through this. No vendor SDK imports anywhere in application code. |
| Serving | vLLM (OpenAI-compatible endpoint) | Self-hosted on-prem |
| Chat / assist model | Qwen3-32B or Qwen3-30B-A3B | Configurable by name |
| Classification model | Qwen3-4B | Auto-categorization and routing — ~50× cheaper than sending everything to the large model |
| Embeddings | BGE-M3 | Strong multilingual, notably Arabic |
| Reranker | bge-reranker-v2-m3 | KB retrieval quality |
| Tracing | Langfuse (self-hosted) | Token counts, latency, prompt versions |

**Hardware note:** Qwen3-32B at usable latency needs roughly 2×A100 80GB or 2×L40S in FP8/AWQ. If that is not confirmed on-prem before the sprint, drop to Qwen3-14B or point LiteLLM at a cloud endpoint for the demo. Because everything routes through LiteLLM, this is a configuration change and touches no application code.

Every AI feature has a deterministic fallback: categorization falls back to "Uncategorized", summaries fall back to the first N characters of the description, suggested replies and solutions simply do not render. The system stays fully usable with the model stopped.

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

**RTL is structural.** Use Tailwind logical properties (`ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`) exclusively. Never `ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*`. One stylesheet serves both directions; `dir` is set on `<html>` from the active locale. There is no separate Arabic stylesheet and no mirroring build step.

Arabic typography: use a font stack with proper Arabic coverage (IBM Plex Sans Arabic, Noto Sans Arabic, or Cairo). Latin-only fonts fall back to system Arabic rendering and look broken.

## Auth & security

| Component | Choice | Notes |
|---|---|---|
| Authentication | FastAPI + JWT (access + refresh) | Keycloak is the production target; deferred as documented debt |
| Password hashing | Argon2 via passlib | |
| Authorization | Role + permission checks in service layer | UI hiding is cosmetic only |
| Machine clients | API keys with scoped permissions | For Tier S integrations |

## Runtime & observability

| Component | Choice |
|---|---|
| Orchestration | Docker Compose (single host, on-prem) |
| Logging | structlog, JSON output, correlation id propagated end to end |
| LLM observability | Langfuse |
| Error tracking | Sentry (self-hosted) — optional for MVP |

Full OpenTelemetry tracing and Prometheus/Grafana are Phase 2. Correlation ids are propagated from the first commit so instrumenting later does not require touching every call site.

## Testing

| Scope | Approach |
|---|---|
| Business rules with branching logic | pytest — status transition legality, permission checks, SLA computation, tenant scoping |
| CRUD passthroughs | No tests |
| AI features | Small bilingual golden dataset, evaluated by script; not unit tests |
| API contracts | Schemathesis against the OpenAPI spec — optional if time permits |

Testcontainers and a CI contract-test gate are the production target and are logged in `docs/DEBT.md`.

---

## Explicitly not in this stack

Keycloak, Kubernetes, Qdrant, Celery, RabbitMQ, Elasticsearch, a separate vector DB, GraphQL, or any ORM other than SQLAlchemy. If the plan or the implementation reaches for one of these, it is a deviation requiring justification.

# Research: Bilingual Support CRM — Core Product

**Input**: `specs/001-bilingual-support-crm/spec.md`, `PLAN.md`, `docs/architecture/stack.md`,
`.specify/memory/constitution.md`, `specs/002-007` (Tier D roadmap).

This document has three parts: (1) technology decisions, all taken directly from
`docs/architecture/stack.md` with no substitution; (2) two documentation gaps discovered in
`PLAN.md` §4.1 that had to be resolved to produce a complete `data-model.md`, resolved using
`PLAN.md`'s own pattern definitions and cross-checked against the constitution; (3) a
compatibility check confirming `data-model.md` accommodates every Tier D roadmap spec
(`specs/002`–`007`) with reserved columns/enum values only, no design decision that would force
a migration across populated tables later.

## Part 1 — Technology Decisions

Every entry below is taken verbatim from `docs/architecture/stack.md`. No dependency outside
that file is introduced. Where `stack.md` marks a choice ⚠ (revised for CPU-only laptop
development), that revision is what this plan builds against — not the original GPU-era design.

| Area | Decision | Rationale | Alternatives considered (rejected) |
|---|---|---|---|
| Backend language/runtime | Python 3.12, FastAPI ^0.115, Uvicorn ^0.32 (standard extras) | `stack.md` §Backend; async-native, matches SQLAlchemy 2.0 async and ARQ | None — `stack.md` is authoritative and single-sourced |
| ORM / migrations | SQLAlchemy 2.0 (async) ^2.0, Alembic ^1.14 | Only ORM permitted per `stack.md` "Explicitly not in this stack" | Any other ORM — explicitly excluded |
| Validation | Pydantic ^2.9 | Matches FastAPI's native integration | — |
| Job queue | ARQ ^0.26 (Redis-backed) | Runs the email poll, categorization, and SLA sweep jobs off the request path (constitution IX, FR-009/FR-049) | Celery/RabbitMQ — explicitly excluded in `stack.md` |
| HTTP client | httpx ^0.27 | Used only inside the LiteLLM wrapper and the email adapter's outbound calls | — |
| Primary datastore | PostgreSQL 16 | One datastore for OLTP, full-text, and vector data | A separate vector database (Qdrant) — explicitly excluded |
| Vector search | `pgvector` ^0.7, `vector(1024)` (BGE-M3 dimensionality) | Matches the ≥16 GB RAM embedding model row in `stack.md`; **see Assumption A1 below** | Local `intfloat/multilingual-e5-small` (384-dim) — only if the target machine has <16 GB RAM |
| Fuzzy/trigram search | `pg_trgm` (built-in extension) | Required by FR-012 (Arabic partial-name/contact search); **do not** rely on PostgreSQL's Arabic text-search configuration — its stemming is inadequate for Arabic morphology (`stack.md`, PLAN.md §5 F06) | PostgreSQL native `tsvector`/`tsquery` Arabic config — explicitly rejected |
| Cache & queue broker | Redis 7 | Backs ARQ; no application-level caching is designed in this sprint (none required by any Tier M/S acceptance criterion) | — |
| Object storage | MinIO (S3 API), latest stable | Backs `attachments.storage_key` and (Tier D, `specs/007`) branch logo/favicon storage | A mounted volume behind the same storage interface — laptop fallback noted in `stack.md`, not used unless the resource budget requires it |
| AI gateway | LiteLLM — every generative/embedding call routes through it; no vendor SDK import anywhere in application code (constitution VIII / PLAN.md C8) | Model names come from `LITELLM_MODEL_CHAT`, `LITELLM_MODEL_CLASSIFY`, `LITELLM_API_BASE`, `LITELLM_API_KEY` env vars only | Direct OpenAI/Anthropic SDK calls — explicitly forbidden |
| Generative model family | Qwen3 family only (Qwen3-32B or 30B-A3B for summary/suggested reply; Qwen3-4B or 8B for categorization), via a remote endpoint (OpenRouter/Together) this sprint | Same family transfers unchanged to a self-hosted vLLM deployment later; prompts tuned against a different family would need re-tuning | GPT/Claude for generative calls — explicitly rejected per `stack.md` |
| Embedding model | `BAAI/bge-m3` (ONNX int8, 1024-dim) if the dev machine has ≥16 GB RAM, else `intfloat/multilingual-e5-small` (384-dim) — chosen once, before batch 4g, and fixed for the life of the `pgvector` column | Local CPU inference is fast enough for interactive search (200–400 ms/query); generative inference on CPU (8–15 tok/s) is rejected outright | Running embeddings remotely — rejected; embeddings stay local per `stack.md` |
| Reranking | `bge-reranker-v2-m3` on CPU, behind a feature flag; disabled → reciprocal-rank-fused order returned (already FR-043's documented fallback) | Adds 300–800 ms/query; acceptable as an optional refinement, not a hard dependency | Always-on reranking — listed as deliberate debt (PLAN.md §8), repaid when GPU is available |
| AI observability | `llm_calls` table (see data-model.md), written by the LiteLLM wrapper on every call, success or failure | Langfuse requires its own Postgres/ClickHouse/S3 — unworkable on the laptop resource budget; `llm_calls` gives the same audit fields (FR-050, PLAN.md F07) at zero extra infrastructure cost | Langfuse — explicitly removed in `stack.md` rev 2; tracked as deliberate debt, repaid when the stack moves to a server |
| Frontend framework | Next.js (App Router) ^15, TypeScript ^5.6 | — | — |
| Styling | Tailwind CSS ^3.4, logical properties only (`ms-*`/`me-*`/`ps-*`/`pe-*`/`start-*`/`end-*`) | Structural RTL requirement (constitution III, FR-002/FR-073) | Tailwind physical utilities (`ml-`/`mr-`/`pl-`/`pr-`/`left-`/`right-`) — forbidden outside an `rtl-exempt:`-commented, `<LtrText>`-wrapped exception |
| Components | shadcn/ui, latest | — | — |
| i18n | next-intl ^3 | — | — |
| Data fetching | TanStack Query ^5 | — | — |
| Forms | react-hook-form + zod, latest | — | — |
| Arabic typography | IBM Plex Sans Arabic, Noto Sans Arabic, or Cairo (one is selected in `data-model.md`'s companion `quickstart.md` setup, not re-litigated here) | A Latin-only stack with Arabic fallback rendering looks broken (`stack.md`, FR-002) | System Arabic fallback — rejected |
| Auth | FastAPI + JWT (access 15 min / refresh 7 days), Argon2 via passlib | Keycloak is the production target, deferred as documented debt (`docs/DEBT.md`) | Keycloak now — explicitly excluded this sprint |
| Logging | structlog, JSON output, correlation id propagated end to end | Full OpenTelemetry/Prometheus/Grafana are Phase 2; correlation ids from commit one mean instrumenting later touches no call sites | Full OTel now — deliberate debt |
| Testing | pytest for branching business logic only (status transitions, permission checks, SLA computation, tenant scoping); no tests for CRUD passthroughs; AI features scored against a bilingual golden set (20 tickets); Schemathesis against the OpenAPI contract only if time permits | Constitution XIV (Testing Proportionality) | Testcontainers / tests against real PG+Redis — deliberate debt, repaid before the first external user |

**A1 — Embedding dimension is an environment decision, not a code decision.** `data-model.md`
fixes `kb_article_chunks.embedding` at `vector(1024)` (the ≥16 GB / BGE-M3 path) because that is
what PLAN.md §4.2 specifies verbatim. If the actual development machine has <16 GB RAM, switching
to the 384-dim `e5-small` model requires a migration that alters the column type — this is called
out explicitly in `stack.md` ("Fix this before batch 4g") and is not re-decided here; it is a
pre-batch-4g checkpoint for whoever runs batch 4a–4f, not a planning ambiguity.

## Part 2 — Filling Gaps in PLAN.md §4.1's Scoping Assignment

PLAN.md §4.1 states the per-table assignment "is exhaustive; adding a table requires assigning it
a pattern," but the Assignment table as currently written in PLAN.md does not include a row for
every entity listed in §4.2, and its `channel_configs`/`llm_calls` rows are additionally
misplaced (they appear above the "Every table carries" paragraph rather than inside the
Assignment table itself) — this reads as a formatting defect from an in-place edit, not an
intentional omission, since both entities are unambiguously assigned (`channel_configs` → S1,
`llm_calls` → S5) once you read past the table break.

**This plan does not edit PLAN.md.** PLAN.md is the authoritative domain-model source
(constitution, "Authoritative Sources & Precedence"); a planning artifact does not get to rewrite
the document that governs it. The gaps below are filled here, in `data-model.md`, using PLAN.md's
own six pattern definitions and PLAN.md's own field descriptions as evidence — not invented
patterns, and not a design opinion substituted for PLAN.md's. **This should be reported back so
PLAN.md §4.1 itself can be corrected** (see the completion report) — once it is, this section
becomes redundant and can be deleted.

| Table | Pattern assigned | Evidence |
|---|---|---|
| `attachments` | **S1** (branch_id, department_id both `NOT NULL`) | §4.2 gives `attachments` two independently-nullable parent FKs (`ticket_id`, `customer_id`) — it does not have the single, mandatory parent chain that S4 (transitive) requires, so scoping it via a join is not well-defined. Direct columns are the only unambiguous choice. This also matches the constitution's earlier (pre-S1–S6) exemption note, which named `attachments` explicitly. |
| `kb_articles` | **S2** (branch_id `NOT NULL`, department_id `NULL` = branch-wide) | §4.2's `kb_articles.category_id` is not marked nullable, i.e. every article requires a category, and `categories` is itself S2 with "NULL department = branch-wide taxonomy." No rule in PLAN.md §5 F06 restricts KB search or authoring to a department, so S2 (with NULL department the expected default) is the closest fit to how the feature is actually described. **Flagged as an inference, not a restatement of an explicit PLAN.md assignment** — confirm with the domain owner when PLAN.md §4.1 is corrected. |
| `kb_article_chunks` | **S4** (transitive, via `kb_article_id` → `kb_articles`) | Textbook parent/child shape identical to `ticket_events`/`contact_methods` — a chunk has no existence or meaning independent of its article. |
| `api_keys` | **S5** (branch_id nullable) | Matches the constitution's explicit prior note ("`audit_logs`, `inbound_messages`, and `api_keys` carry `branch_id` NULLABLE — a system-level or pre-resolution record has no branch"). A machine credential may legitimately be scoped to `NULL` (organization-wide, e.g. an ERP integration spanning branches) or to one branch. |
| `audit_logs` | **S5** (branch_id nullable) | Same constitution note; also consistent with `audit_logs` recording actions on S6 (global) entities such as role/permission changes, which have no branch to attribute. |
| `inbound_messages` | **S5** (branch_id nullable) | Structurally required, not just consistent: a raw inbound message is, by definition, received *before* `channel_configs` resolution determines a branch/department (FR-023a). A `NOT NULL` branch column would make the landing table unable to do the one job it exists for. |

No table above gets more than one pattern, and none of the six patterns were altered or extended
— S1, S2, S4, and S5 (the four already in use elsewhere in PLAN.md's table) are reused as-is.

**A related, larger drift, reported but not fixed here:** the constitution's Principle IV lists
`contact_methods` and `kb_articles` among tables that "MUST carry `branch_id` and
`department_id`" (i.e. S1) — but PLAN.md §4.1 explicitly assigns `contact_methods` to **S4**
(transitive via `customers`, *no* columns), which directly contradicts that constitution
sentence. This plan follows **PLAN.md's explicit, granular per-table assignment** over the
constitution's older, coarser list, per this turn's explicit instruction ("do not add `branch_id`
or `department_id` to any table assigned S4 or S6") and per the constitution's own precedence
rule naming PLAN.md as authoritative for the domain model. The constitution's Principle IV
exemption list predates PLAN.md's S1–S6 scheme and was not fully reconciled when that scheme was
introduced. Recommended fix (not applied here, since amending the constitution is out of scope
for `/speckit.plan`): reword Principle IV to point at "PLAN.md §4.1's per-table assignment" as the
single source of truth, rather than maintaining a second, independently-drifting list of table
names.

## Part 3 — Tier D Compatibility Check (Principle XIII)

For each roadmap spec, `data-model.md` accommodates it with **zero new tables or columns beyond
what PLAN.md §4.2 already specifies**, per this turn's instruction to produce no implementation
design for Tier D. What follows records why each is still additively buildable later with no
migration touching a populated table.

| Roadmap spec | What it needs from sprint 1 | Already present? | Migration risk when built later |
|---|---|---|---|
| `specs/002-whatsapp-channel` | `tickets.channel` including `whatsapp`; `contact_methods.kind` including `whatsapp`; `inbound_messages` landing table; `channel_configs` branch/department resolution; the `ChannelAdapter` interface | **Yes — all five, verbatim in PLAN.md §4.2.** The spec's own "Why this is small" table confirms this. | None. Adding the WhatsApp adapter implementation touches no schema. |
| `specs/003-ai-chatbot` | `kb_article_chunks` with embeddings; hybrid search; the LiteLLM wrapper; `llm_calls` (with nullable `ticket_id`, needed since a chat turn has no ticket until escalation); `tickets.channel` including `chat`; new tables `chat_sessions`/`chat_messages` | KB/search/LiteLLM/`llm_calls` yes; `chat` channel value yes. `chat_sessions`/`chat_messages` are net-new tables. | **None.** A brand-new table with no existing rows is always a purely additive migration — there is nothing to migrate. `llm_calls.ticket_id` is already nullable in PLAN.md §4.2, so no ALTER is needed there either. |
| `specs/004-live-chat-sms` | `chat_sessions`/`chat_messages` (shared with 003); new `agent_presence` table; `tickets.channel` including `sms` and `chat`; `ChannelAdapter` for SMS | `sms`/`chat` channel values yes; `ChannelAdapter` yes. `agent_presence` is net-new. | **None**, same reasoning as above — a new table, not an alteration. |
| `specs/005-csat-feedback` | `tickets.csat_score`, `tickets.csat_comment`; new `csat_surveys` table | **`csat_score`/`csat_comment` are already reserved, `NULL`-able columns on `tickets` in PLAN.md §4.2**, explicitly marked `RESERVED, Tier D`. `csat_surveys` is net-new, `ticket_id`-referencing only. | None. The reserved columns are already nullable, so no existing `tickets` row needs a backfill when this ships. The new table needs no `ALTER` on `tickets`. |
| `specs/006-audit-log-ui` | Read-only queries over `audit_logs`; indexes `(actor_id, created_at)`, `(entity_type, entity_id, created_at)`, `(correlation_id)`; a distinct `audit.read` permission | `audit_logs` schema already supports every field the roadmap spec's diff/causal-chain view needs. **The three indexes are added now** (see `data-model.md`) — cheap at low row counts today, and avoids a slow index build on a large, already-populated `audit_logs` table later. **`audit.read` is seeded now** per PLAN.md §7 ("`audit.read` granted to admin"), even though nothing checks it yet. | None. Both accommodations are additive (an index, and a reference-data row) with nothing to migrate. |
| `specs/007-custom-branding` | New, nullable columns on `branches` (`logo_storage_key`, `favicon_storage_key`, `primary_color`, `accent_color`, `email_header_html`, `email_footer_html`, `portal_custom_domain`, `support_email`, `support_phone`) | Not present — deliberately not added now, since this sprint has no requirement driving them and adding unused columns would be scope creep, not accommodation. | **None even though `branches` will already hold seeded rows by then.** All nine columns are nullable `ADD COLUMN` operations, which PostgreSQL 11+ performs without a table rewrite or lock escalation. No backfill is required because `NULL` is a valid, meaningful default ("no custom branding set"). |

**Two concrete accommodations are therefore made in `data-model.md` beyond what a literal
transcription of PLAN.md §4.2 would already include:**
1. The three `audit_logs` indexes named in `specs/006`, added now rather than deferred.
2. Two permission codes seeded now — `audit.read` and `report.cross_branch` — per PLAN.md §7's
   seed data line ("`report.cross_branch` and `audit.read` granted to admin"). Both are
   reference-data rows in the `permissions` table (an S6 table); seeding them ahead of the
   features that check them is the textbook case of a Principle XIII accommodation: adding a row
   to an existing table is not a migration risk of any kind, and it means `specs/006` and the
   Tier S cross-branch-reporting requirement (FR-060) need zero `permissions`-table change when
   built.

No other Tier D roadmap item required any schema accommodation beyond what PLAN.md §4.2 already
specifies verbatim.

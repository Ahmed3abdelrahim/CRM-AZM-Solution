# CRM-AZM-Solution

## 1. What this is

A bilingual (Arabic/English) on-premise customer support CRM for a multi-branch,
multi-department organization: customers, tickets, SLA policies, a knowledge base, AI-assisted
triage, a self-service portal, and management reporting, all scoped so that a branch's or
department's data never leaks to another. It was built spec-first with
[GitHub Spec Kit](https://github.com/github/spec-kit) — every requirement traces back to a
written spec and plan under `specs/` before any code was written, and a constitution
(`.specify/memory/constitution.md`) of non-negotiable engineering rules (bilingual completeness,
tenant scoping, immutable audit trail, a single AI gateway, and ten more) gates every batch of
work.

---

## 2. Scope

Reproduced verbatim from `PLAN.md` §3:

| Tier | Meaning | Appears in spec? | Appears in data model? | Generates tasks? |
|---|---|---|---|---|
| **M** | Built this sprint | Yes | Yes | Yes |
| **S** | Contract + stub only | Yes | Yes | Yes (stub tasks) |
| **D** | Specified, not built | Yes, with acceptance criteria | Accommodated (reserved fields/tables) | **No** |

`PLAN.md` §5 defines twelve feature areas, F01–F12. Their status in this codebase:

**Complete (Tier M — built and tested this sprint)**
- F01 Customer Management
- F02 Ticket Management
- F04 Agent Dashboard (personal tasks/reminders excluded — see below)
- F05 SLA & Automation (breach-notification delivery excluded — see below)
- F06 Knowledge Base
- F07 AI Features (conversational chatbot excluded — see below)
- F10 Security & Administration (audit-browsing UI excluded — see below; the `audit_logs` table
  itself is written from day one, only the reader is missing)
- F12 Platform (custom branding excluded — see below)

**Partial (Tier S — contract plus one working slice, not the full feature)**
- F03 Communication Channels — the email adapter is functional (IMAP poll, normalize, thread);
  WhatsApp, SMS, and chat adapters exist as importable classes that raise `NotImplementedError`
- F08 Customer Portal — submit, track by reference + contact, ticket history, and published-KB
  browsing are built; portal accounts, CSAT submission, and live chat are not
- F09 Reports & Management — the three required aggregates (tickets by status, SLA compliance,
  per-agent volume) and one dashboard page are built; CSAT reporting, scheduled email delivery,
  and exports are not
- F11 Integrations — OpenAPI at `/docs`/`/openapi.json` and scoped API-key auth are built; ERP
  connectors, outbound webhooks, and retry/DLQ infrastructure are not

**Deferred to Tier D — specified with full acceptance criteria, zero code**

| Spec | Completes / extends |
|---|---|
| `specs/002-whatsapp-channel` | F03 — makes the WhatsApp adapter functional |
| `specs/003-ai-chatbot` | F07 — the conversational assistant |
| `specs/004-live-chat-sms` | F03 — SMS and live-chat adapters |
| `specs/005-csat-feedback` | F08 and F09 — portal accounts, satisfaction rating, CSAT reporting |
| `specs/006-audit-log-ui` | F10 — a searchable, filterable audit-log interface |
| `specs/007-custom-branding` | F12 — per-branch logo/color/domain branding |

Two further Tier D items have no dedicated spec yet, only a reserved slot: F04's personal
tasks/reminders and F05's breach-notification delivery (both are called out inline in `PLAN.md`
§5 and `spec.md`'s FR-032/FR-040).

**None of this needs a schema migration to build later.** `PLAN.md` §4 reserved the columns,
tables, and enum values every Tier D item needs up front — e.g. `tickets.csat_score` and
`tickets.csat_comment` already exist as nullable columns, unused until `specs/005-csat-feedback`
is implemented. Building any of `specs/002`–`specs/007` is additive code against the schema that
already exists, not a migration against live data.

---

## 3. Setup

From a clean machine, with Docker and Docker Compose installed:

```bash
git clone <this-repository-url> CRM-AZM-Solution
cd CRM-AZM-Solution/backend
cp .env.example .env
```

`.env`'s defaults work as-is — they match the credentials the bundled Postgres/Redis/MinIO
containers are configured with in `docker-compose.yml`, so the stack boots and the demo path
works without editing anything. Two things worth knowing before you do:

- `LITELLM_API_KEY` defaults to the placeholder `changeme`. Leave it alone and every AI feature
  runs in its documented fallback mode (see §7). Put a real key in to see live model output.
- `SYSTEM_DEFAULT_BRANCH_ID` / `SYSTEM_DEFAULT_DEPARTMENT_ID` must **not** be changed from the
  example values — the seed script (§4 below) derives the Cairo branch and its Customer Support
  department directly from these two settings.

Bring the stack up:

```bash
docker compose up -d
```

This builds and starts PostgreSQL 16 (with `pgvector`/`pg_trgm`), Redis 7, MinIO, the FastAPI
backend, the ARQ background worker, and the Next.js frontend. Wait for all six containers to
report healthy (`docker compose ps`), then confirm:

```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok", "database": "ok", "redis": "ok"}
```

Apply migrations and seed the demo data:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed.seed
```

The seed script is idempotent — running it a second time produces identical row counts, so it is
safe to re-run if you ever want to reset back to a known state. It does not need to be re-run
otherwise.

The frontend is at `http://localhost:3000`, the API at `http://localhost:8000/api/v1`, and
interactive API docs at `http://localhost:8000/docs`.

---

## 4. Credentials

Seeded by `backend/app/seed/seed.py`. All five users share one password: **`ChangeMe#2026`**.

| Email | Role | Branch / Department |
|---|---|---|
| `admin@azm-crm.example` | Administrator | Cairo — all three departments |
| `mona.elsherif@azm-crm.example` | Team Lead | Cairo / Customer Support |
| `ahmed.hassan@azm-crm.example` | Agent | Cairo / Customer Support |
| `layla.mahmoud@azm-crm.example` | Agent | Cairo / Sales |
| `khalid.alotaibi@azm-crm.example` | Agent | Riyadh / Customer Support |

**Demo the ticket-handling flows as `ahmed.hassan`, not `admin`.** The admin user holds roles
across all three departments rather than one home department, so its own `department_id` is
`NULL`; every tenant-scoped view that requires an exact branch-and-department match (My Open
Tickets, Unassigned, reports without an explicit cross-branch toggle, and so on) returns nothing
for `admin` by design — it is not a bug, it is the same repository-layer scoping rule (Principle
V) applied consistently. Log in as `admin` specifically to demonstrate admin-only capability:
cross-branch reports, API-key issuance, and admin CRUD.

---

## 5. Demo path

1. Open `http://localhost:3000/ar/login` and sign in as `ahmed.hassan@azm-crm.example` /
   `ChangeMe#2026`. Confirm the page renders right-to-left with no layout breakage.
2. On the dashboard, switch between the five views: *My open tickets*, *My team's queue*,
   *Unassigned*, *Breaching soon*, *Recently closed*.
3. Apply a filter (status, priority, or date range) and note the URL updates to encode it — copy
   it, open it in a new tab, and confirm the same filtered view reproduces.
4. From *Unassigned*, open the first ticket — on a freshly seeded database this is
   `TKT-2026-000001`. Confirm the customer's identity and history render inline, with no
   navigation away from the ticket.
5. Attempt to move the ticket directly to a terminal status not legal from its current one (e.g.
   `new → resolved`, using the status dropdown). Confirm the request is rejected with a localized
   422 naming the current status and the statuses actually reachable from it.
6. Now perform a legal transition instead (e.g. `new → open`). Confirm it succeeds and a new
   entry appears on the ticket's timeline, attributed to `ahmed.hassan`.
7. Scroll the timeline and confirm every prior mutation — creation, the transition just made —
   appears in order, each attributed to an actor.
8. Switch to `http://localhost:3000/ar/kb`, search `كلمة المرور`. Then switch to
   `http://localhost:3000/en/kb` and search `password`. Confirm the same underlying article
   (password reset) ranks at the top of both — one bilingual article, matched via its Arabic body
   in one search and its English body in the other.
9. Open `http://localhost:3000/ar/portal/submit` in a private/incognito window (no login).
   Submit a ticket with a name, an email or phone contact, a topic, and a description. Note the
   reference number returned.
10. Go to `http://localhost:3000/ar/portal/track`, enter that reference number and the same
    contact value. Confirm the ticket's status and customer-visible timeline appear — and that no
    internal-only note is ever present. Try the same reference number with a wrong contact value:
    confirm it returns the identical "not found" response as an unknown reference number would
    (no existence disclosure).
11. Log in as `admin@azm-crm.example` and open `http://localhost:3000/ar/reports`. Review tickets
    by status, SLA compliance, and per-agent volume with the cross-branch toggle off (scoped to
    admin's own access), then on (spanning both branches). Log in as `ahmed.hassan` instead and
    confirm the cross-branch toggle is refused (403) — cross-branch visibility is a separate,
    explicitly granted permission, not implied by any other admin capability.
    **Riyadh has no seeded SLA policies** (`PLAN.md` §7 seeds SLA policies against the Cairo
    branch only) — every Riyadh ticket therefore has no applicable policy and is excluded from
    the SLA-compliance percentage entirely, even in the cross-branch view. This is expected, not
    a bug in the report.

---

## 6. Architecture

Full detail in `docs/architecture/stack.md`; the load-bearing choices:

| Layer | Choice |
|---|---|
| API | FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2, Python 3.12 |
| Data | PostgreSQL 16 with `pgvector` and `pg_trgm` — one datastore for OLTP, full-text, and vector search |
| Jobs | ARQ over Redis 7 — categorization, SLA sweep, email poll |
| Object storage | MinIO (S3-compatible) |
| AI gateway | LiteLLM — every generative call routes through it; no vendor SDK imported anywhere else |
| Frontend | Next.js (App Router) + TypeScript + Tailwind (logical properties only) + next-intl + TanStack Query |
| Auth | JWT (access 15 min / refresh 7 days) + Argon2 password hashing; API keys for machine clients |
| Logging | structlog, JSON, correlation ID propagated end to end |

**Six shared abstractions** every feature is built on top of, rather than reimplementing
per-entity (`PLAN.md` §Shared Abstractions / §Generic CRUD Pattern):

1. **`ScopedRepository`** (`app/repositories/scoped_repository.py`) — the only place any
   branch/department/parent-join predicate is ever added to a query.
2. **Permission guard** (`app/core/permissions.py`) — `require_permission`/
   `require_permission_via` decorators; every mutating service method declares what it needs.
3. **Audit-write decorator** (`app/core/audit.py`) — `audited`/`audited_via`; writes a before/after
   snapshot inside the same transaction as the mutation it wraps.
4. **`ChannelAdapter`** (`app/channels/base.py`) — one `normalize()`/`send_reply()` interface every
   inbound channel implements; `ChannelService.ingest()` is written against the interface only.
5. **`LiteLlmWrapper`** (`app/ai/litellm_wrapper.py`) — the sole module allowed to import an LLM
   HTTP client; never raises, always records a call outcome.
6. **`AdminCrudService`** (`app/services/admin_crud_service.py`, the "Generic CRUD Pattern") — one
   generic list/get/create/update/remove implementation that ten reference-data entities
   (branches, departments, categories, priorities, statuses, SLA policies, quick replies, teams,
   roles, users) subclass instead of reimplementing.

**Tenant-scoping patterns (S1–S6)**, applied to every table (`data-model.md` §0.7):

| Pattern | Columns | Meaning |
|---|---|---|
| S1 — Fully scoped | `branch_id` NOT NULL, `department_id` NOT NULL | An operational record owned by one department |
| S2 — Branch-scoped, dept-optional | `branch_id` NOT NULL, `department_id` NULL | Configuration; `NULL` department applies to every department in the branch |
| S3 — Branch-only | `branch_id` NOT NULL | Defines or belongs to branch structure |
| S4 — Transitive | none | Scoped via a mandatory join to a scoped parent, never by adding columns |
| S5 — System-nullable | `branch_id` NULL | System-level or pre-resolution record with no owning branch |
| S6 — Global | none | Shared across every tenant; no scoping filter applied |

---

## 7. Known limitations

AI generative calls (categorization, summary, suggested reply) currently run against a local
Ollama instance on CPU, with no GPU — this is documented debt, not the intended production
configuration (`docs/DEBT.md` D13/D14). At 8–15 tokens/second, a call frequently takes far longer
than a GPU-served endpoint would, and often exceeds even the extended 60-second dev timeout, in
which case the request falls back to its documented deterministic behavior (a `NULL` suggested
category, the first 300 characters of the description as a summary, an empty reply composer) —
every screen stays usable, per Constitution Principle IX, it is simply slow when it does respond.
Production points `LITELLM_API_BASE`/`LITELLM_MODEL_CHAT`/`LITELLM_MODEL_CLASSIFY` at a
GPU-served Qwen3 endpoint instead (self-hosted vLLM or a remote provider, `docs/DEBT.md` D07) —
four environment variables, not a code change, because every generative call already routes
through the single LiteLLM gateway.

This is one entry in a larger, deliberately tracked register — see **`docs/DEBT.md`** for the
full list of shortcuts taken to fit the build budget, each with its production target and the
condition under which it should be repaid.

---

## 8. Project layout

- **`PLAN.md`** (repo root) — the master plan: product overview, non-negotiable constraints,
  scope tiers, full domain model, all twelve feature specifications (F01–F12), implementation
  batch order, seed-data shape, the deliberate-debt summary, and the Definition of Done.
- **`specs/001-bilingual-support-crm/`** — the shipped product's Spec Kit artifacts: `spec.md`
  (requirements), `plan.md` (technical design, shared abstractions, service classes),
  `data-model.md` (every table, column, and scoping pattern), `contracts/openapi.yaml` (the API
  contract everything in `backend/app/` was built against), `quickstart.md` (a longer,
  scenario-by-scenario validation script than §5 above), `tasks.md` (the full batch-by-batch task
  breakdown), and `research.md`.
- **`specs/002-*/` through `specs/007-*/`** — Tier D roadmap specs (§2 above): fully specified with
  acceptance criteria, not implemented, no schema migration required to build them.
- **`docs/architecture/stack.md`** — the authoritative technology stack and version table; any
  dependency not listed there requires justification in `research.md`.
- **`docs/DEBT.md`** — the deliberate debt register (§7 above): every shortcut taken to fit the
  build budget, its production target, and its repayment trigger.
- **`.specify/memory/constitution.md`** — fourteen non-negotiable engineering principles (bilingual
  string externalization, structural RTL parity, universal tenant attribution, repository-layer
  tenant scoping, immutable audit trails, a single AI gateway, deterministic AI degradation,
  service-layer permission enforcement, data-driven status transitions, stateless SLA derivation,
  and more) that every spec, plan, and implementation batch is checked against before merge.

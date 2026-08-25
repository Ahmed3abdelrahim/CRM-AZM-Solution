# PLAN.md — CRM-AZM-Solution

**Authoritative seed document.** Every Spec Kit phase (`constitution`, `specify`, `plan`, `tasks`, `implement`) reads this file. It is the single source of truth for scope, domain model, and business rules. If this file and a generated artifact disagree, this file wins and the artifact is regenerated.

| | |
|---|---|
| **Product** | Bilingual (Arabic/English) customer support CRM |
| **Organization shape** | Multi-branch, multi-department |
| **Deployment** | On-premise, Docker Compose, no external network dependency |
| **Time budget** | 48 hours |
| **Stack** | See `docs/architecture/stack.md` |

---

## 1. Product Overview

A support organization operates across multiple branches, each with multiple departments. Customers raise issues through several channels. Agents resolve them against service-level targets. Team leads distribute and monitor work. Administrators configure the taxonomy, the workflow, and who can do what.

The system must be fully operable in Arabic. Arabic is not a translation of an English product — it is a co-equal locale, structurally supported from the first migration.

### 1.1 Actors

| Actor | Role code | Capabilities |
|---|---|---|
| Administrator | `admin` | Full configuration: users, roles, branches, departments, categories, priorities, status lifecycle, SLA policies. Reads audit log. |
| Team Lead | `lead` | Everything an agent can do, plus reassign across the department, view team queue and performance, override SLA policy on a ticket. |
| Agent | `agent` | Own and team-visible tickets, customer records, knowledge base read, quick replies, internal notes. |
| Customer | `customer` | Own tickets only, via the portal. Submit, track, read own history, read published KB articles. |

### 1.2 The journey that defines success

An agent logs in → finds or creates a customer → raises a ticket with category and priority → the system suggests a category and a reply drawn from the knowledge base → the ticket is assigned → it moves through its lifecycle against an SLA target → it is closed → the full history of what happened and who did it is reconstructible. **In Arabic, throughout.**

---

## 2. Non-Negotiable Constraints

These are structural. Violating any of them requires a schema rewrite, not a patch.

| # | Constraint | Enforcement point |
|---|---|---|
| C1 | Every user-facing string is externalized to `ar`/`en` resource files. No hardcoded literals. | Lint rule + review |
| C2 | Every reference-data table stores `label_ar` and `label_en`, both `NOT NULL`. | Migration constraint |
| C3 | RTL and LTR share one stylesheet via CSS logical properties. No mirrored build, no direction-specific CSS file. | Tailwind config, batch 4a |
| C4 | Every domain table carries `branch_id` and `department_id`. | Migration + base model |
| C5 | Tenant scoping is applied in the repository layer, never by the caller. | `ScopedRepository` base class |
| C6 | `ticket_events` and `audit_logs` are INSERT-only. No UPDATE, no DELETE grant. | DB role permissions + trigger |
| C7 | Audit rows are written in the same transaction as the mutation. | Service-layer decorator |
| C8 | Every LLM/embedding call routes through the LiteLLM wrapper. No vendor SDK imports. | Import lint |
| C9 | Every AI feature has a deterministic fallback; the system is fully usable with the model stopped. | Per-feature acceptance criterion |
| C10 | Permissions checked in service code. UI hiding is cosmetic only. | Service-layer guard |
| C11 | Status transition legality is data-driven (table rows), not hardcoded. | `status_transitions` table |
| C12 | SLA state derived from stored timestamps, correct after full container restart. | No in-memory timers |

---

## 3. Scope Tiers

| Tier | Meaning | Appears in spec? | Appears in data model? | Generates tasks? |
|---|---|---|---|---|
| **M** | Built this sprint | Yes | Yes | Yes |
| **S** | Contract + stub only | Yes | Yes | Yes (stub tasks) |
| **D** | Specified, not built | Yes, with acceptance criteria | Accommodated (reserved fields/tables) | **No** |

---

## 4. Domain Model

### 4.1 Base

### 4.1 Base columns and scoping patterns

**Every table** carries:

```
id            UUID PK
created_at    TIMESTAMPTZ  NOT NULL
created_by    UUID FK → users
```

**Every mutable table** additionally carries:

```
updated_at    TIMESTAMPTZ  NOT NULL
updated_by    UUID FK → users
```

Insert-only tables (`ticket_events`, `audit_logs`, `inbound_messages`, `llm_calls`) MUST NOT
have `updated_at` or `updated_by` — Principle VI forbids the UPDATE that would set them.

**Reference-data tables** additionally carry `label_ar TEXT NOT NULL`,
`label_en TEXT NOT NULL`, `is_active BOOLEAN`, `sort_order INT`.

#### Scoping patterns

| Pattern | Columns | Meaning |
|---|---|---|
| **S1 — Fully scoped** | `branch_id NOT NULL`, `department_id NOT NULL` | Operational records owned by one department |
| **S2 — Branch-scoped, dept-optional** | `branch_id NOT NULL`, `department_id NULL` | Configuration; NULL department = applies to every department in the branch |
| **S3 — Branch-only** | `branch_id NOT NULL` | Defines or belongs to branch structure |
| **S4 — Transitive** | none | Child rows reachable only through a scoped parent; adding columns would be denormalization |
| **S5 — System-nullable** | `branch_id NULL` | System-level or pre-resolution records with no owning branch |
| **S6 — Global** | none | Shared across all tenants |

Patterns S1–S3 and S5 are applied by the shared base model. S4 tables are scoped by a
mandatory join to their parent, enforced in the same `ScopedRepository` base class — never by
the caller. The assignment below is exhaustive; adding a table requires assigning it a pattern.

#### Assignment

| Table | Pattern | Note |
|---|---|---|
| `branches` | S6 | Defines tenancy |
| `departments` | S3 | |
| `users` | S2 | Home branch required; operative department comes from `user_roles` |
| `roles` | S6 | |
| `permissions` | S6 | |
| `role_permissions` | S6 | |
| `user_roles` | S1 | The grant itself is scoped — this is how a user holds different roles per department |
| `teams` | S1 | |
| `team_members` | S4 | via `teams` |
| `customers` | S1 | |
| `contact_methods` | S4 | via `customers` |
| `categories` | S2 | NULL department = branch-wide taxonomy |
| `priorities` | S2 | |
| `ticket_statuses` | S2 | |
| `status_transitions` | S2 | NULL department = the default workflow |
| `sla_policies` | S2 | |
| `quick_replies` | S1 | |
| `tickets` | S1 | |
| `ticket_events` | S4 | via `tickets`;
Reference-data tables additionally inherit `label_ar TEXT NOT NULL`, `label_en TEXT NOT NULL`, `is_active BOOLEAN`, `sort_order INT`.

### 4.2 Entities

**`branches`** — `code`, `label_ar`, `label_en`, `timezone`, `business_hours` (JSONB: per-weekday open/close), `is_active`

**`departments`** — `branch_id`, `code`, `label_ar`, `label_en`, `is_active`

**`users`** — `email` (unique), `password_hash` (Argon2), `full_name_ar`, `full_name_en`, `phone`, `locale` (`ar`|`en`), `is_active`, `last_login_at`

**`roles`** — `code` (`admin`|`lead`|`agent`|`customer`), `label_ar`, `label_en`

**`permissions`** — `code` (e.g. `ticket.assign`, `ticket.close`, `customer.delete`, `admin.config`), `label_ar`, `label_en`

**`role_permissions`** — `role_id`, `permission_id`

**`user_roles`** — `user_id`, `role_id`, `branch_id`, `department_id` — a user may hold different roles in different departments

**`teams`** — `label_ar`, `label_en`, `department_id`; **`team_members`** — `team_id`, `user_id`

**`customers`** — `customer_type` (`individual`|`organization`), `full_name_ar`, `full_name_en` (nullable), `national_id` (nullable), `organization_name` (nullable), `preferred_locale`, `notes`, `is_active`

**`contact_methods`** — `customer_id`, `kind` (`phone`|`email`|`whatsapp`|`other`), `value`, `is_primary`, `is_verified`

**`categories`** — `parent_id` (self-referencing, nullable), `label_ar`, `label_en`, `department_id` (nullable = global), `sort_order`, `is_active`

**`priorities`** — `code`, `label_ar`, `label_en`, `severity` (int, lower = more urgent), `color`

**`ticket_statuses`** — `code`, `label_ar`, `label_en`, `is_terminal`, `pauses_sla`, `sort_order`

**`status_transitions`** — `from_status_id`, `to_status_id`, `department_id` (nullable = global), `required_permission` (nullable), `requires_reason` (bool). *This table IS the workflow engine.*

**`tickets`**
```
reference_no      TEXT UNIQUE   -- e.g. TKT-2026-000001
customer_id       FK → customers
subject           TEXT
description       TEXT
category_id       FK → categories
priority_id       FK → priorities
status_id         FK → ticket_statuses
assignee_id       FK → users        NULL
team_id           FK → teams        NULL
channel           ENUM(web|email|whatsapp|sms|chat|portal)
source_locale     CHAR(2)
sla_policy_id     FK → sla_policies NULL
first_response_at TIMESTAMPTZ       NULL
resolved_at       TIMESTAMPTZ       NULL
closed_at         TIMESTAMPTZ       NULL
reopened_count    INT DEFAULT 0
sla_paused_ms     BIGINT DEFAULT 0  -- accumulated pause duration
ai_suggested_category_id  FK → categories NULL   -- what AI proposed
ai_category_confidence    NUMERIC(4,3)    NULL
csat_score        INT NULL          -- RESERVED, Tier D
csat_comment      TEXT NULL         -- RESERVED, Tier D
```

**`ticket_events`** — INSERT-only
```
ticket_id, actor_id, event_type, field_name, old_value (JSONB),
new_value (JSONB), body (TEXT, for notes/replies), visibility
(internal|customer), reason (TEXT), correlation_id, created_at
```
`event_type` ∈ `created | status_changed | assigned | reassigned | field_changed | note_added | reply_sent | attachment_added | sla_breached | reopened | ai_suggestion_applied`

**`attachments`** — `ticket_id` (nullable), `customer_id` (nullable), `filename`, `content_type`, `size_bytes`, `storage_key` (MinIO), `uploaded_by`

**`sla_policies`** — `label_ar`, `label_en`, `category_id` (nullable), `priority_id` (nullable), `first_response_minutes`, `resolution_minutes`, `business_hours_only` (bool). *Resolution order: exact category+priority match → priority-only → category-only → default.*

**`quick_replies`** — `label_ar`, `label_en`, `body_ar`, `body_en`, `department_id`, `category_id` (nullable)

**`kb_articles`** — `slug`, `title_ar`, `title_en`, `body_ar`, `body_en`, `category_id`, `is_published`, `view_count`, `helpful_count`

**`kb_article_chunks`** — `article_id`, `locale`, `chunk_index`, `content`, `embedding vector(1024)` — BGE-M3 dimensionality

**`api_keys`** — `label`, `key_hash`, `scopes` (JSONB), `last_used_at`, `expires_at`

**`audit_logs`** — INSERT-only — `actor_id`, `action`, `entity_type`, `entity_id`, `before` (JSONB), `after` (JSONB), `ip_address`, `user_agent`, `correlation_id`, `created_at`

**`inbound_messages`** — `channel`, `external_id`, `raw_payload` (JSONB), `normalized` (JSONB), `ticket_id` (nullable), `processed_at`, `error` — the channel abstraction's landing table

### 4.3 Status lifecycle (seed data for `status_transitions`)

| From | Permitted to | Notes |
|---|---|---|
| `new` | `open`, `in_progress`, `closed` | `closed` from `new` = cancelled, requires reason |
| `open` | `in_progress`, `pending_customer`, `resolved`, `closed` | |
| `in_progress` | `open`, `pending_customer`, `resolved` | |
| `pending_customer` | `in_progress`, `resolved`, `closed` | `pauses_sla = true` |
| `resolved` | `closed`, `reopened` | |
| `closed` | `reopened` | terminal; requires `ticket.reopen` permission |
| `reopened` | `in_progress`, `resolved` | increments `reopened_count` |

Any transition not in this table is rejected with a localized error naming the current status and the permitted targets.

---

## 5. Feature Specifications

Each block below is a specification unit. Acceptance criteria are testable without reading code.

---

### F01 — Customer Management · Tier M

**Purpose.** Agents find or create the person behind a ticket, and see everything that has ever happened with them.

**Rules.**
- A customer belongs to exactly one branch and one department.
- At least one contact method is required at creation; exactly one is `is_primary`.
- Search matches across `full_name_ar`, `full_name_en`, `organization_name`, and all contact values, using trigram similarity so Arabic partial matches and transliteration variants both work.
- Deactivation is soft. Customers are never hard-deleted — their ticket history must survive.

**API.** `GET/POST /customers`, `GET/PATCH /customers/{id}`, `POST /customers/{id}/deactivate`, `GET /customers/{id}/history`, `GET/POST /customers/{id}/contact-methods`, `POST /customers/{id}/attachments`

**Acceptance.**
1. Creating a customer with an Arabic name and searching a three-character Arabic substring returns them.
2. `GET /customers/{id}/history` returns a chronological merge of all tickets and all `ticket_events` for that customer.
3. A customer with tickets cannot be hard-deleted; the endpoint does not exist.
4. Creating a customer produces exactly one `audit_logs` row in the same transaction.

---

### F02 — Ticket Management · Tier M

**Purpose.** The core record. Everything else in the product hangs off it.

**Rules.**
- `reference_no` format `TKT-{YYYY}-{6-digit sequence}`, generated by a DB sequence, unique forever, quotable by customers.
- Category and priority are required. Both must be active and, if department-scoped, must match the ticket's department.
- Status changes go through the transition service, which checks `status_transitions`, the actor's permission, and `requires_reason`. Illegal transitions return HTTP 422 with a localized message.
- Assignment to an agent and to a team are independent — a ticket may be team-queued with no individual owner.
- Every mutation writes a `ticket_events` row. The timeline is the ticket's history; there is no separate history feature.
- `first_response_at` is stamped on the first `reply_sent` event with `visibility = customer`. It is never overwritten.

**API.** `GET/POST /tickets`, `GET/PATCH /tickets/{id}`, `POST /tickets/{id}/status`, `POST /tickets/{id}/assign`, `GET /tickets/{id}/events`, `POST /tickets/{id}/notes`, `POST /tickets/{id}/replies`, `POST /tickets/{id}/attachments`

**Acceptance.**
1. A ticket created in Arabic renders correctly RTL in the agent UI and the portal.
2. Attempting `new → resolved` returns 422 naming the current status and permitted targets in the caller's locale.
3. `closed → reopened` succeeds for a user with `ticket.reopen` and increments `reopened_count`; it returns 403 without it.
4. `GET /tickets/{id}/events` returns every mutation in order, each attributed to an actor.
5. No API path exists that can modify or delete a `ticket_events` row.

---

### F03 — Communication Channels · Tier S

**Purpose.** Prove the abstraction. Ship one working adapter.

**Rules.**
- One interface: `ChannelAdapter.normalize(raw) → NormalizedMessage{external_id, channel, from_identity, subject, body, locale, attachments[]}`.
- All inbound traffic lands in `inbound_messages` first, then is converted to a ticket or appended to an existing thread. Raw payload is retained.
- Identity resolution: match `from_identity` against `contact_methods.value`. No match → create a customer with that contact method.
- Threading: match on `external_id` or on `reference_no` found in the subject line.
- **Email adapter is functional** (IMAP poll via ARQ). **WhatsApp, SMS, live chat adapters exist and raise `NotImplementedError`.**
- `POST /channels/inbound` accepts a pre-normalized payload with API-key auth — this is how any future channel integrates without touching ticket logic.

**Acceptance.**
1. Posting a normalized payload for an unknown sender creates a customer and a ticket.
2. Posting one containing an existing `reference_no` in the subject appends a `ticket_events` row instead of creating a ticket.
3. Adding a hypothetical new channel requires implementing the interface only — zero changes to ticket creation code.

---

### F04 — Agent Dashboard · Tier M *(tasks and reminders → Tier D)*

**Purpose.** Where agents spend their day.

**Rules.**
- Views: *My open tickets*, *My team's queue*, *Unassigned*, *Breaching soon* (< 25% of SLA remaining), *Recently closed*.
- Filters: status, priority, category, assignee, channel, date range, free-text. Filter state is URL-encoded and shareable.
- The ticket detail view shows customer context inline — no navigation required to see who they are and what they've raised before.
- Quick replies insert `body_ar` or `body_en` matching the ticket's `source_locale`, with placeholder substitution (`{{customer_name}}`, `{{reference_no}}`, `{{agent_name}}`).
- Internal notes (`visibility = internal`) are visually distinct and never exposed on the portal.

**Acceptance.**
1. Switching UI language to Arabic flips the entire dashboard to RTL with no layout breakage and no page reload.
2. An internal note never appears in any portal response — verified by a test asserting on the portal serializer.
3. *Breaching soon* returns tickets ordered by time remaining ascending.

---

### F05 — SLA & Automation · Tier M *(notification delivery → Tier D)*

**Purpose.** Make targets measurable and work distribute itself.

**Rules.**
- Policy resolution on ticket create: category+priority → priority → category → default.
- `first_response_due_at` and `resolution_due_at` are **computed at query time** from `created_at`, the policy, `sla_paused_ms`, and — when `business_hours_only` — the branch's `business_hours` and timezone.
- Entering a status with `pauses_sla = true` records a pause start in `ticket_events`; leaving it accumulates elapsed time into `sla_paused_ms`.
- Breach states: `on_track` | `at_risk` (< 25% remaining) | `breached`. Derived, never stored.
- An ARQ job sweeps every 5 minutes, writes an `sla_breached` event once per ticket per target, and escalates by raising priority one severity level and reassigning to the department's lead.
- Auto-assignment: round-robin across active agents in the department who have the `ticket.own` permission, skipping anyone flagged unavailable.

**Acceptance.**
1. A ticket parked in `pending_customer` for two hours shows a resolution deadline two hours later than before.
2. `docker compose restart` then re-query: every breach state is identical. No timer state was held in memory.
3. Business-hours policies do not accrue elapsed time outside the branch's configured hours or in its timezone.
4. The breach sweep is idempotent — running it twice produces one `sla_breached` event.

---

### F06 — Knowledge Base · Tier M

**Purpose.** Answers that agents reuse and the AI retrieves from.

**Rules.**
- Articles carry both `title_ar`/`body_ar` and `title_en`/`body_en`. Publishing requires both to be non-empty.
- On save, body is chunked per locale (~500 tokens, 50 overlap) and embedded with BGE-M3 into `kb_article_chunks`.
- Search is hybrid: `pg_trgm` lexical + `pgvector` cosine, fused by reciprocal rank, then reranked with `bge-reranker-v2-m3`. If the reranker is unavailable, fused order is returned.
- **Do not rely on PostgreSQL's Arabic text-search configuration.** Its stemming is inadequate for Arabic morphology — trigram plus semantic is the working path.

**Acceptance.**
1. An Arabic query returns relevant Arabic articles ranked above unrelated ones.
2. An English query for the same concept returns the same article via its English body.
3. Publishing with an empty Arabic body is rejected.
4. With the embedding model stopped, search still returns lexical results.

---

### F07 — AI Features · Tier M *(chatbot → Tier D)*

**Purpose.** Reduce agent handling time. Never block the agent.

Four capabilities, all through the LiteLLM wrapper, all with fallbacks.

| Capability | Model | Trigger | Fallback |
|---|---|---|---|
| Auto-categorization | Qwen3-4B | On ticket create | `ai_suggested_category_id = NULL`; agent picks manually |
| Ticket summary | Qwen3-32B | On demand, and on tickets with > 5 events | Show first 300 chars of description |
| Suggested reply | Qwen3-32B | On demand in the reply composer | Composer opens empty |
| Suggested solution | Retrieval + rerank | On ticket open | Suggestion panel does not render |

**Rules.**
- Categorization returns `{category_id, confidence}`. It **never** sets `category_id` directly — it populates `ai_suggested_category_id`, and the agent accepts or overrides. Acceptance writes an `ai_suggestion_applied` event.
- Output locale always matches `source_locale`. An Arabic ticket gets an Arabic summary and an Arabic suggested reply.
- Suggested replies are drafts. They are never auto-sent under any configuration.
- Suggested solutions are the top 3 KB articles from F06's hybrid search using the ticket subject and description as the query.
- Every call is traced to Langfuse with token counts, latency, model name, and prompt version.
- Timeout 10s, one retry, then fallback. AI latency never blocks the ticket-create response — categorization runs as an ARQ job.

**Acceptance.**
1. Stop the vLLM container. Every screen remains fully usable; no error dialogs; all four fallbacks engage.
2. An Arabic ticket produces an Arabic summary and Arabic suggested reply.
3. Accepting a suggested category writes an `ai_suggestion_applied` event recording both the suggestion and the confidence.
4. Ticket creation latency is unaffected by model availability.
5. A bilingual golden set of 20 tickets is scored for categorization accuracy and the result is recorded.

---

### F08 — Customer Portal · Tier S

**Rules.**
- Submit a ticket (name, contact, subject, description, category, attachments) and track by `reference_no` + the contact method used.
- History view lists the customer's own tickets. Internal notes are never present in the response payload.
- Published KB articles are browsable without authentication.
- **Tier D within this area:** full portal accounts, feedback/CSAT submission, live chat widget.

**Acceptance.**
1. Submitting through the portal creates a ticket with `channel = portal`.
2. Tracking with a valid reference but a mismatched contact method returns 404, not 403 — no existence disclosure.
3. No portal endpoint returns any `visibility = internal` event.

---

### F09 — Reports & Management · Tier S

**Rules.** Three aggregates plus one dashboard page:
- Tickets by status, filterable by branch, department, and date range
- SLA compliance percentage — first-response and resolution, separately
- Per-agent volume: assigned, resolved, average resolution time

All respect the caller's branch/department scope. Admin may pass an explicit cross-branch scope.
**Tier D within this area:** CSAT reporting, scheduled email reports, exports.

**Acceptance.** A lead's report covers only their own department. An admin's covers all branches when explicitly scoped.

---

### F10 — Security & Administration · Tier M *(audit browsing UI → Tier D)*

**Rules.**
- JWT access (15 min) + refresh (7 days). Argon2 password hashing.
- Permission checks in service methods via a guard decorator. Every service method that mutates declares its required permission.
- Admin CRUD for branches, departments, users, roles, categories, priorities, statuses, transitions, SLA policies, quick replies.
- Audit rows written by a service-layer decorator inside the mutation's transaction. **The audit table is written from day one; only the browsing interface is deferred.**

**Acceptance.**
1. An agent calling an admin endpoint receives 403 even with a UI that would have shown the control.
2. Every mutating endpoint produces exactly one audit row containing before and after state.
3. A rolled-back transaction leaves no audit row.
4. `UPDATE` and `DELETE` on `audit_logs` fail at the database level.

---

### F11 — Integrations · Tier S

**Rules.** OpenAPI served at `/docs` and `/openapi.json`. API-key auth with scoped permissions for machine clients. Keys stored hashed, scopes enforced by the same service-layer guard as user permissions.
**Tier D:** ERP connectors, outbound webhooks, retry/DLQ infrastructure.

**Acceptance.** An API key scoped to `ticket.read` can list tickets and receives 403 on create.

---

### F12 — Platform · Tier M *(custom branding → Tier D)*

Not a feature — a set of cross-cutting requirements verified on every other feature.

| Requirement | Verification |
|---|---|
| Arabic & English throughout | Every screen switchable; no untranslated string |
| Correct RTL | Logical properties only; grep the codebase for `ml-`, `mr-`, `pl-`, `pr-`, `left-`, `right-` returns nothing |
| Arabic typography | IBM Plex Sans Arabic / Noto Sans Arabic / Cairo — not a Latin-only stack with fallback |
| Responsive | Usable at 375px width |
| Multi-department | Every query department-scoped at the repository layer |
| Multi-branch | Every query branch-scoped at the repository layer |

---

## 6. Implementation Batches

| Batch | Contents | Gate |
|---|---|---|
| 4a | Compose (PG, Redis, MinIO), Alembic baseline, config, health endpoints, Tailwind RTL config, next-intl scaffold | `docker compose up` clean; migrations apply; RTL toggle works on a placeholder page |
| 4b | F10 — users, roles, permissions, JWT, guard decorator, audit writer | Login works; audit row on every mutation; rollback leaves none |
| 4c | F01 — customers, contact methods, notes, attachments, history | Arabic substring search returns results |
| 4d | F02 — categories, priorities, statuses, transitions, tickets, timeline, assignment | Full journey to closure; illegal transition returns localized 422 |
| 4e | F04 + F12 — dashboard, queues, filters, quick replies, Arabic UI shell | Entire interface usable in Arabic |
| 4f | F05 — SLA policies, pause accounting, breach derivation, sweep job, round-robin | Breach state identical after `docker compose restart` |
| 4g | F06 — articles, chunking, embeddings, hybrid search | AR and EN queries both return the same relevant article |
| 4h | F07 — LiteLLM wrapper, four capabilities, four fallbacks, Langfuse | All screens usable with vLLM stopped |
| 4i | F03 + F08 + F09 + F11 — webhook, email adapter, portal, reports, API keys, seed data | Demo path end to end |

Commit and `/clear` between every batch.

---

## 7. Seed Data

2 branches (different timezones and business hours) · 3 departments · 5 users covering all four roles · 20 customers with Arabic and English names · 40 tickets spread across all statuses, priorities, and channels, some breaching · 10 KB articles fully bilingual · category tree 3 levels deep · 4 priorities · 7 statuses with the full transition table · 3 SLA policies · 8 quick replies.

Seeds must be idempotent and runnable via one command.

---

## 8. Deliberate Debt

Logged in `docs/DEBT.md`. Each item is a conscious 48-hour trade, not an oversight.

| Shortcut | Production target | Repay when |
|---|---|---|
| In-app JWT | Keycloak SSO + AD | Before multi-tenant rollout |
| SLA derived on read | Background timer service | Phase 2 |
| No testcontainers | Integration tests on real PG/Redis | Before first external user |
| No OTel tracing | Full distributed tracing | Phase 2 |
| Single Compose host | Kubernetes | Before HA requirement |
| Email polling | Push/webhook ingestion | When volume demands it |

---

## 9. Bilingual Glossary

Consistency here prevents three different Arabic words appearing for the same concept across the UI.

| English | Arabic | Notes |
|---|---|---|
| Ticket | تذكرة | |
| Customer | عميل | |
| Agent | موظف الدعم | |
| Priority | الأولوية | |
| Category | التصنيف | |
| Status | الحالة | |
| Open | مفتوحة | |
| In Progress | قيد المعالجة | |
| Pending Customer | بانتظار العميل | |
| Resolved | تم الحل | |
| Closed | مغلقة | |
| Reopened | أعيد فتحها | |
| Assign | إسناد | |
| Escalate | تصعيد | |
| Knowledge Base | قاعدة المعرفة | |
| Branch | الفرع | |
| Department | القسم | |
| Attachment | مرفق | |
| Internal Note | ملاحظة داخلية | |
| Reference Number | الرقم المرجعي | |

---

## 10. Definition of Done

- [ ] `docker compose up` reaches a working, seeded system on a clean machine
- [ ] Full ticket journey completes in Arabic
- [ ] Illegal status transition rejected with a localized reason
- [ ] Every mutation produces an audit row in the same transaction
- [ ] SLA breach state correct after full restart
- [ ] All four AI capabilities respond, and all four degrade gracefully with the model stopped
- [ ] Bilingual KB search returns relevant results in both locales
- [ ] OpenAPI at `/docs` covers all Tier M and Tier S endpoints
- [ ] Codebase grep for direction-specific CSS utilities returns nothing
- [ ] `README.md` documents setup, seed, demo path, and the tier table from §3
- [ ] `docs/DEBT.md` matches §8

# Data Model: Bilingual Support CRM — Core Product

**Source of truth**: PLAN.md §4 (Domain Model), binding on every entity, field, and constraint
below. Two categories of table (`attachments`, `kb_articles`/`kb_article_chunks`, `api_keys`,
`audit_logs`, `inbound_messages`) were missing from PLAN.md §4.1's own Assignment table; their
pattern assignment is resolved and justified in `research.md` Part 2, not invented here. Nothing
in PLAN.md §4.2 is removed or renamed. Indexes and foreign keys are added as needed per this
document's own §0.4/§0.5 conventions.

## 0. Conventions (apply uniformly; not restated per table)

### 0.1 Base columns — every table

| Column | Type | Null? | Default |
|---|---|---|---|
| `id` | `UUID` | NOT NULL, PK | server-generated (v4) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |
| `created_by` | `UUID` FK → `users.id` (ON DELETE SET NULL) | NULL | — (NULL only for system/seed-created rows) |

### 0.2 Additional base columns — every **mutable** table (i.e. every table except the four
insert-only tables in §0.3)

| Column | Type | Null? | Default |
|---|---|---|---|
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()`, updated on every write |
| `updated_by` | `UUID` FK → `users.id` (ON DELETE SET NULL) | NULL | |

### 0.3 Insert-only tables

`ticket_events`, `audit_logs`, `inbound_messages`, `llm_calls`. Per PLAN.md §4.1 these **MUST
NOT** have `updated_at`/`updated_by` — Principle VI (constitution) forbids the UPDATE that would
ever set them. Enforced at the DB role/trigger layer per PLAN.md C6 (§3 below).

### 0.4 Reference-data label base — applied only to tables whose PLAN.md §4.2 entry lists
`label_ar`, `label_en` as fields: `branches`, `departments`, `roles`, `permissions`, `categories`,
`priorities`, `ticket_statuses`, `sla_policies`, `quick_replies`, `teams`.

| Column | Type | Null? | Default |
|---|---|---|---|
| `label_ar` | `TEXT` | NOT NULL | |
| `label_en` | `TEXT` | NOT NULL | |

This is the *only* universally-applied part (it is what PLAN.md C2 actually requires: "every
reference-data table stores `label_ar` and `label_en`, both `NOT NULL`"). **`is_active` and
`sort_order` are NOT part of this shared base** — PLAN.md §4.2 lists them per table inconsistently
(e.g. `branches.is_active` exists, `roles.is_active` does not; `categories.sort_order` exists,
`sla_policies.sort_order` does not), so each is added only where §4.2 explicitly names it for that
specific table, per this table:

| Table | `is_active`? | `sort_order`? |
|---|---|---|
| `branches` | ✓ | — |
| `departments` | ✓ | — |
| `roles` | — | — |
| `permissions` | — | — |
| `categories` | ✓ | ✓ |
| `priorities` | — | — |
| `ticket_statuses` | — | ✓ |
| `sla_policies` | — | — |
| `quick_replies` | — | — |
| `teams` | — | — |

A table with no `is_active` column is **hard-deletable** (§0.6) rather than soft-deactivatable —
there is no flag to toggle. This is not a gap; it is what "Admin CRUD" (PLAN.md F10) means for a
table PLAN.md never gave a deactivation flag: the "D" is a real `DELETE`, guarded by `ON DELETE
RESTRICT` on every table that references it, so deleting a row still in use fails cleanly instead
of silently orphaning data.

### 0.5 Enumerated values — implemented as `TEXT` + `CHECK`, never a native Postgres `ENUM` type

PLAN.md writes several fields as `ENUM(...)`. They are implemented here as `TEXT` with a `CHECK
(col IN (...))` constraint, not a native Postgres `ENUM` type, for one specific reason: extending a
native Postgres enum type is a schema migration that historically could not run inside the same
transaction as other DDL; extending a `CHECK` constraint is a single, ordinary, always-transactional
migration. This is an implementation-mechanics choice, not a business-rule change — the permitted
value sets below are exactly what PLAN.md specifies, unchanged.

`ticket_statuses.code` and `categories.code`-equivalents are **plain `TEXT`, with no `CHECK`
constraint at all** — Principle XI / PLAN.md C11 requires status legality to be data-driven via
the `status_transitions` table, so the set of valid status codes is *rows in a table*, never a
fixed list baked into a `CHECK` constraint or an application `match`/`switch` statement.

### 0.6 Foreign key delete behavior (applied uniformly; not restated per FK below)

- FK to a **reference-data table** (branches, departments, roles, permissions, categories,
  priorities, ticket_statuses, sla_policies, quick_replies, teams): `ON DELETE RESTRICT`. For the
  four with an `is_active` column (`branches`, `departments`, `categories`, plus `users` and
  `customers` elsewhere in this document), rows are deactivated in normal operation and this only
  guards a manual `DELETE` bypassing the service layer. For the five *without* one (`roles`,
  `permissions`, `priorities`, `ticket_statuses`, `sla_policies`, `quick_replies`, `teams`),
  deletion is the real, exposed operation (§0.4), and `RESTRICT` is what makes it safe: it fails
  the moment the row is actually referenced anywhere.
- FK from a true parent-owned child row (`ticket_events`→`tickets`, `contact_methods`→`customers`,
  `team_members`→`teams`, `kb_article_chunks`→`kb_articles`, `role_permissions`→`roles`/
  `permissions`): `ON DELETE CASCADE`. Defensive only — `customers` and `tickets` are never hard-
  deleted per FR-013/FR-006, so this path is not expected to fire in normal operation.
- FK to `users` (`created_by`, `updated_by`, `assignee_id`, `actor_id`, etc.): `ON DELETE SET
  NULL`, except `ticket_events.actor_id` and `audit_logs.actor_id`, which are `ON DELETE
  RESTRICT` — an insert-only accountability record must never lose its attribution.
- `attachments.ticket_id` / `attachments.customer_id`: both `ON DELETE CASCADE` (each nullable,
  see §1.16 — an attachment belongs to whichever one is non-null).

### 0.7 Scoping patterns (verbatim from PLAN.md §4.1)

| Pattern | Columns | Meaning |
|---|---|---|
| **S1 — Fully scoped** | `branch_id NOT NULL`, `department_id NOT NULL` | Operational record owned by one department |
| **S2 — Branch-scoped, dept-optional** | `branch_id NOT NULL`, `department_id NULL` | Configuration; `NULL` department = applies to every department in the branch |
| **S3 — Branch-only** | `branch_id NOT NULL` | Defines or belongs to branch structure |
| **S4 — Transitive** | none | Child rows reachable only through a scoped parent; scoped via a mandatory join to that parent inside `ScopedRepository`, never by adding columns |
| **S5 — System-nullable** | `branch_id NULL` | System-level or pre-resolution record with no owning branch |
| **S6 — Global** | none | Shared across all tenants; no scoping filter applied |

## 1. Entities

Each entry: pattern, then fields **additional** to the applicable base(s) in §0. FKs and indexes
follow §0.6's delete-behavior convention unless stated otherwise.

### 1.1 `branches` — S6

| Column | Type | Null? | Notes |
|---|---|---|---|
| `code` | `TEXT` | NOT NULL, UNIQUE | |
| `timezone` | `TEXT` (IANA name) | NOT NULL | |
| `business_hours` | `JSONB` | NOT NULL | per-weekday open/close, e.g. `{"mon": {"open":"08:00","close":"17:00"}, ...}` |

*(+ `label_ar`, `label_en`, `is_active` per §0.4 — no `sort_order`, not listed in PLAN.md §4.2 for
this table.)*

No `branch_id`/`department_id` columns — S6. Top of the tenancy hierarchy; nothing scopes *to* it
via a parent join.

### 1.2 `departments` — S3

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S3 scoping column |
| `code` | `TEXT` | NOT NULL | UNIQUE per `(branch_id, code)` |

*(+ `label_ar`, `label_en`, `is_active` per §0.4 — no `sort_order`.)*

**Index**: `(branch_id, code)` UNIQUE.

### 1.3 `users` — S2

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column — home branch |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column; operative department per assignment actually comes from `user_roles`, not this column — this is a home/default only |
| `email` | `TEXT` | NOT NULL, UNIQUE | |
| `password_hash` | `TEXT` | NOT NULL | Argon2 (passlib) |
| `full_name_ar` | `TEXT` | NOT NULL | |
| `full_name_en` | `TEXT` | NOT NULL | |
| `phone` | `TEXT` | NULL | |
| `locale` | `TEXT` | NOT NULL | `CHECK (locale IN ('ar','en'))`, default `'ar'` |
| `is_active` | `BOOLEAN` | NOT NULL | default `true` |
| `last_login_at` | `TIMESTAMPTZ` | NULL | |

**Index**: `email` UNIQUE (already); `(branch_id, is_active)`.

### 1.4 `roles` — S6

| Column | Type | Null? | Notes |
|---|---|---|---|
| `code` | `TEXT` | NOT NULL, UNIQUE | `CHECK (code IN ('admin','lead','agent','customer'))` |

*(+ `label_ar`, `label_en` per §0.4. No `is_active`/`sort_order` — not listed in PLAN.md §4.2 for
this table, so removal of a role is a hard `DELETE`, `RESTRICT`-guarded by `user_roles`/
`role_permissions` referencing it.)*

### 1.5 `permissions` — S6

| Column | Type | Null? | Notes |
|---|---|---|---|
| `code` | `TEXT` | NOT NULL, UNIQUE | dotted form, e.g. `ticket.assign` — see §4 for the seeded set |

*(+ `label_ar`, `label_en` per §0.4. No `is_active`/`sort_order`.)* Not in PLAN.md F10's "Admin
CRUD" list — this table is read-only through the API (seeded and migration-managed only); only
*assigning* a permission to a role is admin-editable (`role_permissions`, below).

### 1.6 `role_permissions` — S6

| Column | Type | Null? | Notes |
|---|---|---|---|
| `role_id` | `UUID` FK → `roles.id`, CASCADE | NOT NULL | |
| `permission_id` | `UUID` FK → `permissions.id`, CASCADE | NOT NULL | |

*(+ `updated_at`/`updated_by` per §0.2 — like every other mutable table; this is not one of the
four insert-only tables in §0.3, and PLAN.md's base-column rule draws no exception for join
tables, so none is invented here either.)*

**Index**: `(role_id, permission_id)` UNIQUE.

### 1.7 `user_roles` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `user_id` | `UUID` FK → `users.id`, CASCADE | NOT NULL | |
| `role_id` | `UUID` FK → `roles.id`, RESTRICT | NOT NULL | |

**Index**: `(user_id, role_id, branch_id, department_id)` UNIQUE. This table is *how* a user holds
different roles in different departments (PLAN.md §4.2) — a user's full permission set for a given
request is the union of `role_permissions` reachable via every `user_roles` row matching the
request's resolved branch/department.

### 1.8 `teams` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |

*(+ `label_ar`, `label_en` per §0.4. No `is_active`/`sort_order` — hard `DELETE`. `team_members`
rows cascade-delete with it (§0.6); `tickets.team_id` is `SET NULL` (§1.16), so a team-queued
ticket survives its team being deleted, simply becoming unassigned-to-a-team rather than blocking
the deletion.)*

### 1.9 `team_members` — S4 (via `teams`)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `team_id` | `UUID` FK → `teams.id`, CASCADE | NOT NULL | parent for S4 scoping join |
| `user_id` | `UUID` FK → `users.id`, CASCADE | NOT NULL | |

**Index**: `(team_id, user_id)` UNIQUE. No `branch_id`/`department_id` — scoped transitively
through `teams` inside `ScopedRepository`.

### 1.10 `customers` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `customer_type` | `TEXT` | NOT NULL | `CHECK (customer_type IN ('individual','organization'))` |
| `full_name_ar` | `TEXT` | NOT NULL | |
| `full_name_en` | `TEXT` | NULL | |
| `national_id` | `TEXT` | NULL | |
| `organization_name` | `TEXT` | NULL | |
| `preferred_locale` | `TEXT` | NOT NULL | `CHECK (preferred_locale IN ('ar','en'))` |
| `notes` | `TEXT` | NULL | |
| `is_active` | `BOOLEAN` | NOT NULL | default `true` — deactivation flag (FR-013); never hard-deleted |

**Indexes**:
- `GIN (full_name_ar gin_trgm_ops)`, `GIN (full_name_en gin_trgm_ops)`,
  `GIN (organization_name gin_trgm_ops)` — trigram indexes backing FR-012's approximate search.
- `(branch_id, department_id, is_active)`.

Per FR-023 / the Customer key entity, identity is per branch/department by construction: the S1
scoping columns are exactly what make "the same person contacting two branches produces two
customer records" true without any extra modeling — they are simply two different rows, never
merged.

### 1.11 `contact_methods` — S4 (via `customers`)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `customer_id` | `UUID` FK → `customers.id`, CASCADE | NOT NULL | parent for S4 scoping join |
| `kind` | `TEXT` | NOT NULL | `CHECK (kind IN ('phone','email','whatsapp','other'))` |
| `value` | `TEXT` | NOT NULL | |
| `is_primary` | `BOOLEAN` | NOT NULL | default `false` |
| `is_verified` | `BOOLEAN` | NOT NULL | default `false` |

**Indexes**:
- `GIN (value gin_trgm_ops)` — backs FR-012 and FR-023's contact-method matching.
- **Partial unique** `(customer_id) WHERE is_primary` — enforces FR-011's "exactly one contact
  method is primary" at the database level, not just in service code.

No `branch_id`/`department_id` — scoped transitively through `customers`. Note: FR-023's "matching
MUST NOT be performed across branches" means every lookup against this table is issued through
`ScopedRepository` with the *message's resolved* `TenantScope` already applied to the `customers`
join — see `plan.md` §ScopedRepository for the exact mechanism.

### 1.12 `categories` — S2

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column; `NULL` = branch-wide taxonomy |
| `parent_id` | `UUID` FK → `categories.id`, RESTRICT | NULL | self-referencing, up to 3 levels deep per seed data |

*(+ reference-data base §0.4 — `label_ar`, `label_en`, `is_active`, `sort_order`.)*

### 1.13 `priorities` — S2

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column |
| `code` | `TEXT` | NOT NULL | plain `TEXT`, unique per `(branch_id, department_id, code)` — not a native enum (§0.5) |
| `severity` | `INT` | NOT NULL | lower = more urgent |
| `color` | `TEXT` | NOT NULL | |

*(+ `label_ar`, `label_en` per §0.4. No `is_active`/`sort_order` — hard `DELETE`, `RESTRICT`-
guarded by `tickets`/`sla_policies` referencing it.)*

### 1.14 `ticket_statuses` — S2

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column |
| `code` | `TEXT` | NOT NULL | plain `TEXT`, no `CHECK` — §0.5. Unique per `(branch_id, department_id, code)` |
| `is_terminal` | `BOOLEAN` | NOT NULL | |
| `pauses_sla` | `BOOLEAN` | NOT NULL | |

*(+ `label_ar`, `label_en`, `sort_order` per §0.4. No `is_active` — PLAN.md §4.2 lists `sort_order`
for this table but not `is_active`, so a status is hard-`DELETE`d, `RESTRICT`-guarded by
`tickets`/`status_transitions` referencing it, not deactivated.)*

### 1.15 `status_transitions` — S2 — **this table is the workflow engine (Principle XI)**

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column; `NULL` = the default workflow |
| `from_status_id` | `UUID` FK → `ticket_statuses.id`, RESTRICT | NOT NULL | |
| `to_status_id` | `UUID` FK → `ticket_statuses.id`, RESTRICT | NOT NULL | |
| `required_permission` | `TEXT` | NULL | a `permissions.code` value, checked at runtime — not an FK, since it is meaningful even before/without a row existing yet in a fresh seed order |
| `requires_reason` | `BOOLEAN` | NOT NULL | default `false` |

**Index**: `(branch_id, department_id, from_status_id, to_status_id)` UNIQUE. No `label_ar`/
`label_en`/`is_active`/`sort_order` — not in PLAN.md §4.2's field list for this table, and it is
not a labeled lookup a user browses, so §0.4 does not apply here.

The transition service (`TicketTransitionService`, `plan.md`) does exactly one query against this
table to decide legality — see `plan.md`'s service signatures. No status code, transition, or
permission check is ever hardcoded in application code.

### 1.16 `tickets` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `reference_no` | `TEXT` | NOT NULL, UNIQUE | format `TKT-{YYYY}-{6-digit sequence}`, DB-sequence-generated |
| `customer_id` | `UUID` FK → `customers.id`, RESTRICT | NOT NULL | |
| `subject` | `TEXT` | NOT NULL | |
| `description` | `TEXT` | NOT NULL | |
| `category_id` | `UUID` FK → `categories.id`, RESTRICT | NOT NULL | |
| `priority_id` | `UUID` FK → `priorities.id`, RESTRICT | NOT NULL | |
| `status_id` | `UUID` FK → `ticket_statuses.id`, RESTRICT | NOT NULL | |
| `assignee_id` | `UUID` FK → `users.id`, SET NULL | NULL | |
| `team_id` | `UUID` FK → `teams.id`, SET NULL | NULL | |
| `channel` | `TEXT` | NOT NULL | `CHECK (channel IN ('web','email','whatsapp','sms','chat','portal'))` |
| `source_locale` | `CHAR(2)` | NOT NULL | `CHECK (source_locale IN ('ar','en'))` |
| `sla_policy_id` | `UUID` FK → `sla_policies.id`, RESTRICT | NULL | |
| `first_response_at` | `TIMESTAMPTZ` | NULL | set once, never overwritten (FR-021) |
| `resolved_at` | `TIMESTAMPTZ` | NULL | |
| `closed_at` | `TIMESTAMPTZ` | NULL | |
| `reopened_count` | `INT` | NOT NULL | default `0` |
| `sla_paused_ms` | `BIGINT` | NOT NULL | default `0`, accumulated pause duration |
| `needs_triage` | `BOOLEAN` | NOT NULL | default `false` — set when channel-config resolution fell back to the system default (FR-023a) |
| `ai_suggested_category_id` | `UUID` FK → `categories.id`, SET NULL | NULL | what the AI proposed; never copied into `category_id` directly (FR-044) |
| `ai_category_confidence` | `NUMERIC(4,3)` | NULL | |
| `csat_score` | `INT` | NULL | **RESERVED, Tier D** (`specs/005-csat-feedback`) — no `CHECK` range constraint added yet since nothing writes it this sprint; add `CHECK (csat_score BETWEEN 1 AND 5)` when `specs/005` is built |
| `csat_comment` | `TEXT` | NULL | **RESERVED, Tier D** (`specs/005-csat-feedback`) |

**Indexes**:
- `reference_no` UNIQUE (already).
- `(branch_id, department_id, status_id)` — dashboard queue queries (F04).
- `(assignee_id, status_id)` — "my open tickets" (F04).
- `(team_id, status_id)` — "my team's queue" (F04).
- `(department_id, status_id) WHERE assignee_id IS NULL` — "unassigned" queue, including
  `needs_triage` tickets (F04, FR-023a).
- `(created_at)` — SLA sweep (F05) and reporting (F09).
- `(status_id) WHERE needs_triage` — partial index for the triage surface.

### 1.17 `ticket_events` — S4 (via `tickets`) — **insert-only** (§0.3)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `ticket_id` | `UUID` FK → `tickets.id`, CASCADE | NOT NULL | parent for S4 scoping join |
| `actor_id` | `UUID` FK → `users.id`, RESTRICT | NULL | `NULL` only for system-generated events (e.g. the SLA sweep's `sla_breached` event) |
| `event_type` | `TEXT` | NOT NULL | `CHECK (event_type IN ('created','status_changed','assigned','reassigned','field_changed','note_added','reply_sent','attachment_added','sla_breached','reopened','ai_suggestion_applied'))` — exactly PLAN.md §4.2's list, no value added. FR-023c's needs-triage correction (old/new branch and department) is recorded as a `field_changed` event with `field_name = 'branch_id'` or `'department_id'`, reusing the existing generic old/new-value shape rather than inventing a new `event_type`. |
| `field_name` | `TEXT` | NULL | |
| `old_value` | `JSONB` | NULL | |
| `new_value` | `JSONB` | NULL | |
| `body` | `TEXT` | NULL | notes/replies |
| `visibility` | `TEXT` | NOT NULL | `CHECK (visibility IN ('internal','customer'))` |
| `reason` | `TEXT` | NULL | populated when the triggering action's `requires_reason` was true |
| `correlation_id` | `UUID` | NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | (no `updated_at`/`updated_by` — §0.3) |

**Indexes**: `(ticket_id, created_at)` — the timeline query (FR-020); `(correlation_id)`.

No `branch_id`/`department_id` — scoped transitively through `tickets`.

### 1.18 `attachments` — **S1** (see `research.md` Part 2 for why, not S4)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `ticket_id` | `UUID` FK → `tickets.id`, CASCADE | NULL | exactly one of `ticket_id`/`customer_id` must be non-null — `CHECK (num_nonnulls(ticket_id, customer_id) = 1)` |
| `customer_id` | `UUID` FK → `customers.id`, CASCADE | NULL | see above |
| `filename` | `TEXT` | NOT NULL | |
| `content_type` | `TEXT` | NOT NULL | |
| `size_bytes` | `BIGINT` | NOT NULL | |
| `storage_key` | `TEXT` | NOT NULL, UNIQUE | MinIO object key |
| `uploaded_by` | `UUID` FK → `users.id`, SET NULL | NULL | |

**Index**: `(ticket_id)`, `(customer_id)`.

### 1.19 `sla_policies` — S2

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column |
| `category_id` | `UUID` FK → `categories.id`, RESTRICT | NULL | |
| `priority_id` | `UUID` FK → `priorities.id`, RESTRICT | NULL | |
| `first_response_minutes` | `INT` | NOT NULL | |
| `resolution_minutes` | `INT` | NOT NULL | |
| `business_hours_only` | `BOOLEAN` | NOT NULL | default `false` |

*(+ `label_ar`, `label_en` per §0.4. No `is_active`/`sort_order` — hard `DELETE`, `RESTRICT`-
guarded by `tickets.sla_policy_id` referencing it.)*

**Index**: `(branch_id, department_id, category_id, priority_id)` — backs the resolution-order
query (exact match → priority-only → category-only → default; FR-033).

### 1.20 `quick_replies` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `body_ar` | `TEXT` | NOT NULL | |
| `body_en` | `TEXT` | NOT NULL | |
| `category_id` | `UUID` FK → `categories.id`, RESTRICT | NULL | |

*(+ `label_ar`, `label_en` per §0.4 — the reply's display name, distinct from `body_ar`/`body_en`,
its inserted content. No `is_active`/`sort_order` — hard `DELETE`.)*

### 1.21 `kb_articles` — **S2** (see `research.md` Part 2)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S2 scoping column |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NULL | S2 scoping column |
| `slug` | `TEXT` | NOT NULL | UNIQUE per `(branch_id, slug)` |
| `title_ar` | `TEXT` | NOT NULL | required non-empty to publish (FR-041) |
| `title_en` | `TEXT` | NOT NULL | required non-empty to publish |
| `body_ar` | `TEXT` | NOT NULL | required non-empty to publish |
| `body_en` | `TEXT` | NOT NULL | required non-empty to publish |
| `category_id` | `UUID` FK → `categories.id`, RESTRICT | NOT NULL | |
| `is_published` | `BOOLEAN` | NOT NULL | default `false` |
| `view_count` | `INT` | NOT NULL | default `0` |
| `helpful_count` | `INT` | NOT NULL | default `0` |

**Index**: `GIN (body_ar gin_trgm_ops)`, `GIN (body_en gin_trgm_ops)` — lexical half of hybrid
search (F06); `(category_id)`.

### 1.22 `kb_article_chunks` — **S4** (via `kb_articles`; see `research.md` Part 2)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `kb_article_id` | `UUID` FK → `kb_articles.id`, CASCADE | NOT NULL | parent for S4 scoping join |
| `locale` | `TEXT` | NOT NULL | `CHECK (locale IN ('ar','en'))` |
| `chunk_index` | `INT` | NOT NULL | |
| `content` | `TEXT` | NOT NULL | |
| `embedding` | `vector(1024)` | NOT NULL | BGE-M3 dimensionality — see `research.md` A1 for the <16GB-RAM alternative dimension |

**Indexes**: `(kb_article_id, locale, chunk_index)` UNIQUE; an approximate nearest-neighbor index
on `embedding` (HNSW, `vector_cosine_ops`) — semantic half of hybrid search (F06); `GIN (content
gin_trgm_ops)`.

No `branch_id`/`department_id` — scoped transitively through `kb_articles`.

### 1.23 `api_keys` — **S5** (see `research.md` Part 2)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NULL | S5 scoping column |
| `label` | `TEXT` | NOT NULL | |
| `key_hash` | `TEXT` | NOT NULL, UNIQUE | |
| `scopes` | `JSONB` | NOT NULL | array of `permissions.code` values |
| `last_used_at` | `TIMESTAMPTZ` | NULL | |
| `expires_at` | `TIMESTAMPTZ` | NULL | |

### 1.24 `audit_logs` — **S5** (see `research.md` Part 2) — **insert-only** (§0.3)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NULL | S5 scoping column |
| `actor_id` | `UUID` FK → `users.id`, RESTRICT | NULL | `NULL` only for a system-initiated action |
| `action` | `TEXT` | NOT NULL | e.g. `create`, `update`, `deactivate`, `admin.config.update` |
| `entity_type` | `TEXT` | NOT NULL | |
| `entity_id` | `UUID` | NOT NULL | |
| `before` | `JSONB` | NULL | |
| `after` | `JSONB` | NULL | |
| `ip_address` | `TEXT` | NULL | |
| `user_agent` | `TEXT` | NULL | |
| `correlation_id` | `UUID` | NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | (no `updated_at`/`updated_by` — §0.3) |

**Indexes** *(added now — `specs/006-audit-log-ui` accommodation, see `research.md` Part 3)*:
`(actor_id, created_at)`, `(entity_type, entity_id, created_at)`, `(correlation_id)`.

### 1.25 `inbound_messages` — **S5** (see `research.md` Part 2) — **insert-only** (§0.3)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NULL | S5 scoping column — `NULL` until/unless a ticket is resolved from it; the resolved ticket carries the real scope (see FR-023a) |
| `channel` | `TEXT` | NOT NULL | `CHECK (channel IN ('web','email','whatsapp','sms','chat','portal'))` |
| `external_id` | `TEXT` | NOT NULL | |
| `raw_payload` | `JSONB` | NOT NULL | retained verbatim for traceability |
| `normalized` | `JSONB` | NULL | populated once `ChannelAdapter.normalize()` succeeds |
| `ticket_id` | `UUID` FK → `tickets.id`, SET NULL | NULL | |
| `processed_at` | `TIMESTAMPTZ` | NULL | |
| `error` | `TEXT` | NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | (no `updated_at`/`updated_by` — §0.3) |

**Index**: `(channel, external_id)` UNIQUE — prevents double-processing the same inbound payload
on webhook/poll retry; `(ticket_id)`.

### 1.26 `channel_configs` — S1

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NOT NULL | S1 scoping column — the branch a message at `identifier` resolves to |
| `department_id` | `UUID` FK → `departments.id`, RESTRICT | NOT NULL | S1 scoping column |
| `channel` | `TEXT` | NOT NULL | `CHECK (channel IN ('web','email','whatsapp','sms','chat','portal'))` |
| `identifier` | `TEXT` | NOT NULL, UNIQUE | mailbox address or phone number |
| `default_category_id` | `UUID` FK → `categories.id`, SET NULL | NULL | |
| `is_active` | `BOOLEAN` | NOT NULL | default `true` |

### 1.27 `llm_calls` — **S5** (given in PLAN.md §4.1) — **insert-only** (§0.3)

| Column | Type | Null? | Notes |
|---|---|---|---|
| `branch_id` | `UUID` FK → `branches.id`, RESTRICT | NULL | S5 scoping column |
| `ticket_id` | `UUID` FK → `tickets.id`, SET NULL | NULL | nullable — a future chatbot turn (`specs/003`) has no ticket until escalation |
| `capability` | `TEXT` | NOT NULL | `CHECK (capability IN ('categorize','summarize','suggest_reply','suggest_solution'))` |
| `model` | `TEXT` | NOT NULL | |
| `prompt_version` | `TEXT` | NOT NULL | |
| `input_tokens` | `INT` | NULL | |
| `output_tokens` | `INT` | NULL | |
| `latency_ms` | `INT` | NOT NULL | |
| `fallback_used` | `BOOLEAN` | NOT NULL | |
| `error` | `TEXT` | NULL | |
| `correlation_id` | `UUID` | NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | (no `updated_at`/`updated_by` — §0.3) |

**Index**: `(ticket_id, created_at)`, `(capability, created_at)`.

## 2. Scoping Assignment — Complete Table

| Table | Pattern | Table | Pattern |
|---|---|---|---|
| `branches` | S6 | `ticket_statuses` | S2 |
| `departments` | S3 | `status_transitions` | S2 |
| `users` | S2 | `tickets` | S1 |
| `roles` | S6 | `ticket_events` | S4 (via `tickets`) |
| `permissions` | S6 | `attachments` | S1 |
| `role_permissions` | S6 | `sla_policies` | S2 |
| `user_roles` | S1 | `quick_replies` | S1 |
| `teams` | S1 | `kb_articles` | S2 |
| `team_members` | S4 (via `teams`) | `kb_article_chunks` | S4 (via `kb_articles`) |
| `customers` | S1 | `api_keys` | S5 |
| `contact_methods` | S4 (via `customers`) | `audit_logs` | S5 |
| `categories` | S2 | `inbound_messages` | S5 |
| `priorities` | S2 | `channel_configs` | S1 |
| | | `llm_calls` | S5 |

Every table has exactly one pattern. No pattern beyond the six PLAN.md §4.1 defines is used.
`attachments`, `kb_articles`, `kb_article_chunks`, `api_keys`, `audit_logs`, and `inbound_messages`
are resolved gaps — see `research.md` Part 2 for the evidence behind each.

## 3. Constraint Enforcement Map (PLAN.md §2, C1–C12)

| # | Constraint | Enforced here by |
|---|---|---|
| C2 | Reference-data `label_ar`/`label_en` both `NOT NULL` | §0.4 base, applied to all ten reference-data tables |
| C4 | Every domain table carries `branch_id`+`department_id` | Not literal for every table — PLAN.md §4.1 itself defines S3/S4/S5/S6 as the documented exceptions to a naive reading of C4; C4 is satisfied by "every table has a pattern from §4.1," not by every table having both columns |
| C6 | `ticket_events`/`audit_logs` insert-only | §0.3; DB role grants revoking `UPDATE`/`DELETE` on these four tables, plus `inbound_messages`/`llm_calls`, are a migration-time concern (`plan.md` §Project Structure, `alembic/versions/`), not a data-model concern |
| C11 | Status legality is data-driven | §1.15 `status_transitions`; §0.5 forbids a native enum or hardcoded status list anywhere |
| C12 | SLA state derived from stored timestamps only | No SLA-state column exists anywhere in this schema — `tickets.first_response_at`/`resolved_at`/`sla_paused_ms` are the only stored facts; breach state is computed, never stored (`plan.md` §SlaService) |

C1, C3, C5, C7–C10 are not schema-level constraints — they are enforced in code (`plan.md`'s five
shared abstractions and service layer) and are out of `data-model.md`'s scope by definition.

## 4. Seed Data — `status_transitions` (from PLAN.md §4.3)

Seeded once per branch/department combination using the **default workflow** (`department_id =
NULL`), so every department starts on the identical table below unless an admin later adds a
department-specific override row — the transition service always checks the department-specific
row first, then falls back to the `NULL`-department default (same resolution shape as
`categories`/`sla_policies`).

| From status | Permitted to | `requires_reason` | `required_permission` |
|---|---|---|---|
| `new` | `open` | false | — |
| `new` | `in_progress` | false | — |
| `new` | `closed` | **true** | — (cancellation) |
| `open` | `in_progress` | false | — |
| `open` | `pending_customer` | false | — |
| `open` | `resolved` | false | — |
| `open` | `closed` | false | — |
| `in_progress` | `open` | false | — |
| `in_progress` | `pending_customer` | false | — |
| `in_progress` | `resolved` | false | — |
| `pending_customer` | `in_progress` | false | — |
| `pending_customer` | `resolved` | false | — |
| `pending_customer` | `closed` | false | — |
| `resolved` | `closed` | false | — |
| `resolved` | `reopened` | false | `ticket.reopen` |
| `closed` | `reopened` | false | `ticket.reopen` |
| `reopened` | `in_progress` | false | — |
| `reopened` | `resolved` | false | — |

`ticket_statuses` seed rows: `new`, `open`, `in_progress`, `pending_customer` (`pauses_sla=true`),
`resolved`, `closed` (`is_terminal=true`), `reopened` — 7 rows, matching PLAN.md §7's seed count.
Any `(from_status, to_status)` pair not in this table is illegal — rejected per FR-017, with no
code path that special-cases a status by name.

## 5. Seeded Permission Codes

From PLAN.md §4.2's examples, PLAN.md §7's explicit seed instruction, and this spec's FR-039/
FR-060 resolutions:

| Code | Purpose |
|---|---|
| `admin.config` | **Write-only** for the ten Generic CRUD Pattern entities (branches, departments, users, roles, categories, priorities, ticket statuses, SLA policies, quick replies, teams) plus `status_transitions` (list/create/update/delete subset) — `create`/`update`/`delete`/`deactivate` only. Granted to `admin` only. |
| `branch.read`, `department.read`, `user.read`, `role.read`, `category.read`, `priority.read`, `ticket_status.read`, `status_transition.read`, `sla_policy.read`, `quick_reply.read`, `team.read` | **Read** for the same eleven entities (`list`/`get`) — split from `admin.config` after `/speckit-analyze` finding D1: an Agent building a ticket-creation form or reply composer needs to read categories, priorities, teams, and quick replies, but never held `admin.config`. Granted to `agent`, `lead`, and `admin`. |
| `ticket.read`, `ticket.create` | Base CRUD, also the pair F11's acceptance criterion exercises for scoped API keys |
| `ticket.assign` | Assigning/reassigning a ticket (FR-019, F04) |
| `ticket.close` | Closing a ticket |
| `ticket.reopen` | Reopening a resolved/closed ticket (FR-018, §4 above) |
| `ticket.own` | Eligibility for SLA auto-assignment round-robin (FR-038) |
| `ticket.sla_override` | Team Lead's SLA policy override (FR-039) |
| `customer.read`, `customer.create` | Base CRUD |
| `customer.delete` | Guards the deactivation endpoint (FR-013) — named `delete` per PLAN.md §4.2's own example despite the operation being a soft deactivation; the permission code is not renamed, only its bound behavior is documented here as deactivation, not a hard delete (no hard-delete endpoint exists at all) |
| `report.cross_branch` | **Seeded now, granted to `admin` per PLAN.md §7** — FR-060's distinct, separately-grantable cross-branch reporting permission |
| `audit.read` | **Seeded now, granted to `admin` per PLAN.md §7** — Tier D accommodation for `specs/006-audit-log-ui`; nothing checks it yet |

Full CRUD-permission naming convention (`{entity}.read`/`.create`/`.update`/`.deactivate`) for
every other S1/S2/S3 entity not named above (e.g. `kb_article.read`, `kb_article.publish`) is
defined once in `plan.md`'s "Generic CRUD Pattern" section rather than enumerated per entity here.

## 5.1 Role → Permission Grants (seed-time — closes `/speckit-analyze` finding E1)

Every permission code in §5 above, mapped to the role(s) it is granted to at seed time
(`app/seed/seed.py`, `data-model.md` §4's `roles` rows: `admin`, `lead`, `agent` — `customer` is
the portal's unauthenticated/no-login actor and holds none of these). This table is exhaustive:
every code in §5 appears exactly once below.

| Permission code(s) | Granted to |
|---|---|
| `admin.config` | `admin` only |
| `audit.read` | `admin` only |
| `report.cross_branch` | `admin` only |
| `customer.delete` | `admin` only |
| `ticket.sla_override` | `lead`, `admin` |
| `ticket.reopen` | `lead`, `admin` |
| `ticket.assign` | `lead`, `admin` |
| `ticket.read`, `ticket.create`, `ticket.close`, `ticket.own` | `agent`, `lead`, `admin` |
| `customer.read`, `customer.create` | `agent`, `lead`, `admin` |
| `branch.read`, `department.read`, `user.read`, `role.read`, `category.read`, `priority.read`, `ticket_status.read`, `status_transition.read`, `sla_policy.read`, `quick_reply.read`, `team.read` | `agent`, `lead`, `admin` |

This is what makes Story 2 Acceptance Scenario 3 / FR-018 / `quickstart.md` step 4.6 concretely
true of the seeded system: a seeded `agent` does not hold `ticket.reopen` (403 on reopen), a
seeded `lead` does (succeeds, `reopened_count` increments) — without this table, that behavior
depended on an implementer's guess. `ticket.assign` is `lead`+`admin` only (not `agent`) so that
FR-031's "Team Lead can additionally reassign across the entire department" is a real capability
delta over Agent, not a distinction with no enforcement difference; an Agent still assigns/claims
their own tickets via `TicketService.assign` called on their own queue, gated the same as any
other `ticket.assign`-holding actor — Agents not holding `ticket.assign` at all is the simplest
rule that satisfies both FR-019 (agents can be assigned to) and FR-031 (only Leads reassign)
without inventing a second, narrower permission code PLAN.md never names.

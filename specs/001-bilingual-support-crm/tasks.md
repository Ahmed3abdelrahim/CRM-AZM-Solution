---
description: "Task list for Bilingual Support CRM — Tier M/S implementation, organized by PLAN.md §6 batches"
---

# Tasks: Bilingual Support CRM — Core Product

**Input**: `plan.md`, `data-model.md`, `contracts/openapi.yaml`, `research.md`, `quickstart.md`,
`spec.md` — all in `specs/001-bilingual-support-crm/`

**Scope**: Tier M and Tier S requirements only. No task exists anywhere in this document for a
Tier D capability (PLAN.md §3, constitution Principle XIII) — Tier D is specified in `spec.md`
and accommodated in `data-model.md`, and that is the entirety of its footprint here.

**Organization**: Batches 4a–4i, exactly as ordered in PLAN.md §6 — **not** by user story. This
is a deliberate deviation from this template's default (user-story phases): PLAN.md §6's batch
sequence is itself the dependency order this 48-hour sprint is built and demoed in, each batch
ending in a commit + `/clear` (constitution, Development Workflow), so it is the organizing
structure requested for this run. `[Story]` labels are correspondingly omitted throughout —
every task instead cites the PLAN.md feature area (F01–F12) and/or `spec.md` FR-### it serves.

**Tests**: Included, but only where constitution Principle XIV (Testing Proportionality) actually
requires them — status transition legality, permission checks, SLA computation, tenant scoping.
No test task exists for a CRUD passthrough. AI features are scored against the golden set, not
covered by unit tests.

## Format: `[ID] [P?] Description with exact file path(s)`

- **[P]**: Can run in parallel with other [P] tasks in the same batch (different files, no
  ordering dependency between them)
- Every task names the exact file(s) it creates or modifies, per `plan.md`'s file tree
- Each batch ends with a **Gate** task: the PLAN.md §6 verification for that batch, phrased as
  something checkable by running a command or clicking through a screen — never "read the code"

---

## Batch 4a — Compose, schema, shared abstractions, RTL/i18n scaffold

**Contents (PLAN.md §6)**: Compose (PG, Redis, MinIO), Alembic baseline, config, health
endpoints, Tailwind RTL config, next-intl scaffold — **plus, per this run's explicit instruction,
all five shared abstractions before any entity work begins.** Every later batch depends on this
one being complete.

**Design decision carried over from `plan.md`**: the Alembic baseline is the *complete* schema
from `data-model.md` §1 in one migration (`alembic/versions/0001_initial.py`), matching `plan.md`'s
file tree, which lists exactly one migration file for the whole project. Later batches add
services/routers/UI against this already-complete schema — none of them touches
`alembic/versions/` again.

- [X] T001 Create `backend/docker-compose.yml`, `backend/Dockerfile`, `backend/.env.example` — services: postgres (16, `pgvector`+`pg_trgm`), redis (7), minio, backend (FastAPI), arq-worker, frontend (Next.js), per `docs/architecture/stack.md`
- [X] T002 [P] Create `backend/pyproject.toml` — Python 3.12, FastAPI ^0.115, SQLAlchemy ^2.0 (async), Alembic ^1.14, Pydantic ^2.9, Uvicorn ^0.32, ARQ ^0.26, httpx ^0.27, litellm, passlib[argon2], structlog, pytest — exact versions from `docs/architecture/stack.md`, nothing else
- [X] T003 [P] Create `frontend/package.json` — Next.js ^15, TypeScript ^5.6, Tailwind ^3.4, shadcn/ui, next-intl ^3, TanStack Query ^5, react-hook-form + zod
- [X] T004 Create `backend/app/config.py` — Pydantic `Settings`: `DATABASE_URL`, `REDIS_URL`, MinIO creds, `LITELLM_API_BASE`/`LITELLM_API_KEY`/`LITELLM_MODEL_CHAT`/`LITELLM_MODEL_CLASSIFY`, JWT secrets + TTLs (15 min access / 7 day refresh), `SYSTEM_DEFAULT_BRANCH_ID`, `SYSTEM_DEFAULT_DEPARTMENT_ID` (depends on T002)
- [X] T005 Create `backend/app/db.py` — async engine + session factory, `get_session()` dependency, one transaction per request (depends on T004)
- [X] T006 Create `backend/app/models/base.py` — `Base`, id/`created_at`/`created_by` mixin (data-model.md §0.1), `updated_at`/`updated_by` mixin (§0.2) (depends on T005)
- [X] T007 [P] Create `backend/app/models/branch.py` — `Branch` (S6; `data-model.md` §1.1) (depends on T006)
- [X] T008 [P] Create `backend/app/models/department.py` — `Department` (S3; §1.2) (depends on T006)
- [X] T009 [P] Create `backend/app/models/user.py` — `User` (S2; §1.3) (depends on T006)
- [X] T010 [P] Create `backend/app/models/role.py` — `Role`, `Permission`, `RolePermission` (all S6; §1.4–1.6) (depends on T006)
- [X] T011 [P] Create `backend/app/models/user_role.py` — `UserRole` (S1; §1.7) (depends on T006)
- [X] T012 [P] Create `backend/app/models/team.py` — `Team` (S1), `TeamMember` (S4 via `teams`) (§1.8–1.9) (depends on T006)
- [X] T013 [P] Create `backend/app/models/customer.py` — `Customer` (S1), `ContactMethod` (S4 via `customers`, partial-unique-primary constraint) (§1.10–1.11) (depends on T006)
- [X] T014 [P] Create `backend/app/models/category.py` — `Category` (S2, self-referencing `parent_id`) (§1.12) (depends on T006)
- [X] T015 [P] Create `backend/app/models/priority.py` — `Priority` (S2, no `is_active`/`sort_order`) (§1.13) (depends on T006)
- [X] T016 [P] Create `backend/app/models/ticket_status.py` — `TicketStatus` (S2, `sort_order` only) (§1.14) (depends on T006)
- [X] T017 [P] Create `backend/app/models/status_transition.py` — `StatusTransition` (S2, no reference-data label fields) (§1.15) (depends on T006)
- [X] T018 [P] Create `backend/app/models/ticket.py` — `Ticket` (S1; every field in §1.16 incl. `needs_triage`, `ai_suggested_category_id`, reserved `csat_score`/`csat_comment`) (depends on T006)
- [X] T019 [P] Create `backend/app/models/ticket_event.py` — `TicketEvent` (S4 via `tickets`, insert-only, `event_type` CHECK with exactly PLAN.md §4.2's 11 values) (§1.17) (depends on T006)
- [X] T020 [P] Create `backend/app/models/attachment.py` — `Attachment` (S1, exactly-one-of-ticket/customer CHECK) (§1.18) (depends on T006)
- [X] T021 [P] Create `backend/app/models/sla_policy.py` — `SlaPolicy` (S2, no `is_active`/`sort_order`) (§1.19) (depends on T006)
- [X] T022 [P] Create `backend/app/models/quick_reply.py` — `QuickReply` (S1, no `is_active`/`sort_order`) (§1.20) (depends on T006)
- [X] T023 [P] Create `backend/app/models/kb_article.py` — `KbArticle` (S2), `KbArticleChunk` (S4 via `kb_articles`, `vector(1024)`) (§1.21–1.22) (depends on T006)
- [X] T024 [P] Create `backend/app/models/api_key.py` — `ApiKey` (S5) (§1.23) (depends on T006)
- [X] T025 [P] Create `backend/app/models/audit_log.py` — `AuditLog` (S5, insert-only) (§1.24) (depends on T006)
- [X] T026 [P] Create `backend/app/models/inbound_message.py` — `InboundMessage` (S5, insert-only) (§1.25) (depends on T006)
- [X] T027 [P] Create `backend/app/models/channel_config.py` — `ChannelConfig` (S1) (§1.26) (depends on T006)
- [X] T028 [P] Create `backend/app/models/llm_call.py` — `LlmCall` (S5, insert-only) (§1.27) (depends on T006)
- [X] T029 Create `backend/alembic/env.py`, `backend/alembic.ini` — async Alembic config (depends on T005)
- [X] T030 Create `backend/alembic/versions/0001_initial.py` — every table in `data-model.md` §1 (all 27), every index, every FK with the ON DELETE behavior in §0.6, `pgvector`/`pg_trgm` extensions, the `reference_no` DB sequence, and — per constitution Principle VI / PLAN.md C6 — revokes `UPDATE`/`DELETE` grants (via trigger) on `ticket_events`, `audit_logs`, `inbound_messages`, `llm_calls` (depends on T007–T028)
- [X] T031 [P] Create `backend/app/repositories/scoped_repository.py` — `ScopingMode`, `TenantScope`, `ScopedRepository` exactly per `plan.md` §Shared Abstractions #1, including the `_scoped_select()` behavior for all six modes and the `has_soft_delete`-gated `delete()`/`deactivate()` split (depends on T006)
- [X] T032 [P] Create `backend/app/core/permissions.py` — `CurrentActor`, `PermissionDeniedError`, `require_permission`, `require_permission_via` exactly per `plan.md` §Shared Abstractions #2 (depends on T006)
- [X] T033 [P] Create `backend/app/core/audit.py` — `audited` decorator exactly per `plan.md` §Shared Abstractions #3 (before/after snapshot, same-transaction write, no independent commit) (depends on T025)
- [X] T034 [P] Create `backend/app/channels/base.py` — `NormalizedAttachment`, `NormalizedMessage`, `ChannelAdapter` protocol exactly per `plan.md` §Shared Abstractions #4 (depends on T006)
- [X] T035 [P] Create `backend/app/ai/litellm_wrapper.py` — `LlmCapability`, `LlmResult`, `LiteLlmWrapper` exactly per `plan.md` §Shared Abstractions #5 (never raises; writes one `llm_calls` row per call via its own session) (depends on T028)
- [X] T036 [P] Create `backend/tests/unit/test_scoped_repository.py` — one test per `ScopingMode` (S1–S6) verifying `_scoped_select()` includes/excludes rows correctly, plus one test that an S4 repository never emits a `branch_id`/`department_id` predicate (constitution Principle V; Testing Proportionality — tenant scoping) (depends on T031)
- [X] T037 Create `backend/app/core/errors.py` — `PermissionDeniedError`→403, `IllegalTransitionError`→422, `NotFoundError`→404, all serialized as `ErrorResponse{message_ar, message_en}` (depends on T032)
- [X] T038 [P] Create `backend/app/core/lint_no_vendor_sdk.py` — import-lint failing the build if any module besides `app/ai/litellm_wrapper.py` imports an LLM vendor SDK/HTTP client for LLM use (constitution Principle VIII / PLAN.md C8) (depends on T035)
- [X] T039 Create `backend/app/main.py` — FastAPI app factory, structlog JSON logging + correlation-id middleware, mounts `app.api.router` (depends on T037)
- [X] T040 [P] Create `backend/app/api/router.py` (empty aggregator, routers added in later batches) and `backend/app/api/routers/health.py` — `GET /health` per `contracts/openapi.yaml` (depends on T039)
- [X] T041 [P] Create `frontend/tailwind.config.ts` — logical properties only (no `ml-`/`mr-`/`pl-`/`pr-`/`left-`/`right-` utilities enabled) (depends on T003)
- [X] T042 [P] Create `frontend/messages/ar.json`, `frontend/messages/en.json` — scaffold with a handful of placeholder keys (depends on T003)
- [X] T043 Create `frontend/app/[locale]/layout.tsx` — sets `<html dir>` from the active locale via next-intl; the only place `dir` is set anywhere in the frontend (depends on T041, T042)
- [X] T044 [P] Create `frontend/components/ltr-text.tsx` — `<LtrText>`, sets `dir="ltr"` locally (constitution Principle III) (depends on T041)
- [X] T045 Create a placeholder page at `frontend/app/[locale]/(agent)/dashboard/page.tsx` containing only a locale switcher and one `<LtrText>`-wrapped sample value, to exercise the RTL toggle for this batch's gate (depends on T043, T044)
- [X] T045a [P] Create `frontend/scripts/check-i18n-literals.sh` — a grep-based check (not an
      ESLint rule) scanning `frontend/app/` and `frontend/components/` for JSX string literals
      (text between tags, and string-valued `label`/`title`/`placeholder`/`aria-label` props) not
      routed through a `next-intl` translation call (`useTranslations`/`t(...)`), exiting non-zero
      on any hit; wire it as an npm script (`"check:i18n"`) in `frontend/package.json` (constitution
      Principle I / PLAN.md C1's stated enforcement point — added after `/speckit-analyze` finding
      E1, since PLAN.md C8's equivalent import-lint (T038) already existed but C1's did not)
      (depends on T003, T045)

**Gate (PLAN.md §6)**: `docker compose up` reaches a healthy state for every service with zero
restarts; `docker compose exec backend alembic upgrade head` applies cleanly with no errors;
opening the placeholder dashboard page and switching the locale switcher flips the page's reading
direction immediately, with no page reload and no console error, and the `<LtrText>` sample stays
left-to-right in both states.

---

## Batch 4b — F10: users, roles, permissions, JWT, guard decorator, audit writer

**Contents (PLAN.md §6)**: F10 — users, roles, permissions, JWT, guard decorator, audit writer.
Also covers F10's "Admin CRUD for branches, departments" (its own rule text) and the Generic CRUD
Pattern (`plan.md`) these two, plus roles, plus users, are the first users of.

- [X] T046 Create `backend/app/core/security.py` — JWT issue/verify (access 15 min / refresh 7 day), Argon2 password hashing via passlib (depends on T004)
- [X] T047 Complete `backend/app/api/deps.py` — `get_current_actor()` decodes a bearer JWT into a `CurrentActor` (permissions = union of `role_permissions` reachable via every matching `user_roles` row for the resolved branch/department) (depends on T046, T032)
- [X] T048 Create `backend/app/services/admin_crud_service.py` — generic `AdminCrudService[ModelT, CreateSchemaT, UpdateSchemaT]` exactly per `plan.md` §Generic CRUD Pattern (`list`/`get` wrapped with `require_permission(read_permission)`; `create`/`update`/`remove` wrapped with `require_permission(write_permission)` + `audited`) (depends on T031, T032, T033)
- [X] T049 [P] In `backend/app/services/admin_crud_service.py`, add `BranchCrudService` (`read_permission="branch.read"`), `DepartmentCrudService` (`read_permission="department.read"`), `RoleCrudService` (`read_permission="role.read"`) thin subclasses — each sets `repository_cls`, `entity_type`, `read_permission`; `write_permission` inherits `"admin.config"` unchanged (depends on T048)
- [X] T050 Create `backend/app/services/user_service.py` — `UserService(AdminCrudService[User, UserCreate, UserUpdate])`, `read_permission="user.read"`, overriding `create()` to Argon2-hash `password`→`password_hash` before delegating to `super().create()`; plus `grant_role(actor, user_id, role_id, branch_id, department_id) -> UserRole` (depends on T048, T046)
- [X] T051 Create `backend/app/services/auth_service.py` — `login`, `refresh`, `logout` exactly per `plan.md` §Service Classes (depends on T046, T050)
- [X] T052 [P] Create `backend/app/schemas/auth.py` — `LoginRequest`, `RefreshRequest`, `TokenPair` per `contracts/openapi.yaml` (depends on T005)
- [X] T053 [P] Create `backend/app/schemas/user.py` — `User`, `UserCreate`, `UserUpdate`, `UserRole`, `UserRoleCreate` per `contracts/openapi.yaml` (depends on T005)
- [X] T054 [P] Create `backend/app/schemas/role.py` — `Role`, `RoleCreate`, `RoleUpdate`, `Permission`, reference-data `Branch`/`Department` schemas per `contracts/openapi.yaml` (depends on T005)
- [X] T055 Create `backend/app/api/routers/auth.py` — `POST /auth/login`, `/auth/refresh`, `/auth/logout` (depends on T051, T052)
- [X] T056 Create `backend/app/api/routers/admin_config.py` — `/branches`, `/departments`, `/users` (+`/users/{id}/roles`), `/roles` (+`/roles/{id}/permissions`), `/permissions` routes, each handler validating input then calling exactly one `AdminCrudService`/`UserService`/`RoleCrudService` method and serializing the result — no business logic in this file (depends on T049, T050, T053, T054)
- [X] T057 Wire `admin_config.py` and `auth.py` into `backend/app/api/router.py` (depends on T055, T056)
- [X] T058 [P] Create `backend/tests/unit/test_permissions.py` — `require_permission` grants/denies correctly for a `CurrentActor` with/without the code (Testing Proportionality — permission checks) (depends on T032)
- [X] T059 [P] Create `backend/tests/unit/test_audit.py` — a mutating call through `AdminCrudService` produces exactly one `AuditLog` row with correct before/after; a forced failure inside the wrapped call (e.g. an artificial exception) leaves zero rows after rollback (Testing Proportionality; also this batch's own gate) (depends on T048)

**Gate (PLAN.md §6)**: `POST /auth/login` with a seeded (or manually created) admin user returns
a token pair; any subsequent admin mutation (e.g. `POST /branches`) produces exactly one
`audit_logs` row with populated `before`/`after`; running `T059`'s rollback test shows zero
`audit_logs` rows for the failed attempt.

---

## Batch 4c — F01: customers

**Contents (PLAN.md §6)**: F01 — customers, contact methods, notes, attachments, history.

- [X] T060 [P] Create `backend/app/schemas/customer.py` — `Customer`, `CustomerCreate`, `CustomerUpdate`, `CustomerHistory`, `ContactMethod`, `ContactMethodCreate`, `AttachmentUpload`, `Attachment` per `contracts/openapi.yaml` (depends on T005)
- [X] T061 Create `backend/app/services/customer_service.py` — `search`, `get`, `create` (rejects unless `contact_methods` has ≥1 item with exactly one `is_primary`), `update`, `deactivate`, `get_history` (merges `tickets`+`ticket_events`), `add_contact_method`, `add_attachment` exactly per `plan.md` §Service Classes (depends on T031, T032, T033, T013)
- [X] T062 Configure a `CustomerRepository` (`ScopedRepository[Customer]`, `scoping_mode=S1_FULL`) and `ContactMethodRepository` (`ScopedRepository[ContactMethod]`, `scoping_mode=S4_TRANSITIVE`, `parent_model=Customer`) as class-attribute config inside `customer_service.py` (no new repository file needed — no bespoke query beyond what `ScopedRepository` already provides) (depends on T031, T061)
- [X] T063 [P] Add trigram-similarity `search()` query (`pg_trgm` on `full_name_ar`/`full_name_en`/`organization_name`/`contact_methods.value`) to `CustomerRepository` in `customer_service.py` (FR-012) (depends on T062)
- [X] T064 Create `backend/app/api/routers/customers.py` — `/customers`, `/customers/{id}`, `/customers/{id}/deactivate`, `/customers/{id}/history`, `/customers/{id}/contact-methods`, `/customers/{id}/attachments`, per `contracts/openapi.yaml` — validate/delegate/serialize only (depends on T061)
- [X] T065 Wire `customers.py` into `backend/app/api/router.py` (depends on T064)
- [X] T066 [P] Create `frontend/app/[locale]/(agent)/customers/page.tsx` — list + search (depends on T043)
- [X] T067 [P] Create `frontend/app/[locale]/(agent)/customers/[id]/page.tsx` — detail, history, contact methods, attachment upload (depends on T043)

**Gate (PLAN.md §6)**: Creating a customer with an Arabic full name via `POST /customers`, then
`GET /customers?q=<3-character Arabic substring>`, returns that customer.

---

## Batch 4d — F02: categories, priorities, statuses, transitions, tickets, timeline, assignment

**Contents (PLAN.md §6)**: F02 — categories, priorities, statuses, transitions, tickets,
timeline, assignment.

- [X] T068 [P] In `backend/app/services/admin_crud_service.py`, add `CategoryCrudService`
      (`read_permission="category.read"`, `has_soft_delete=True`, matching `data-model.md` §0.4's
      per-table matrix), `PriorityCrudService` (`read_permission="priority.read"`),
      `TicketStatusCrudService` (`read_permission="ticket_status.read"`) thin subclasses (depends
      on T048)
- [X] T069 Create `backend/app/services/status_transition_service.py` (admin side) —
      `list` (`require_permission("status_transition.read")`) plus `create`/`update`/`delete`
      (no single-`get`, matching `contracts/openapi.yaml`) over `StatusTransition`, each requiring
      `"admin.config"`; `delete` is a hard `DELETE` (no `is_active` column) (depends on T048)
- [X] T069a [P] Create `backend/app/schemas/team.py` — `Team`, `TeamCreate`, `TeamUpdate`,
      `TeamMemberCreate` per `contracts/openapi.yaml` (depends on T005)
- [X] T069b In `backend/app/services/admin_crud_service.py`, add `TeamCrudService` thin subclass
      — sets `repository_cls` (`ScopedRepository[Team]`, `scoping_mode=S1_FULL`), `entity_type`,
      `read_permission="team.read"`, `has_soft_delete=False` (hard delete, matching
      `data-model.md` §0.4; `write_permission` inherits `"admin.config"` unchanged) — plus its one
      bespoke method:
      `add_member(actor, team_id, user_id) -> TeamMember`
      (`require_permission("admin.config")` + `audited("team_member", "create")`) — added after
      `/speckit-analyze` finding D1's follow-up: no task previously created this service or its
      `/teams` routes at all (depends on T048, T012)
- [X] T070 [P] Create `backend/app/schemas/ticket_taxonomy.py` — `Category`/`CategoryCreate`/
      `CategoryUpdate`, `Priority`/`PriorityCreate`/`PriorityUpdate`, `TicketStatus`/
      `TicketStatusCreate`/`TicketStatusUpdate`, `StatusTransition`/`StatusTransitionCreate`/
      `StatusTransitionUpdate` per `contracts/openapi.yaml` (depends on T005)
- [X] T071 [P] Create `backend/app/schemas/ticket.py` — `Ticket`, `TicketSummary`,
      `TicketCreate`, `TicketUpdate`, `TicketStatusChange`, `TicketAssign`,
      `SlaOverrideRequest`, `TicketTriageCorrection`, `TicketNoteCreate`, `TicketReplyCreate`,
      `TicketEvent`, `IllegalTransitionError` per `contracts/openapi.yaml` (depends on T005)
- [X] T072 Create `backend/app/repositories/ticket_repository.py` — `TicketRepository`
      (`ScopedRepository[Ticket]`, `scoping_mode=S1_FULL`) plus the five F04 dashboard-view query
      builders (`my_open`, `team_queue`, `unassigned` incl. `needs_triage` tickets,
      `breaching_soon` ordered by time-remaining ascending, `recently_closed`) and the shared
      filter set (status/priority/category/assignee/channel/date-range/free-text) — used by both
      this batch's `TicketService.list` and Batch 4e's dashboard (depends on T031, T018)
- [X] T073 Create `backend/app/services/ticket_service.py` — `list`, `get`, `create` (validates
      `category_id`/`priority_id` are each currently active and, if department-scoped, match the
      ticket's `department_id` — rejects with a localized 422 otherwise, FR-016; DB-sequence
      `reference_no` generation `TKT-{year}-{6-digit}`, resolves `sla_policy_id` via a stub
      `SlaService.resolve_policy` completed in Batch 4f, writes the `created` event, enqueues
      `categorization_job` without awaiting it), `update`, `assign`, `add_note`, `add_reply`
      (stamps `first_response_at` iff currently `NULL`), `add_attachment`, `correct_triage`
      (clears `needs_triage`, writes a `field_changed` event per FR-023c), `get_events` — exactly
      per `plan.md` §Service Classes (depends on T072, T032, T033)
- [X] T074 Create `backend/app/services/ticket_transition_service.py` — `change_status`: the only
      method in the codebase querying `status_transitions`; matches `(from_status_id,
      to_status_id)` at the ticket's department, falling back to the `department_id IS NULL`
      default row; raises `IllegalTransitionError(current_status_id, permitted_status_ids)` on no
      match; raises `PermissionDeniedError` when `required_permission` is set and absent; raises a
      validation error when `requires_reason` is true and `reason` is `None` (constitution
      Principle XI / PLAN.md C11) (depends on T073, T037)
- [X] T075 [P] Create `backend/tests/unit/test_ticket_transitions.py` — legal transition succeeds;
      illegal transition raises `IllegalTransitionError` naming current + permitted statuses;
      `requires_reason=true` without a reason is rejected; a transition whose
      `required_permission` the actor lacks is rejected (Testing Proportionality — status
      transition legality) (depends on T074)
- [X] T076 Create `backend/app/api/routers/admin_config.py` additions — `/categories`,
      `/priorities`, `/ticket-statuses`, `/status-transitions` routes (extends the file from
      Batch 4b) (depends on T068, T069, T070)
- [X] T076a [P] Create `backend/app/api/routers/admin_config.py` additions — `/teams`
      (list/create/get/update/delete) and `/teams/{id}/members` (add member) routes, calling
      `TeamCrudService`'s inherited CRUD methods and its bespoke `add_member` — validate/delegate/
      serialize only (depends on T069a, T069b)
- [X] T077 Create `backend/app/api/routers/tickets.py` — every `/tickets*` path in
      `contracts/openapi.yaml` except `/tickets/{id}/sla-override` (Batch 4f) and the
      `/tickets/{id}/ai/*` paths (Batch 4h) — validate/delegate/serialize only (depends on T073,
      T074, T071)
- [X] T078 Wire the Batch 4d router additions into `backend/app/api/router.py` (depends on T076,
      T076a, T077)
- [X] T079 [P] Create `frontend/app/[locale]/(agent)/tickets/[id]/page.tsx` — ticket detail,
      status-change control (surfacing the localized illegal-transition error), assignment,
      timeline, notes/replies, attachments, inline customer context (FR-028) (depends on T043,
      T067)

**Gate (PLAN.md §6)**: Driving a ticket through a legal path from `new` to `closed` succeeds
end-to-end via the API; attempting an illegal transition (e.g. `new` → `resolved` directly)
returns HTTP 422 naming the current status and the permitted targets, localized to the caller's
locale.

---

## Batch 4e — F04 + F12: dashboard, queues, filters, quick replies, Arabic UI shell

**Contents (PLAN.md §6)**: F04 + F12 — dashboard, queues, filters, quick replies, Arabic UI
shell.

- [X] T080 [P] In `backend/app/services/admin_crud_service.py`, add `QuickReplyCrudService`
      thin subclass (`read_permission="quick_reply.read"`, `has_soft_delete=False` — hard
      delete, `data-model.md` §0.4) (depends on T048)
- [X] T081 [P] Create `backend/app/schemas/quick_reply.py` — `QuickReply`, `QuickReplyCreate`,
      `QuickReplyUpdate` per `contracts/openapi.yaml` (depends on T005)
- [X] T082 Add placeholder-substitution logic (`{{customer_name}}`, `{{reference_no}}`,
      `{{agent_name}}`) to `backend/app/services/customer_service.py`'s sibling — create
      `backend/app/services/quick_reply_render.py` with one pure function
      `render(quick_reply: QuickReply, ticket: Ticket) -> str`, called from the frontend's reply
      composer via a small `GET /quick-replies?category_id=` + client-side substitution, OR from
      a dedicated endpoint — this task creates the pure function only; wiring is T086 below
      (depends on T081)
- [X] T083 Add `/quick-replies` routes to `backend/app/api/routers/admin_config.py` (depends on
      T080, T081)
- [X] T084 Wire the Batch 4e router addition into `backend/app/api/router.py` (depends on T083)
      — already satisfied: `admin_config.router` was wired into `api_router` in Batch 4b (T057);
      the new `/quick-replies` routes live in that same file/router, so no further change to
      `router.py` itself was needed.
- [X] T085 [P] Create `frontend/app/[locale]/(agent)/dashboard/page.tsx` (replacing Batch 4a's
      placeholder) — the five views (My open tickets / My team's queue / Unassigned / Breaching
      soon / Recently closed) via `GET /tickets?view=`, plus the shared filter set with
      URL-encoded, shareable filter state (FR-027) (depends on T072, T043)
- [X] T086 In `frontend/app/[locale]/(agent)/tickets/[id]/page.tsx`, add the quick-reply picker
      (matching the ticket's `source_locale`, placeholders filled via T082's logic exposed
      through the reply composer) and visually distinguish internal notes from customer-facing
      replies (FR-030) (depends on T079, T082)
- [X] T087 [P] Verify (no new component expected) that every color/spacing/margin utility
      introduced across `frontend/app/` and `frontend/components/` so far uses Tailwind logical
      properties only — run `grep -rE "\b(ml|mr|pl|pr|left|right)-" frontend/` and fix any hit
      found outside an `rtl-exempt:`-commented, `<LtrText>`-wrapped line (constitution Principle
      III / PLAN.md C3) (depends on T085, T086) — zero hits in `frontend/app/` and
      `frontend/components/`.

**Gate (PLAN.md §6)**: Switching the UI language to Arabic flips the entire dashboard to RTL with
no layout breakage and no page reload; the "Breaching soon" view returns tickets ordered by time
remaining ascending; an internal note is never present in any response the customer portal would
receive (verified once Batch 4i's portal exists — cross-checked again there).

**Gate verification (this run)**: `tsc --noEmit`, `npm run build`, `pytest backend/tests` (18/18),
`scripts/check-i18n-literals.sh`, and the T087 grep all pass clean. Additionally driven live —
`docker compose` stack already running (postgres/redis/minio/backend/arq-worker/frontend),
logged in as the existing `admin@example.com` test user, headless-Chromium (Playwright) against
`http://localhost:3000` — confirming: `<html dir>` flips `ltr`↔`rtl` on locale switch with a
single navigation entry (no full reload); dashboard views/filters render correctly mirrored in
both directions at 1280×950; the quick-reply picker (T086) renders, filters to the ticket's
category, and its substituted body matches `quick_reply_render.py`'s `render()` output
byte-for-byte; internal vs. customer-visible timeline entries are visibly distinguished (amber vs.
sky); zero browser console errors on either locale. `GET /tickets?view=breaching_soon` returns
`200 []` — correctly empty, since no `sla_policies` exist yet (Batch 4f).

Four defects were found and fixed during this live verification, all necessary for "the entire
agent interface usable" but outside T080–T087's own file list, so recorded separately from the
task checklist above:
1. **No CORS middleware** (`backend/app/main.py`, since Batch 4a/T039) — every browser fetch from
   the frontend's origin to the API was silently blocked, so no page could ever load real data.
   Added `CORSMiddleware` gated by a new `CORS_ORIGINS` setting (`app/config.py`,
   `.env.example`), default `http://localhost:3000`.
2. **`Ticket` response schema missing `customer`** (`backend/app/schemas/ticket.py`, since Batch
   4d/T071) — `contracts/openapi.yaml`'s `Ticket.customer` was never declared on the Pydantic
   model, so `TicketService.get()`'s FR-028 customer-attach was silently dropped by response
   serialization; broke both T079's existing "inline customer context" section and this batch's
   `{{customer_name}}` quick-reply substitution. Added the missing field.
3. **`LocaleSwitcher` dropped the query string** (`frontend/components/locale-switcher.tsx`, since
   Batch 4a/T045) — switching language reset this batch's URL-encoded filter/view state (FR-027).
   Now preserves `useSearchParams()` across the locale-prefixed path swap.
4. **Mixed-locale content inherited the page's `dir` instead of its own** — an English-locale
   ticket's subject/description, this batch's composer textarea and quick-reply-filled body, and
   timeline event bodies/reasons visually reordered (leading punctuation) inside an Arabic-`dir`
   page. Added `dir="auto"` (browser-native per-content-block direction inference) to each; no
   Tailwind utility involved, so this doesn't touch T087's physical-vs-logical-properties check.

**Post-gate fixes (user browser test, this run, still Batch 4e — no 4f work)**: two more defects
surfaced testing the gate build directly, both frontend-only:
5. **A 401 rendered as a generic error instead of redirecting to login** — every page's
   `{queryX.isError && <p role="alert">{t("error")}</p>}` treated an expired/missing token
   identically to any other failure. `frontend/lib/api-client.ts`'s `request()` now intercepts
   `401` before it ever becomes an `ApiError`: clears the stored token and hard-navigates to
   `/{locale}/login?next=<original path+query>`, returning a never-resolving promise so the
   caller's query/mutation never reaches an error-render state. `POST /auth/login` itself opts out
   via a new `skipAuthRedirect` flag (its own 401 — wrong password — must stay inline on the login
   form, not bounce back to itself).
6. **No login page existed** — confirmed via `find`/`grep`, nothing under `frontend/app/` served
   one, so there was no way back in once a token expired or on a fresh visit. Added
   `frontend/app/[locale]/login/page.tsx`: email/password form calling the new `api.login()`,
   bilingual inline error on failure (reusing the `ApiError.messageAr`/`messageEn` pattern already
   used elsewhere), `setAccessToken()` + redirect to `next` (restricted to a same-locale relative
   path — not an open redirect) or `/{locale}/dashboard` on success. New `Login` message namespace
   in both `messages/ar.json` and `messages/en.json`.

Verified live end-to-end (same running `docker compose` stack): an unauthenticated visit to the
ticket-detail page and to the dashboard (with an active `?view=` filter) both land on the correctly
localized, correctly-RTL/LTR `/login` page with `next` preserved; a wrong password shows the
bilingual "Invalid credentials" error inline with no redirect loop; correct credentials sign in and
land back on the originally-requested page. `tsc --noEmit`, `npm run build` (now also emitting
`/ar/login` and `/en/login`), and `check-i18n-literals.sh` all still pass; backend untouched, 18/18
backend unit tests still pass.

---

## Batch 4f — F05: SLA policies, pause accounting, breach derivation, sweep job, round-robin

**Contents (PLAN.md §6)**: F05 — SLA policies, pause accounting, breach derivation, sweep job,
round-robin.

- [ ] T088 [P] In `backend/app/services/admin_crud_service.py`, add `SlaPolicyCrudService` thin
      subclass (`read_permission="sla_policy.read"`, `has_soft_delete=False`) (depends on T048)
- [ ] T089 [P] Create `backend/app/schemas/sla_policy.py` — `SlaPolicy`, `SlaPolicyCreate`,
      `SlaPolicyUpdate` per `contracts/openapi.yaml` (depends on T005)
- [ ] T090 Create `backend/app/services/sla_service.py` — `compute_due_dates` (pure function:
      `created_at` + policy + `sla_paused_ms` + business-hours/timezone when
      `business_hours_only`), `compute_breach_state` (pure function: on_track/at_risk <25%
      remaining/breached), `resolve_policy` (exact category+priority → priority-only →
      category-only → default), `override_policy` (existing policies only, reason required,
      recomputes from original `created_at`, permits an immediately-breaching result) — exactly
      per `plan.md` §Service Classes (depends on T018, T031)
- [ ] T091 Complete `backend/app/services/ticket_service.py`'s `create()` to call
      `SlaService.resolve_policy` for real (removing Batch 4d's stub) (depends on T090, T073)
- [ ] T092 Create `backend/app/services/assignment_service.py` — `auto_assign_ticket`:
      round-robin over active `ticket.own`-holding, non-unavailable agents in the ticket's
      department; returns `None` if none eligible (depends on T018, T031)
- [ ] T093 Add `sweep_breaches` to `backend/app/services/sla_service.py` — for every open ticket
      whose computed state is `breached` with no existing `sla_breached` event for its current
      target: write one, raise priority one severity level, reassign to the department's lead;
      idempotent by construction (checks for an existing event first) (depends on T090, T019)
- [ ] T094 Create `backend/app/jobs/worker.py` — ARQ `WorkerSettings` registering the jobs below
      (depends on T005)
- [ ] T095 [P] Create `backend/app/jobs/sla_sweep_job.py` — runs `SlaService.sweep_breaches()`
      every 5 minutes (depends on T093, T094)
- [ ] T096 [P] Create `backend/app/jobs/categorization_job.py` — stub that calls
      `AssignmentService.auto_assign_ticket` after categorization; the categorization call itself
      is completed in Batch 4h — for this batch, the job body calls
      `AssignmentService.auto_assign_ticket(ticket_id)` directly (depends on T092, T094)
- [ ] T097 Add `POST /tickets/{id}/sla-override` to `backend/app/api/routers/tickets.py` (depends
      on T090, T077)
- [ ] T098 Add `/sla-policies` routes to `backend/app/api/routers/admin_config.py` (depends on
      T088, T089)
- [ ] T099 Wire the Batch 4f router additions into `backend/app/api/router.py` (depends on T097,
      T098)
- [ ] T100 [P] Create `backend/tests/unit/test_sla_service.py` — pause accounting shifts the
      deadline by exactly the paused duration; business-hours policies don't accrue outside the
      branch's hours/timezone; `sweep_breaches()` run twice writes exactly one `sla_breached`
      event per ticket/target; an SLA override with an already-past recomputed deadline is
      permitted and produces a breach (Testing Proportionality — SLA computation) (depends on
      T090, T093)

**Gate (PLAN.md §6)**: A ticket parked in a pause-accounting status for a fixed period shows a
resolution deadline shifted out by exactly that period; restarting the entire stack
(`docker compose restart`) and re-querying shows identical breach states for every ticket — no
state held only in memory; running the breach sweep twice in a row produces zero additional
`sla_breached` events on the second run.

---

## Batch 4g — F06: articles, chunking, embeddings, hybrid search

**Contents (PLAN.md §6)**: F06 — articles, chunking, embeddings, hybrid search.

**Pre-batch checkpoint (`docs/architecture/stack.md`)**: confirm the development machine's
available RAM and fix the embedding model (`BAAI/bge-m3` int8, 1024-dim, ≥16 GB, or
`intfloat/multilingual-e5-small`, 384-dim, <16 GB) *before* T103 — `kb_article_chunks.embedding`'s
dimension (already `vector(1024)` in Batch 4a's migration per `data-model.md`) is not casually
changed once populated.

- [ ] T101 [P] Create `backend/app/schemas/kb_article.py` — `KbArticle`, `KbArticleCreate`,
      `KbArticleUpdate`, `KbSearchResult` per `contracts/openapi.yaml` (depends on T005)
- [ ] T102 Create `backend/app/repositories/kb_repository.py` — `KbArticleRepository`
      (`ScopedRepository[KbArticle]`, `scoping_mode=S2_BRANCH_DEPT_OPTIONAL`) plus the hybrid
      search query builder (`pg_trgm` lexical + `pgvector` cosine, reciprocal-rank-fused) (depends
      on T031, T023)
- [ ] T103 Create `backend/app/services/kb_service.py` — `create_article`, `update_article`
      (chunks ~500 tokens/50 overlap per locale, embeds via the fixed model from the pre-batch
      checkpoint, writes `kb_article_chunks`), `publish_article` (422 unless all four
      title/body fields non-empty, FR-041), `search` (calls the hybrid query, reranks with
      `bge-reranker-v2-m3` behind a feature flag, else returns fused order — FR-043) — exactly per
      `plan.md` §Service Classes (depends on T102)
- [ ] T104 Create `backend/app/api/routers/kb.py` — `/kb/articles*`, `/kb/search` per
      `contracts/openapi.yaml` (depends on T103)
- [ ] T105 Wire `kb.py` into `backend/app/api/router.py` (depends on T104)
- [ ] T106 [P] Create `frontend/app/[locale]/(agent)/kb/page.tsx` — article list, editor
      (bilingual title/body fields, publish action), search box (depends on T043)

**Gate (PLAN.md §6)**: An Arabic-language query and an English-language query for the same
underlying concept both return the same seeded bilingual article, ranked above unrelated ones.

---

## Batch 4h — F07: four AI capabilities, four fallbacks, AI observability

**Contents (PLAN.md §6)**: F07 — LiteLLM wrapper (already built, Batch 4a), four capabilities,
four fallbacks, Langfuse → per `docs/architecture/stack.md` rev 2, this is the already-built
`llm_calls` table (Batch 4a), not Langfuse; no task here re-adds infrastructure Batch 4a already
provides.

- [ ] T107 [P] Create `backend/app/schemas/ai.py` — `AiSummaryResponse`,
      `AiSuggestedReplyResponse`, `CategorizationDecision`, `BenchmarkResult` per
      `contracts/openapi.yaml` (depends on T005)
- [ ] T108 Create `backend/app/ai/categorization.py` — prompt template + `AiService.categorize`
      body: calls `LiteLlmWrapper.complete(LlmCapability.CATEGORIZE, ...)`, writes
      `ai_suggested_category_id`/`ai_category_confidence` directly (never `category_id`); on
      `fallback_used`, leaves both `NULL` (depends on T035, T018)
- [ ] T109 [P] Create `backend/app/ai/summary.py` — prompt template + `AiService.summarize` body;
      fallback: first 300 characters of `description` (depends on T035)
- [ ] T110 [P] Create `backend/app/ai/suggested_reply.py` — prompt template +
      `AiService.suggest_reply` body; fallback: empty draft; output locale always matches
      `tickets.source_locale` (depends on T035)
- [ ] T111 Create `backend/app/services/ai_service.py` — `summarize`, `suggest_reply`,
      `suggest_solution` (top 3 from `KbService.search()` over subject+description; fallback:
      empty list), `categorize`, `apply_categorization_decision` (writes real `category_id` +
      `ai_suggestion_applied` event with suggestion+confidence, FR-044),
      `run_categorization_benchmark` — exactly per `plan.md` §Service Classes (depends on T108,
      T109, T110, T103)
- [ ] T112 Complete `backend/app/jobs/categorization_job.py` — now calls
      `AiService.categorize(ticket_id)` before `AssignmentService.auto_assign_ticket` (replaces
      Batch 4f's stub body) (depends on T111, T096)
- [ ] T113 Create `backend/tests/golden/bilingual_tickets.json` — 20 tickets (mixed Arabic/
      English) with known-correct category labels, per PLAN.md §5 F07 acceptance #6 / FR-050
      (depends on T111)
- [ ] T114 Create `backend/app/api/routers/ai.py` — `/tickets/{id}/ai/summary`,
      `/suggested-reply`, `/suggested-solution`, `/categorization-suggestion`,
      `/ai/categorization-benchmark` per `contracts/openapi.yaml` (depends on T111, T113)
- [ ] T115 Wire `ai.py` into `backend/app/api/router.py` (depends on T114)
- [ ] T116 [P] In `frontend/app/[locale]/(agent)/tickets/[id]/page.tsx`, add the AI summary
      panel, suggested-reply-into-composer action, suggested-solution panel (not rendered on an
      empty fallback list), and the categorization-suggestion accept/override control (depends on
      T079, T114)

**Gate (PLAN.md §6)**: With the configured LLM endpoint stopped (or the host disconnected from
the network), every screen remains fully usable, no error dialogs appear, and all four AI-assisted
capabilities visibly engage their documented fallback.

---

## Batch 4i — F03 + F08 + F09 + F11: email adapter, portal, reports, API keys, seed data

**Contents (PLAN.md §6)**: F03 + F08 + F09 + F11 — webhook, email adapter, portal, reports, API
keys, seed data.

- [ ] T117 [P] Create `backend/app/channels/email_adapter.py` — functional `EmailAdapter`
      (`ChannelAdapter`), IMAP poll via `httpx`/`imaplib`, implements `normalize()`/`send_reply()`
      (depends on T034)
- [ ] T118 [P] Create `backend/app/channels/whatsapp_adapter.py`,
      `backend/app/channels/sms_adapter.py`, `backend/app/channels/chat_adapter.py` — each
      declares its `channel` and both `ChannelAdapter` methods, each raising
      `NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")` — present and
      importable, never absent (PLAN.md F03) (depends on T034)
- [ ] T119 [P] Create `backend/app/schemas/channel.py` — `NormalizedMessagePayload`,
      `InboundMessageAccepted`, `ApiKey`, `ApiKeyCreate`, `ApiKeyCreated` per
      `contracts/openapi.yaml` (depends on T005)
- [ ] T120 [P] Create `backend/app/schemas/portal.py` — `PortalTicketSubmit`,
      `PortalTicketReceipt`, `PortalTicketView` per `contracts/openapi.yaml` (depends on T005)
- [ ] T121 [P] Create `backend/app/schemas/report.py` — `TicketsByStatusReport`,
      `SlaComplianceReport`, `AgentVolumeReport` per `contracts/openapi.yaml` (depends on T005)
- [ ] T122 Create `backend/app/services/channel_service.py` — `register_adapter`, `ingest`
      (persists raw payload to `inbound_messages` first; resolves branch/department via a quoted
      ticket reference override (FR-023b) or `channel_configs` match with system-default +
      `needs_triage` fallback (FR-023a); constructs a **fresh `TenantScope` from the resolved
      branch/department, never the caller's own scope** (constitution/plan.md self-audit finding —
      see `plan.md` §Post-Design Constitution Check); matches/creates the customer within that
      scope only; threads by `external_id`/`reference_no`), `poll_email` — exactly per `plan.md`
      §Service Classes (depends on T117, T118, T031, T073)
- [ ] T123 Create `backend/app/jobs/email_poll_job.py` — runs `ChannelService.poll_email()`
      periodically (depends on T122, T094)
- [ ] T124 Create `backend/app/services/portal_service.py` — `submit_ticket` (branch from
      `category_id`'s own branch; department from the category's department, else system-default
      + `needs_triage`, reusing the exact same fallback `ChannelService` uses), `track_ticket`
      (returns `None` on any mismatch — unknown reference OR wrong contact — identically, FR-053),
      `get_history` (filters out `visibility="internal"`, FR-054) — exactly per `plan.md` §Service
      Classes (depends on T073, T031)
- [ ] T125 Create `backend/app/services/report_service.py` — `tickets_by_status`,
      `sla_compliance`, `agent_volume`; each raises `PermissionDeniedError("report.cross_branch")`
      if `cross_branch=True` is requested without that permission (FR-060) — exactly per
      `plan.md` §Service Classes (depends on T031, T090)
- [ ] T126 Create `backend/app/services/api_key_service.py` — `issue` (random secret, only the
      Argon2 hash persisted), `revoke`, `authenticate` (used by API-key auth) — exactly per
      `plan.md` §Service Classes (depends on T031, T046)
- [ ] T127 Complete `backend/app/api/deps.py`'s `get_current_actor()` to also accept `X-API-Key`
      via `ApiKeyService.authenticate`, building a `CurrentActor` whose `scope` is
      `TenantScope(branch_id=api_keys.branch_id, department_id=None)` (depends on T126, T047)
- [ ] T128 Create `backend/app/api/routers/channels.py` — `POST /channels/inbound` (API-key auth
      only) (depends on T122, T119, T127)
- [ ] T129 Create `backend/app/api/routers/portal.py` — every `/portal/*` path, unauthenticated
      (`security: []`) per `contracts/openapi.yaml` (depends on T124, T120)
- [ ] T130 Create `backend/app/api/routers/reports.py` — `/reports/*` per
      `contracts/openapi.yaml` (depends on T125, T121)
- [ ] T131 Create `backend/app/api/routers/api_keys.py` — `/api-keys*` per
      `contracts/openapi.yaml` (depends on T126, T119)
- [ ] T132 Wire the Batch 4i routers into `backend/app/api/router.py`; confirm
      `GET /docs`/`GET /openapi.json` now covers every Tier M/S path in
      `contracts/openapi.yaml` (depends on T128, T129, T130, T131)
- [ ] T133 [P] Create `frontend/app/[locale]/(portal)/submit/page.tsx`,
      `frontend/app/[locale]/(portal)/track/page.tsx`,
      `frontend/app/[locale]/(portal)/kb/page.tsx` — unauthenticated portal pages (depends on
      T129)
- [ ] T134 [P] Create `frontend/app/[locale]/(agent)/reports/page.tsx` — the three aggregates +
      dashboard page, cross-branch toggle gated client-side (server still enforces it, T125)
      (depends on T130)
- [ ] T135 [P] Create `frontend/app/[locale]/(agent)/admin/` API-key management screen (issue,
      list, revoke) (depends on T131)
- [ ] T136 Create `backend/app/seed/seed.py` — idempotent seed matching PLAN.md §7 exactly: 2
      branches (different timezones/business hours), 3 departments, 5 users covering all four
      roles, 20 bilingual customers, 40 tickets spread across every status/priority/channel (some
      pre-breaching), 10 fully bilingual KB articles, a 3-level category tree, 4 priorities, 7
      statuses with the full `status_transitions` table from `data-model.md` §4, 3 SLA policies,
      8 quick replies, 2 `channel_configs` rows (one per department), and the full seeded
      permission set from `data-model.md` §5, with every role→permission grant assigned exactly
      per `data-model.md` §5.1's table (not left to guesswork) — `admin.config`/`audit.read`/
      `report.cross_branch`/`customer.delete` to `admin` only; `ticket.sla_override`/
      `ticket.reopen`/`ticket.assign` to `lead`+`admin`; `ticket.read`/`ticket.create`/
      `ticket.close`/`ticket.own`/`customer.read`/`customer.create` and all eleven
      `{entity}.read` codes (`branch.read`, `department.read`, `user.read`, `role.read`,
      `category.read`, `priority.read`, `ticket_status.read`, `status_transition.read`,
      `sla_policy.read`, `quick_reply.read`, `team.read`) to `agent`+`lead`+`admin`
      (`/speckit-analyze` findings D1 and E1). This task's seed
      script writes rows through every model created in Batch 4a and touches functionality from
      every batch since (customers, tickets, KB articles, SLA policies, channel configs), so it
      depends on T030 (full schema) and, transitively, on every batch's models being complete —
      in practice this is the last task started, after Batch 4h's T116 (depends on T030, T136 is
      scheduled last in this batch)
- [ ] T137 Run `docker compose exec backend python -m app.seed.seed` twice in succession and
      diff row counts — must be identical, confirming idempotency (depends on T136)

**Gate (PLAN.md §6)**: The full demo path works end-to-end on freshly seeded data — an inbound
email creates a ticket, a portal submission creates a separately-tracked ticket, reports reflect
seeded volume correctly scoped by branch/department, and an API key scoped to `ticket.read` can
list tickets via `GET /tickets` but is refused on `POST /tickets`.

---

## Dependencies & Execution Order

- **Batch 4a is the foundation for everything.** No task in any other batch can start before
  every T001–T045 task (models, migration, all five shared abstractions, RTL/i18n scaffold) is
  done — this is the explicit instruction for this run, not just a template convention.
- **Batches 4b → 4i run in strict sequence**, matching PLAN.md §6 exactly: each batch's services
  depend on `AdminCrudService` (built in 4b) and/or entities/services built in an earlier batch
  (e.g. 4f's `SlaService.resolve_policy` completes a stub 4d left in `TicketService.create`; 4h's
  `AiService.categorize` completes a stub 4f left in `categorization_job.py`). PLAN.md §6's own
  "commit and `/clear` between every batch" instruction is the reason no batch's tasks are
  interleaved with another's above.
- **Within a batch**, tasks not marked `[P]` depend on the nearest preceding non-`[P]` task in
  that batch unless another dependency is stated inline; `[P]` tasks may run concurrently with
  each other once their own stated dependencies are satisfied.

## Parallel Execution Examples

**Batch 4a**, once T006 (`base.py`) is done, all 22 model files (T007–T028) can be authored
concurrently:

```text
Task: "Create backend/app/models/branch.py — Branch (S6)"
Task: "Create backend/app/models/department.py — Department (S3)"
Task: "Create backend/app/models/user.py — User (S2)"
... (all 22 model tasks)
```

Once models are done, the five shared abstractions (T031–T035) are independent of each other and
can run concurrently:

```text
Task: "Create backend/app/repositories/scoped_repository.py — ScopedRepository"
Task: "Create backend/app/core/permissions.py — require_permission"
Task: "Create backend/app/core/audit.py — audited"
Task: "Create backend/app/channels/base.py — ChannelAdapter"
Task: "Create backend/app/ai/litellm_wrapper.py — LiteLlmWrapper"
```

**Batch 4i**, the three channel adapter files (T118) and the three schema files (T119–T121) are
each independently parallel once their shared dependency (T034/T005) is met.

## Implementation Strategy

### Sequential batches, not incremental user-story delivery

This sprint's delivery unit is the **batch**, not the user story — PLAN.md §6 and the
constitution's Development Workflow section both specify commit + `/clear` after each batch's
gate passes, in order 4a → 4i. There is no supported "do 4c before 4b" path: 4b's guard
decorator and audit writer are load-bearing for every subsequent batch's `@require_permission`/
`@audited` usage.

### MVP checkpoint

If time runs out mid-sprint, the latest **fully-gated** batch is the demo-ready state — per
PLAN.md §6's gates, Batch 4d (full ticket journey, illegal-transition rejection) is the earliest
point at which PLAN.md §1.2's "journey that defines success" is demonstrable end-to-end, even
without AI, KB, SLA automation, or channels/portal/reports layered on top yet.

### What's deliberately absent

No task exists for: personal tasks/reminders, breach-notification delivery, a conversational
chatbot, full portal accounts, CSAT submission/reporting, live chat, scheduled/exported reports,
audit-trail browsing UI, ERP connectors, outbound webhooks/retry infrastructure, or custom
branding — all Tier D (PLAN.md §3), specified in `spec.md` with acceptance criteria and
schema-accommodated in `data-model.md`/`research.md` Part 3, generating zero tasks here per
constitution Principle XIII.

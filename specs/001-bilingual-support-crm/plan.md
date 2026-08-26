# Implementation Plan: Bilingual Support CRM — Core Product

**Branch**: `001-bilingual-support-crm` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-bilingual-support-crm/spec.md`, `PLAN.md`,
`docs/architecture/stack.md`, `.specify/memory/constitution.md`.

## Summary

Build the Tier M/S surface of PLAN.md's twelve feature areas as one FastAPI backend (Python
3.12, SQLAlchemy async, PostgreSQL 16) and one Next.js 15 frontend, on Docker Compose. Every
constitutional guarantee (bilingual, RTL, tenant scoping, immutable audit/timeline, AI gateway
abstraction, deterministic AI fallback, service-layer permissions, data-driven workflow, stateless
SLA) is carried by five shared abstractions (§Shared Abstractions) that every other module is
built on top of — not re-implemented per feature. Tier D capabilities are schema-accommodated only
(`data-model.md`, `research.md` Part 3) and generate no tasks (Principle XIII).

## Technical Context

| | |
|---|---|
| **Language/Version** | Python 3.12 (backend), TypeScript 5.6 (frontend) |
| **Primary Dependencies** | FastAPI 0.115, SQLAlchemy 2.0 (async), Alembic 1.14, Pydantic 2.9, Uvicorn 0.32, ARQ 0.26, httpx 0.27, LiteLLM · Next.js 15 (App Router), Tailwind 3.4, shadcn/ui, next-intl 3, TanStack Query 5, react-hook-form + zod |
| **Storage** | PostgreSQL 16 (+ `pgvector` 0.7, `pg_trgm`), Redis 7 (ARQ broker), MinIO (S3 API) |
| **Testing** | pytest (branching business logic only — status transitions, permission checks, SLA computation, tenant scoping; Principle XIV) · bilingual golden set of 20 tickets, scored by script, for AI features · Schemathesis against `contracts/openapi.yaml`, time-permitting |
| **Target Platform** | Docker Compose, single host (laptop dev now, on-prem server later — identical architecture, `docs/architecture/stack.md`) |
| **Project Type** | Web application (backend + frontend) |
| **Performance Goals** | Not independently set by this plan — PLAN.md and `spec.md` define no throughput target; the only stated latency constraint is FR-049 (AI never blocks ticket creation) and F06's 200–400 ms/query embedding search |
| **Constraints** | No external network dependency at runtime except the configured LLM endpoint (PLAN.md); every AI feature must degrade cleanly offline (FR-009) |
| **Scale/Scope** | Sprint seed data only (PLAN.md §7): 2 branches, 3 departments, 5 users, 20 customers, 40 tickets, 10 KB articles — this plan does not size for production load |

No `NEEDS CLARIFICATION` remains — `docs/architecture/stack.md` fully specifies the stack, and
`spec.md`'s three clarifications (channel routing, SLA override bounds, cross-branch permission)
were already resolved before this plan was written.

## Constitution Check

*GATE: checked before Phase 0 research below, and re-checked after Phase 1 design in
§Post-Design Constitution Check & Self-Audit at the end of this document.*

| Principle | How this plan satisfies it |
|---|---|
| I. Bilingual String Externalization | `messages/ar.json`/`messages/en.json` (next-intl) on the frontend; every API error uses `ErrorResponse{message_ar, message_en}` (`contracts/openapi.yaml`) — no literal user-facing string in either codebase |
| II. Reference-Data Bilingual Completeness | `data-model.md` §0.4 — `label_ar`/`label_en` `NOT NULL` on every reference-data table |
| III. Structural RTL/LTR Parity | Tailwind logical properties only (`docs/architecture/stack.md`); `<LtrText>` component for reference numbers/emails/phones/URLs, per the constitution's `rtl-exempt:` exception mechanism |
| IV. Universal Tenant Attribution | `data-model.md` §2 — every table has exactly one of the six patterns, exhaustively |
| V. Repository-Layer Tenant Scoping | `ScopedRepository` (§Shared Abstractions #1) is the *only* place any scope filter is written |
| VI. Immutable Event & Audit Trails | `alembic/versions/0001_initial.py` revokes `UPDATE`/`DELETE` grants on the four insert-only tables (`data-model.md` §0.3) at the DB role level, backed by a trigger |
| VII. Atomic Audit Writes | `audited` decorator (§Shared Abstractions #3) writes inside the same session/transaction as the mutation it wraps |
| VIII. Single AI Gateway | `LiteLlmWrapper` (§Shared Abstractions #5) is the only module importing an LLM HTTP client; `app/ai/*` and `app/channels/*` never import a vendor SDK — enforced by an import-lint rule (`app/core/lint_no_vendor_sdk.py`, run in `pyproject.toml`'s lint step) |
| IX. Deterministic AI Degradation | Every `AiService` method catches `LiteLlmWrapper`'s own internal failure (it never raises — see #5) and returns the documented fallback; `contracts/openapi.yaml`'s `fallback_used` field on every AI response makes this observable |
| X. Service-Layer Permission Enforcement | `require_permission` (§Shared Abstractions #2) wraps *service* methods, never route handlers — route handlers cannot bypass it by construction |
| XI. Data-Driven Status Transitions | `TicketTransitionService.change_status` (§Service Classes) issues exactly one query against `status_transitions`; no status code appears in an `if`/`match` anywhere in the plan |
| XII. Stateless SLA Derivation | `SlaService.compute_due_dates`/`compute_breach_state` are pure functions over stored fields — `data-model.md` has no SLA-state column to hold state in |
| XIII. Scope Discipline | `research.md` Part 3; Tier D items get zero entries in the file tree below and zero service methods |
| XIV. Testing Proportionality | `tests/unit/` targets exactly the branching logic named in Technical Context's Testing row; `tests/golden/` for AI; no test scaffolding for generic CRUD |

No violations — **Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/001-bilingual-support-crm/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── openapi.yaml      # Phase 1 output — all Tier M/S endpoints
└── tasks.md               # Phase 2 output (/speckit.tasks — not created by this command)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   ├── env.py                          # Alembic runtime config (async engine)
│   └── versions/
│       └── 0001_initial.py             # Full schema from data-model.md, incl. DB-role grant revocation for the four insert-only tables (C6)
├── app/
│   ├── main.py                         # FastAPI app factory; mounts app.api.router; structlog + correlation-id middleware
│   ├── config.py                       # Pydantic Settings: DB/Redis/MinIO URLs, LITELLM_*, JWT secrets, SYSTEM_DEFAULT_BRANCH_ID/DEPARTMENT_ID
│   ├── db.py                           # Async engine/session factory; get_session() dependency (one transaction per request)
│   ├── models/                         # SQLAlchemy 2.0 ORM models — one file per data-model.md entity, no business logic
│   │   ├── base.py                     # Base, id/created_at/created_by mixin (§0.1), updated_at/updated_by mixin (§0.2)
│   │   ├── branch.py
│   │   ├── department.py
│   │   ├── user.py
│   │   ├── role.py                     # Role, Permission, RolePermission
│   │   ├── user_role.py
│   │   ├── team.py                     # Team, TeamMember
│   │   ├── customer.py                 # Customer, ContactMethod
│   │   ├── category.py
│   │   ├── priority.py
│   │   ├── ticket_status.py
│   │   ├── status_transition.py
│   │   ├── ticket.py
│   │   ├── ticket_event.py
│   │   ├── attachment.py
│   │   ├── sla_policy.py
│   │   ├── quick_reply.py
│   │   ├── kb_article.py               # KbArticle, KbArticleChunk
│   │   ├── api_key.py
│   │   ├── audit_log.py
│   │   ├── inbound_message.py
│   │   ├── channel_config.py
│   │   └── llm_call.py
│   ├── schemas/                        # Pydantic request/response models — mirrors contracts/openapi.yaml 1:1, one file per models/ file
│   ├── repositories/
│   │   ├── scoped_repository.py        # TenantScope, ScopingMode, ScopedRepository — Shared Abstraction #1
│   │   └── (no other files — every entity repository is `ScopedRepository[Model]` instantiated with class attributes, not a subclass with its own code, unless it needs a bespoke query — see kb_repository.py, ticket_repository.py below)
│   │   ├── ticket_repository.py        # ScopedRepository[Ticket] + view/filter query builders for F04's five dashboard views
│   │   └── kb_repository.py            # ScopedRepository[KbArticle] + hybrid trigram/vector search query
│   ├── services/
│   │   ├── admin_crud_service.py       # AdminCrudService[ModelT, CreateT, UpdateT] — Generic CRUD Pattern, defined once
│   │   ├── auth_service.py
│   │   ├── customer_service.py
│   │   ├── ticket_service.py
│   │   ├── ticket_transition_service.py
│   │   ├── assignment_service.py
│   │   ├── sla_service.py
│   │   ├── kb_service.py
│   │   ├── ai_service.py
│   │   ├── channel_service.py
│   │   ├── portal_service.py
│   │   ├── report_service.py
│   │   └── api_key_service.py
│   ├── channels/
│   │   ├── base.py                     # ChannelAdapter, NormalizedMessage, NormalizedAttachment — Shared Abstraction #4
│   │   ├── email_adapter.py            # Functional — IMAP poll
│   │   ├── whatsapp_adapter.py         # Declared; normalize()/send_reply() raise NotImplementedError
│   │   ├── sms_adapter.py              # Declared; raises NotImplementedError
│   │   └── chat_adapter.py             # Declared; raises NotImplementedError
│   ├── ai/
│   │   └── litellm_wrapper.py          # LlmCapability, LlmResult, LiteLlmWrapper — Shared Abstraction #5
│   ├── core/
│   │   ├── security.py                 # JWT issue/verify, Argon2 hashing (passlib)
│   │   ├── permissions.py              # CurrentActor, require_permission — Shared Abstraction #2
│   │   ├── audit.py                    # audited decorator — Shared Abstraction #3
│   │   ├── errors.py                   # PermissionDeniedError, IllegalTransitionError, NotFoundError → HTTP mapping with localized ErrorResponse
│   │   └── lint_no_vendor_sdk.py       # Import-lint enforcing Principle VIII / PLAN.md C8
│   ├── api/
│   │   ├── deps.py                     # get_current_actor() (JWT or API-key → CurrentActor), get_session()
│   │   ├── router.py                   # Aggregates every router below under /api/v1, per contracts/openapi.yaml
│   │   └── routers/                    # One file per contracts/openapi.yaml tag; each handler: validate request → call one service method → serialize response. No business logic here (constitution/PLAN.md: "route handlers validate, delegate, serialize")
│   │       ├── auth.py
│   │       ├── admin_config.py         # branches, departments, users, roles, categories, priorities, ticket-statuses, status-transitions, sla-policies, quick-replies, teams
│   │       ├── customers.py
│   │       ├── tickets.py
│   │       ├── kb.py
│   │       ├── ai.py
│   │       ├── channels.py
│   │       ├── portal.py
│   │       ├── reports.py
│   │       ├── api_keys.py
│   │       └── health.py
│   ├── jobs/
│   │   ├── worker.py                   # ARQ WorkerSettings — registers the three jobs below
│   │   ├── email_poll_job.py           # Runs ChannelService.poll_email() every N seconds
│   │   ├── categorization_job.py       # Runs AiService.categorize(ticket_id); enqueued by TicketService.create
│   │   └── sla_sweep_job.py            # Runs SlaService.sweep_breaches() every 5 minutes (PLAN.md F05)
│   └── seed/
│       └── seed.py                     # Idempotent seed per PLAN.md §7 — branches/departments/users/customers/tickets/KB/categories/priorities/statuses+transitions/SLA policies/quick replies/channel_configs/permissions incl. audit.read + report.cross_branch granted to admin
├── tests/
│   ├── unit/                           # Principle XIV scope only: transition legality, permission checks, SLA computation, tenant scoping
│   ├── integration/
│   └── golden/
│       └── bilingual_tickets.json      # 20-ticket golden set for AI categorization scoring (FR-050)
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── pyproject.toml
└── .env.example

frontend/
├── app/
│   ├── [locale]/
│   │   ├── layout.tsx                  # Sets <html dir> from active locale (next-intl) — the only place `dir` is set
│   │   ├── (agent)/
│   │   │   ├── dashboard/page.tsx      # F04's five views via TanStack Query against GET /tickets?view=
│   │   │   ├── tickets/[id]/page.tsx   # Ticket detail incl. inline customer context, AI panels, timeline
│   │   │   ├── customers/page.tsx
│   │   │   ├── customers/[id]/page.tsx
│   │   │   ├── kb/page.tsx
│   │   │   ├── reports/page.tsx
│   │   │   └── admin/                  # API-key management only (issue/list/revoke) this sprint — admin config for branches, departments, users, roles, categories, priorities, statuses, transitions, SLA policies, quick replies, and teams is API-only (already-built AdminCrudService/TeamCrudService endpoints); no UI for those this sprint (docs/DEBT.md D12, `/speckit-analyze` finding F1)
│   │   └── (portal)/
│   │       ├── submit/page.tsx
│   │       ├── track/page.tsx
│   │       └── kb/page.tsx
├── components/
│   ├── ui/                             # shadcn/ui primitives
│   └── ltr-text.tsx                    # <LtrText> — sets dir="ltr" locally for reference numbers/emails/phones/URLs (constitution III)
├── lib/
│   └── api-client.ts                   # Typed client generated from contracts/openapi.yaml
├── messages/
│   ├── ar.json
│   └── en.json
├── next.config.js
├── tailwind.config.ts                  # Logical properties only — no ml-/mr-/pl-/pr-/left-/right-
└── package.json

docs/
├── architecture/stack.md               # Already exists — authoritative tech source
└── DEBT.md                             # To be created before batch 4a per constitution Principle XIII / PLAN.md §8 (not part of this plan's output)
```

**Structure Decision**: Web application (Option 2) — separate `backend/` (FastAPI) and
`frontend/` (Next.js), matching `docs/architecture/stack.md`'s two-runtime design and PLAN.md
§6's batch sequencing (backend batches 4b–4d, 4f–4h build against the API directly; frontend
batch 4e/4i consumes it).

## Shared Abstractions

These five carry the constitution. Every other module composes them; none of them is
reimplemented, subclassed-around, or bypassed anywhere else in this plan.

### 1. `ScopedRepository` (`app/repositories/scoped_repository.py`) — Principle V / PLAN.md C5

```python
class ScopingMode(str, Enum):
    S1_FULL = "s1_full"                        # branch_id + department_id, both NOT NULL
    S2_BRANCH_DEPT_OPTIONAL = "s2_branch_dept_optional"  # branch_id NOT NULL, department_id NULL
    S3_BRANCH_ONLY = "s3_branch_only"           # branch_id NOT NULL only
    S4_TRANSITIVE = "s4_transitive"             # no columns; join to parent_model via parent_fk_column
    S5_SYSTEM_NULLABLE = "s5_system_nullable"   # branch_id NULL
    S6_GLOBAL = "s6_global"                     # no columns, no filter

@dataclass(frozen=True)
class TenantScope:
    branch_id: UUID | None
    department_id: UUID | None
    cross_branch: bool = False   # honored only by ReportService, and only after a permission check

class ScopedRepository(Generic[ModelT]):
    model: ClassVar[type[Any]]
    scoping_mode: ClassVar[ScopingMode]
    parent_model: ClassVar[type[Any] | None] = None      # required iff scoping_mode is S4
    parent_fk_column: ClassVar[str | None] = None         # e.g. "ticket_id" — required iff S4
    has_soft_delete: ClassVar[bool] = False                # True iff the model has an is_active column (data-model.md §0.4)

    def __init__(self, session: AsyncSession, scope: TenantScope) -> None: ...

    async def get(self, id: UUID) -> ModelT | None: ...
    async def list(self, filters: Mapping[str, Any] | None = None, order_by: str | None = None,
                    limit: int = 50, offset: int = 0) -> list[ModelT]: ...
    async def create(self, values: Mapping[str, Any]) -> ModelT: ...
    async def update(self, id: UUID, values: Mapping[str, Any]) -> ModelT: ...
    async def deactivate(self, id: UUID) -> ModelT:
        """Sets is_active=False. Raises NotImplementedError if has_soft_delete is False —
        use delete() instead (data-model.md §0.4's hard-delete tables)."""
    async def delete(self, id: UUID) -> None:
        """Hard DELETE. Raises NotImplementedError if has_soft_delete is True — use
        deactivate() instead. Lets the DB's ON DELETE RESTRICT surface as an IntegrityError,
        mapped by app/core/errors.py to a 409 with a localized message."""

    def _scoped_select(self) -> Select[tuple[ModelT]]:
        """The ONLY method in the entire codebase permitted to add a branch_id/department_id
        predicate or a parent-join predicate to a query. Every public method above calls this
        first. Behavior by scoping_mode:
          S1: WHERE model.branch_id = scope.branch_id AND model.department_id = scope.department_id
          S2: WHERE model.branch_id = scope.branch_id
              AND (model.department_id = scope.department_id OR model.department_id IS NULL)
          S3: WHERE model.branch_id = scope.branch_id
          S4: JOIN parent_model ON model.parent_fk_column == parent_model.id, then apply
              parent_model's OWN _scoped_select predicate (recursive — a S4 child of an S4
              child, e.g. none currently exist, still resolves correctly)
          S5: WHERE model.branch_id = scope.branch_id OR model.branch_id IS NULL
              (a system-level/pre-resolution row is visible within any scope that could plausibly
              own it — narrower filtering, where needed, is applied by the calling service, e.g.
              AuditService only ever queries S5 rows explicitly by actor/entity, never lists all)
          S6: no predicate at all
        cross_branch=True on the scope skips the branch predicate entirely for S1/S2/S3; it is
        set only by ReportService, and only after that service has itself checked
        `report.cross_branch` is in the caller's CurrentActor.permissions (§Service Classes).
        """
```

Every entity repository is `ScopedRepository[Model]` with `model`/`scoping_mode`/
`parent_model`/`parent_fk_column`/`has_soft_delete` set as class attributes — no subclass writes
its own `WHERE`. `TicketRepository` and `KbRepository` (the two files listed under
`repositories/` beyond the base) *add* methods (dashboard views, hybrid search) but never
override `_scoped_select`.

### 2. Permission guard (`app/core/permissions.py`) — Principle X / PLAN.md C10

```python
@dataclass(frozen=True)
class CurrentActor:
    user_id: UUID
    scope: TenantScope
    permissions: frozenset[str]
    correlation_id: UUID

class PermissionDeniedError(Exception):
    def __init__(self, code: str) -> None: ...

def require_permission(code: str):
    """Wraps an async SERVICE method (never a route handler). The wrapped method's signature
    MUST be `(self, actor: CurrentActor, *args, **kwargs)`. Before calling it, checks
    `code in actor.permissions`; raises PermissionDeniedError(code) if not, which app/core/errors.py
    maps to HTTP 403 with a localized ErrorResponse. On success, calls straight through with no
    other side effect."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(self, actor: CurrentActor, *args, **kwargs):
            if code not in actor.permissions:
                raise PermissionDeniedError(code)
            return await fn(self, actor, *args, **kwargs)
        return wrapper
    return decorator

def require_permission_via(code_selector: Callable[[Any], str]):
    """Identical to require_permission, except the permission code is read off the bound
    instance at call time via `code_selector(self)` instead of being a fixed literal — this is
    the ONLY difference. Exists because AdminCrudService's four decorated methods (§Generic CRUD
    Pattern) are defined once on the generic base class, but each subclass sets a different
    `read_permission`/`write_permission` class attribute; a literal `code` captured at
    decoration time on the base class could never see a subclass's value. Wraps an async SERVICE
    method whose signature MUST be `(self, actor: CurrentActor, *args, **kwargs)` — identical
    calling convention to require_permission."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(self, actor: CurrentActor, *args, **kwargs):
            code = code_selector(self)
            if code not in actor.permissions:
                raise PermissionDeniedError(code)
            return await fn(self, actor, *args, **kwargs)
        return wrapper
    return decorator
```

A route handler's only auth-adjacent responsibility is calling `get_current_actor()` (which
decodes the JWT or API key into a `CurrentActor`, resolving `permissions` as the union of
`role_permissions` reachable via every matching `user_roles` row, or the API key's `scopes`) and
passing it as the first argument to a service method. The permission decision itself always
executes inside the decorated service method, never in `app/api/routers/*`.

### 3. Audit-write decorator (`app/core/audit.py`) — Principle VII / PLAN.md C7

```python
def audited(entity_type: str, action: str):
    """Wraps an async SERVICE method already wrapped by (or itself calling) require_permission,
    whose signature is `(self, actor: CurrentActor, id: UUID | None, *args, **kwargs) -> ModelT | None`.

    Behavior, all inside the SAME AsyncSession/transaction as the wrapped call (never a separate
    commit):
      1. If `id` is not None, load the entity's current row and serialize it as `before`
         (None if the row doesn't exist yet — the create case).
      2. Call the wrapped method; let any exception propagate uncaught (the transaction rolls
         back, so no audit row is written — this IS the "rolled-back transaction leaves no audit
         row" guarantee, not a separate try/except).
      3. Serialize the result as `after` (None for delete/deactivate-returning-None).
      4. session.add(AuditLog(actor_id=actor.user_id, action=action, entity_type=entity_type,
         entity_id=(result.id if result is not None else id), before=before, after=after,
         correlation_id=actor.correlation_id)) — added to the session, not committed
         independently; the request-scoped get_session() dependency commits once, at the end of
         the request, per app/db.py.
      5. Return the wrapped method's result unchanged.
    """
    return audited_via(lambda self: entity_type, action)


def audited_via(entity_type_selector: Callable[[Any], str], action: str):
    """Identical to `audited`, except entity_type is read off the bound instance at call time
    via `entity_type_selector(self)` instead of being a fixed literal — the audit-write analogue
    of `require_permission_via` above. Added during Batch 4b: `AdminCrudService.create`/`.update`/
    `.remove` (§Generic CRUD Pattern) are defined once on the generic base class, but each
    subclass (`BranchCrudService`, `DepartmentCrudService`, ...) sets a different `entity_type`
    class attribute — a literal `entity_type` captured at decoration time on the base class could
    never see a subclass's value. Every `AdminCrudService` subclass's `create`/`update`/`remove`
    is wrapped with `@audited_via(lambda self: self.entity_type, action)`, not the plain `audited`
    shown above (which stays the right choice for a bespoke, non-generic service method with a
    fixed, literal entity_type — e.g. `TeamCrudService.add_member`'s
    `@audited("team_member", "create")`). Same five-step behavior as `audited`, substituting
    `entity_type_selector(self)` for the literal `entity_type` at step 4.
    """
```

### 4. `ChannelAdapter` (`app/channels/base.py`) — Principle VIII's channel half / PLAN.md F03

```python
class NormalizedAttachment(BaseModel):
    filename: str
    content_type: str
    data: bytes | None
    source_url: str | None

class NormalizedMessage(BaseModel):
    external_id: str
    channel: ChannelEnum
    from_identity: str
    to_identity: str                    # the receiving identifier — matched against channel_configs.identifier
    subject: str | None
    body: str
    locale: Literal["ar", "en"]
    attachments: list[NormalizedAttachment]
    received_at: datetime

class ChannelAdapter(Protocol):
    channel: ClassVar[ChannelEnum]
    def normalize(self, raw: dict[str, Any]) -> NormalizedMessage: ...
    async def send_reply(self, ticket_id: UUID, body: str, locale: Literal["ar", "en"]) -> None: ...
```

`EmailAdapter` implements both methods functionally. `WhatsappAdapter`, `SmsAdapter`,
`ChatAdapter` implement the `channel` class attribute and define both methods with a body of
exactly `raise NotImplementedError(f"{self.channel} channel is Tier D — see specs/00X")` — present
and importable, not absent, per PLAN.md F03. `ChannelService.ingest()` (§Service Classes) is the
only caller of `normalize()`; it is written entirely against the `ChannelAdapter` protocol, never
against a concrete adapter class, which is what makes "adding a channel later requires zero
changes to ticket creation logic" mechanically true rather than just documented.

### 5. `LiteLlmWrapper` (`app/ai/litellm_wrapper.py`) — Principle VIII/IX / PLAN.md C8/C9

```python
class LlmCapability(str, Enum):
    CATEGORIZE = "categorize"
    SUMMARIZE = "summarize"
    SUGGEST_REPLY = "suggest_reply"

class LlmResult(BaseModel):
    text: str | None
    structured: dict[str, Any] | None
    fallback_used: bool
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None

class LiteLlmWrapper:
    def __init__(self, api_base: str, api_key: str, model_chat: str, model_classify: str,
                 timeout_s: float = 10.0, max_retries: int = 1) -> None: ...

    async def complete(self, capability: LlmCapability, prompt: str, prompt_version: str,
                        ticket_id: UUID | None, correlation_id: UUID) -> LlmResult:
        """NEVER raises to the caller. On timeout, HTTP error, or retry exhaustion, returns
        LlmResult(text=None, structured=None, fallback_used=True, ...) instead of propagating.
        Every call — success or failure — inserts exactly one llm_calls row (capability, model,
        prompt_version, token counts if known, latency_ms, fallback_used, error if any,
        correlation_id) via its own short-lived session, committed immediately (not tied to the
        caller's transaction — an AI call outcome must be recorded even if the caller's ticket
        transaction later rolls back for an unrelated reason). This is the only module in the
        codebase that imports an LLM HTTP client; app/core/lint_no_vendor_sdk.py fails CI if any
        other module imports one directly."""
```

`AiService` (§Service Classes) is the only caller. No `AiService` method ever raises — it catches
nothing, because `LiteLlmWrapper.complete()` already never raises; the fallback text/behavior
named in `spec.md` FR-009/FR-047 is simply what each `AiService` method returns when
`result.fallback_used` is `True`.

## Generic CRUD Pattern

Defined once. **Entities that follow it verbatim** (i.e. their router calls only
`AdminCrudService` methods, with no bespoke service code): `branches`, `departments`, `users`
(with one override — see below), `roles`, `categories`, `priorities`, `ticket_statuses`,
`sla_policies`, `quick_replies`, `teams`. `status_transitions` uses the `list`/`create`/`update`/
`delete` subset only (no single-`get`, matching `contracts/openapi.yaml`).

```python
class AdminCrudService(Generic[ModelT, CreateSchemaT, UpdateSchemaT]):
    repository_cls: ClassVar[type[ScopedRepository]]
    read_permission: ClassVar[str]              # e.g. "category.read" — granted to agent, lead, admin
    write_permission: ClassVar[str] = "admin.config"   # admin-only, unchanged across every subclass
    entity_type: ClassVar[str]                 # for the audited() decorator

    def __init__(self, session: AsyncSession) -> None: ...

    @require_permission_via(lambda self: self.read_permission)   # see note below
    async def list(self, actor: CurrentActor, filters: Mapping[str, Any] | None = None,
                    limit: int = 50, offset: int = 0) -> list[ModelT]: ...
    @require_permission_via(lambda self: self.read_permission)
    async def get(self, actor: CurrentActor, id: UUID) -> ModelT: ...     # raises NotFoundError
    @require_permission_via(lambda self: self.write_permission)
    async def create(self, actor: CurrentActor, data: CreateSchemaT) -> ModelT: ...
    @require_permission_via(lambda self: self.write_permission)
    async def update(self, actor: CurrentActor, id: UUID, data: UpdateSchemaT) -> ModelT: ...
    @require_permission_via(lambda self: self.write_permission)
    async def remove(self, actor: CurrentActor, id: UUID) -> ModelT | None:
        """Calls repository.deactivate(id) if repository_cls.has_soft_delete else
        repository.delete(id) — the branch is on the class attribute, not re-decided per call."""
```

**Read/write permissions are split, not shared** (fixed after `/speckit-analyze` finding D1: the
original single `permission` attribute gated `list`/`get` behind `admin.config`, which only the
`admin` role holds — meaning an Agent could not read categories, priorities, ticket statuses, SLA
policies, teams, or quick replies at all, breaking FR-016/FR-019/FR-029 for its primary actor).
`list`/`get` require `read_permission` (`{entity}.read`, seeded to `agent`, `lead`, *and* `admin` —
`data-model.md` §5); `create`/`update`/`remove` require `write_permission` (`admin.config`,
`admin`-only, unchanged). Every one of the ten generic-CRUD subclasses sets `read_permission` to
its own `{entity}.read` code (`branch.read`, `department.read`, `user.read`, `role.read`,
`category.read`, `priority.read`, `ticket_status.read`, `status_transition.read`,
`sla_policy.read`, `quick_reply.read`, `team.read`); none overrides `write_permission`.

`create`, `update`, and `remove` are each additionally wrapped with `@audited(entity_type,
action)` at definition time in `admin_crud_service.py` — `list`/`get` are not audited (reads have
no concept of a before/after change, matching `data-model.md`'s `audit_logs` schema).
`require_permission_via` (defined alongside `require_permission` in `app/core/permissions.py`,
§Shared Abstractions #2) exists so the permission code can be a class attribute instead of a
literal.

**`UserService(AdminCrudService[User, UserCreate, UserUpdate])`** overrides `create` only, to hash
`password` into `password_hash` via `passlib`'s Argon2 hasher before delegating to
`super().create()` — everything else (list/get/update/remove, audit, permission) is inherited
unchanged.

**`TeamCrudService(AdminCrudService[Team, TeamCreate, TeamUpdate])`** (`read_permission=
"team.read"`, `has_soft_delete=False` — hard delete, `data-model.md` §0.4) adds exactly one
bespoke method beyond the inherited CRUD: `async def add_member(self, actor: CurrentActor,
team_id: UUID, user_id: UUID) -> TeamMember`, wrapped with `@require_permission("admin.config")`
and `@audited("team_member", "create")` — a team with no way to add a member is otherwise a dead
end, the same shape of gap D1 fixed one level up (`/speckit-analyze` finding, follow-up).

Every other S1/S2/S3 entity not covered by the ten above (`kb_articles`, `quick_replies` is
already listed) gets its CRUD permission named `{entity}.read`/`{entity}.create` following the
same `ticket.read`/`ticket.create` convention documented in `data-model.md` §5 — `KbService`
(bespoke, below) still composes `AdminCrudService`'s `list`/`get` for the plain-CRUD parts of its
surface and only adds bespoke methods for publish/search/chunking.

## Service Classes

Bespoke services — i.e. containing at least one method the Generic CRUD Pattern does not cover.
Every mutating method below carries `@require_permission(...)` and, where it returns a
persisted entity, `@audited(...)`; both are omitted from the signatures below for brevity and
stated once here instead, per this plan's "never write 'as needed'" instruction — the permission
code for each is the one named in `contracts/openapi.yaml`'s matching `x-permission`.

**`AuthService`**
- `async def login(self, email: str, password: str) -> TokenPair`
- `async def refresh(self, refresh_token: str) -> TokenPair`
- `async def logout(self, actor: CurrentActor) -> None`

**`CustomerService`**
- `async def search(self, actor: CurrentActor, q: str | None, limit: int, offset: int) -> list[Customer]`
- `async def get(self, actor: CurrentActor, id: UUID) -> Customer`
- `async def create(self, actor: CurrentActor, data: CustomerCreate) -> Customer` — rejects if `data.contact_methods` has zero items or more/less than exactly one `is_primary=True` (FR-011; also DB-enforced, §data-model.md §1.11)
- `async def update(self, actor: CurrentActor, id: UUID, data: CustomerUpdate) -> Customer`
- `async def deactivate(self, actor: CurrentActor, id: UUID) -> Customer`
- `async def get_history(self, actor: CurrentActor, id: UUID) -> CustomerHistory` — merges `tickets` and `ticket_events` for every ticket owned by this customer, sorted by timestamp (FR-014)
- `async def add_contact_method(self, actor: CurrentActor, customer_id: UUID, data: ContactMethodCreate) -> ContactMethod`
- `async def add_attachment(self, actor: CurrentActor, customer_id: UUID, file: UploadFile) -> Attachment`

**`TicketService`**
- `async def list(self, actor: CurrentActor, view: TicketView | None, filters: TicketFilters, limit: int, offset: int) -> list[TicketSummary]` — `view` maps to one of F04's five queue definitions via `TicketRepository`
- `async def get(self, actor: CurrentActor, id: UUID) -> Ticket` — includes computed `sla_first_response_due_at`/`sla_resolution_due_at`/`sla_breach_state` via `SlaService` (never stored)
- `async def create(self, actor: CurrentActor, data: TicketCreate) -> Ticket` — validates `data.category_id` and `data.priority_id` are each currently active, and, if the resolved category/priority is department-scoped (its own `department_id` is not `NULL`), that it matches the ticket's `department_id`; rejects with a localized validation error (422) if either check fails (FR-016) — generates `reference_no` from a DB sequence (`TKT-{year}-{6-digit}`), resolves `sla_policy_id` via `SlaService.resolve_policy`, writes the `created` event, enqueues `categorization_job` (never awaits it — FR-049)
- `async def update(self, actor: CurrentActor, id: UUID, data: TicketUpdate) -> Ticket`
- `async def assign(self, actor: CurrentActor, id: UUID, assignee_id: UUID | None, team_id: UUID | None) -> Ticket`
- `async def add_note(self, actor: CurrentActor, id: UUID, body: str) -> TicketEvent`
- `async def add_reply(self, actor: CurrentActor, id: UUID, body: str) -> TicketEvent` — stamps `first_response_at` iff it is currently `NULL` (FR-021)
- `async def add_attachment(self, actor: CurrentActor, id: UUID, file: UploadFile) -> Attachment`
- `async def correct_triage(self, actor: CurrentActor, id: UUID, branch_id: UUID, department_id: UUID) -> Ticket` — clears `needs_triage`, writes a `field_changed` event per `field_name` (FR-023c; `data-model.md` §1.17)
- `async def get_events(self, actor: CurrentActor, id: UUID) -> list[TicketEvent]`

**`TicketTransitionService`**
- `async def change_status(self, actor: CurrentActor, ticket_id: UUID, to_status_id: UUID, reason: str | None) -> Ticket` — the ONLY method in the codebase that queries `status_transitions`; raises `IllegalTransitionError(current_status_id, permitted_status_ids)` (→ HTTP 422) when no `(from_status_id, to_status_id)` row matches the ticket's branch/department (falling back to the `department_id IS NULL` default row); raises `PermissionDeniedError` if the matched row's `required_permission` is set and absent from `actor.permissions`; raises a validation error if `requires_reason` is true and `reason` is `None`

**`AssignmentService`**
- `async def auto_assign_ticket(self, ticket_id: UUID) -> Ticket | None` — round-robins over active `ticket.own`-holding agents in the ticket's department who are not flagged unavailable; returns `None` (ticket stays unassigned) if none are eligible. Called only by `categorization_job`, after categorization completes — never directly by `TicketService.create` (fixed after `/speckit-analyze` finding F1: `TicketCreate` never accepts `assignee_id` in the first place, and a second, synchronous call site here would risk double-assigning a ticket against the async job's own call).

**`SlaService`**
- `def compute_due_dates(self, ticket: Ticket, policy: SlaPolicy, branch: Branch) -> SlaDueDates` — pure function; applies `sla_paused_ms` and, if `policy.business_hours_only`, `branch.business_hours`/`branch.timezone`
- `def compute_breach_state(self, due_dates: SlaDueDates, now: datetime) -> Literal["on_track", "at_risk", "breached"]` — pure function; `at_risk` when <25% of the relevant window remains
- `async def resolve_policy(self, branch_id: UUID, department_id: UUID, category_id: UUID, priority_id: UUID) -> SlaPolicy | None` — exact category+priority → priority-only → category-only → default (`data-model.md` §1.19 index)
- `async def override_policy(self, actor: CurrentActor, ticket_id: UUID, sla_policy_id: UUID, reason: str) -> Ticket` — `require_permission("ticket.sla_override")`; recomputes both due dates from the ticket's original `created_at` under the new policy (FR-039); an immediately-breaching result is permitted and is picked up by the next `sweep_breaches()` run rather than recorded inline, keeping breach recording in exactly one place
- `async def sweep_breaches(self) -> int` — `sla_sweep_job`'s body; for every open ticket whose computed `breach_state == "breached"` with no existing `sla_breached` event for its current target, writes one, raises priority one severity level, reassigns to the department's lead; returns the count written (idempotency check is "does an `sla_breached` event already exist for this ticket+target", so re-running produces zero new events)

**`KbService`**
- `async def create_article(self, actor: CurrentActor, data: KbArticleCreate) -> KbArticle`
- `async def update_article(self, actor: CurrentActor, id: UUID, data: KbArticleUpdate) -> KbArticle` — re-chunks (~500 tokens, 50 overlap) and re-embeds both locales on any body change
- `async def publish_article(self, actor: CurrentActor, id: UUID) -> KbArticle` — rejects (422) unless `title_ar`/`title_en`/`body_ar`/`body_en` are all non-empty (FR-041)
- `async def search(self, actor: CurrentActor, query: str, limit: int) -> list[KbSearchResult]` — `pg_trgm` lexical + `pgvector` cosine, reciprocal-rank-fused; reranked with `bge-reranker-v2-m3` iff the reranker feature flag is on, else fused order returned directly (FR-043)

**`AiService`** — every method below wraps `LiteLlmWrapper.complete()`/`KbService.search()`; none raises
- `async def summarize(self, ticket_id: UUID) -> AiSummaryResponse` — fallback: first 300 characters of `description`
- `async def suggest_reply(self, ticket_id: UUID) -> AiSuggestedReplyResponse` — fallback: empty draft
- `async def suggest_solution(self, ticket_id: UUID) -> list[KbSearchResult]` — top 3 from `KbService.search()` over subject+description; fallback: empty list
- `async def categorize(self, ticket_id: UUID) -> None` — `categorization_job`'s body; writes `ai_suggested_category_id`/`ai_category_confidence` directly (never `category_id`); fallback: leaves both `NULL`
- `async def apply_categorization_decision(self, actor: CurrentActor, ticket_id: UUID, accepted: bool, override_category_id: UUID | None) -> Ticket` — writes the ticket's real `category_id` and an `ai_suggestion_applied` event recording the original suggestion + confidence (FR-044)
- `async def run_categorization_benchmark(self, actor: CurrentActor) -> BenchmarkResult` — scores `tests/golden/bilingual_tickets.json` (FR-050)

**`ChannelService`**
- `def register_adapter(self, adapter: ChannelAdapter) -> None` — called once per adapter at app startup (`app/main.py`)
- `async def ingest(self, channel: ChannelEnum, raw: dict[str, Any]) -> InboundMessageAccepted` —
  1. `adapter.normalize(raw)` → `NormalizedMessage`; the raw payload is persisted to
     `inbound_messages` *before* any further processing, per PLAN.md F03.
  2. If `NormalizedMessage.subject` (or body) contains a valid, existing `reference_no`: resolve
     the ticket by that reference; its `branch_id`/`department_id` **override** whatever
     `channel_configs` would have resolved (FR-023b). If the receiving identifier's configured
     branch/department differs, append a `field_changed` timeline event recording the mismatch —
     it does not block the append.
  3. Otherwise: look up `channel_configs` by `to_identity`. A match gives `(branch_id,
     department_id, default_category_id)`; no match falls back to `config.SYSTEM_DEFAULT_BRANCH_ID`/
     `SYSTEM_DEFAULT_DEPARTMENT_ID` and sets `needs_triage=True` (FR-023a).
  4. Constructs a **fresh `TenantScope`** from the branch/department resolved in step 2 or 3 —
     *never* reuses the caller's own `CurrentActor.scope` (the caller here is typically an API-key
     client with no single home branch). Contact-method matching (FR-023) is performed through a
     `ContactMethodRepository`/`CustomerRepository` pair constructed with this resolved scope, so
     it is structurally impossible for it to match a customer in a different branch/department.
  5. No match on `from_identity` → creates a new `Customer` + primary `ContactMethod` in the
     resolved scope, then a new `Ticket`; a match on `external_id` or `reference_no` → appends a
     `reply_sent`/`note_added` event to the existing ticket instead (FR-024's threading rule).
- `async def poll_email(self) -> int` — `email_poll_job`'s body; IMAP poll, calls `ingest()` per message, returns count processed

**`PortalService`** (unauthenticated — no `CurrentActor`/`require_permission`; every method is
inherently public per `contracts/openapi.yaml`'s `security: []`)
- `async def submit_ticket(self, data: PortalTicketSubmit) -> str` — returns `reference_no`.
  Branch is resolved from `data.category_id`'s own `branch_id` (categories are always S2-scoped
  to exactly one branch); department is the category's `department_id` if set, else the same
  system-default-plus-`needs_triage` fallback as `ChannelService` step 3 above — reusing the
  identical accommodation rather than inventing a second one.
- `async def track_ticket(self, reference_no: str, contact_value: str) -> PortalTicketView | None` — `None` on any mismatch (unknown reference OR wrong contact), so the router returns an identical 404 either way (FR-053) — no branching on "which reason" anywhere past this method
- `async def get_history(self, reference_no: str, contact_value: str) -> list[PortalTicketView] | None` — same resolution; filters out every `visibility="internal"` event before returning (FR-054)

**`ReportService`**
- `async def tickets_by_status(self, actor: CurrentActor, date_from: date | None, date_to: date | None, cross_branch: bool) -> TicketsByStatusReport`
- `async def sla_compliance(self, actor: CurrentActor, date_from: date | None, date_to: date | None, cross_branch: bool) -> SlaComplianceReport`
- `async def agent_volume(self, actor: CurrentActor, date_from: date | None, date_to: date | None, cross_branch: bool) -> AgentVolumeReport`

  All three: if `cross_branch` is `True`, raise `PermissionDeniedError("report.cross_branch")`
  unless that code is in `actor.permissions`; only then does the constructed `TenantScope` set
  `cross_branch=True` before querying (FR-060).

**`ApiKeyService`**
- `async def issue(self, actor: CurrentActor, data: ApiKeyCreate) -> tuple[ApiKey, str]` — generates a random secret, returns `(record, plaintext)`; only `key_hash` (Argon2) is persisted
- `async def revoke(self, actor: CurrentActor, id: UUID) -> ApiKey` — sets `expires_at = now()`
- `async def authenticate(self, plaintext_key: str) -> CurrentActor` — looks up by `key_hash`, builds a `CurrentActor` whose `permissions` is exactly `scopes` (JSONB) and whose `scope` is `TenantScope(branch_id=api_keys.branch_id, department_id=None)`; used by `get_current_actor()` (`app/api/deps.py`) when the request carries `X-API-Key` instead of a bearer JWT

No bespoke `AuditService` exists — `audited` (§Shared Abstractions #3) is the entire write path,
and audit *reading* is Tier D (`specs/006-audit-log-ui`), out of this plan's scope entirely.

## Complexity Tracking

*Empty — the Constitution Check above found no violation requiring justification.*

## Post-Design Constitution Check & Self-Audit

*Re-checked after Phase 1 design, per this command's own workflow, and per this turn's explicit
instruction to re-read the constitution and PLAN.md §4.1 and report every place the artifacts
produced in this run violate a principle or diverge from the assigned scoping pattern. Three real
issues were found while drafting `data-model.md`/`contracts/openapi.yaml` in this session — they
were fixed in place before this plan was written, and are reported here rather than silently
corrected, per the instruction to list them.*

### Issues found and fixed in this run

1. **Over-applied "reference-data base."** An early draft of `data-model.md` §0.4 gave every
   `label_ar`/`label_en` table (`branches`, `departments`, `roles`, `permissions`, `categories`,
   `priorities`, `ticket_statuses`, `sla_policies`, `quick_replies`, `teams`) both `is_active` and
   `sort_order` uniformly. PLAN.md §4.2 lists these two fields per table *inconsistently* (e.g.
   `roles` has neither; `ticket_statuses` has `sort_order` but not `is_active`) — the uniform draft
   invented four fields PLAN.md never specified (`roles.is_active`, `roles.sort_order`,
   `permissions.is_active`, `permissions.sort_order`, `priorities.is_active`,
   `priorities.sort_order`, `ticket_statuses.is_active`, `sla_policies.is_active`,
   `sla_policies.sort_order`, `quick_replies.is_active`, `quick_replies.sort_order`,
   `teams.is_active`, `teams.sort_order`, `departments.sort_order`, `branches.sort_order`).
   **Fixed**: §0.4 now lists only `label_ar`/`label_en` as universal, with a per-table matrix for
   `is_active`/`sort_order` matching PLAN.md §4.2 exactly; `contracts/openapi.yaml`'s
   `ReferenceDataBase` schema and the seven affected entity schemas were corrected to match.
2. **Invented `ticket_events.event_type` value.** An early draft added `'branch_corrected'` to the
   `event_type` `CHECK` constraint to represent FR-023c's needs-triage correction — a value not in
   PLAN.md §4.2's explicit eleven-value list. **Fixed**: the correction is now recorded as a
   `field_changed` event (`field_name = 'branch_id'` or `'department_id'`), reusing the existing
   generic shape; the `CHECK` constraint and the OpenAPI `TicketEvent.event_type` enum both now
   match PLAN.md's list exactly, with zero added values.
3. **Inconsistent `updated_at`/`updated_by` carve-out.** An early draft excluded `role_permissions`
   from §0.2's "every mutable table" rule with an ad hoc justification, while leaving the
   structurally identical `user_roles` and `team_members` join tables to inherit it normally —
   an unjustified, self-inconsistent exception. **Fixed**: `role_permissions` now inherits
   `updated_at`/`updated_by` like every other mutable table; no exception is carved out anywhere
   in `data-model.md` that PLAN.md does not itself state.

A related but *unfixed-by-design* item, carried over from `research.md` Part 2 rather than fixed
here: PLAN.md §4.1's own Assignment table is missing rows for six tables (resolved using PLAN.md's
own pattern definitions, not invented) and its `channel_configs`/`llm_calls` rows are visibly
misplaced (a formatting defect, not a content one). This plan does not edit PLAN.md — see
`research.md` Part 2 for the full reasoning and the recommendation to correct PLAN.md §4.1 itself.

### Scoping-pattern verification (PLAN.md §4.1, this turn's explicit check)

Every table in `data-model.md` §2 was checked individually against its assigned pattern:

- **No S4 or S6 table carries `branch_id` or `department_id`.** Verified for all nine
  (`branches`, `roles`, `permissions`, `role_permissions` — S6; `team_members`, `contact_methods`,
  `ticket_events`, `kb_article_chunks` — S4). None has either column, in `data-model.md` or in any
  `contracts/openapi.yaml` schema.
- **`ChannelService.ingest()` (§Service Classes) constructs a fresh `TenantScope` from the
  message's resolved branch/department**, not the calling API key's own scope — checked
  specifically because reusing an API-key's scope here would have been a subtle, easy-to-miss
  violation of FR-023's per-branch customer-identity requirement despite every table still having
  the "correct" pattern on paper.
- **`ReportService`'s `cross_branch` flag is gated by a permission check before it reaches
  `TenantScope`**, never trusted from the request directly — checked because `TenantScope.
  cross_branch` is the one deliberate, narrow escape hatch from `ScopedRepository`'s default
  filtering, and an ungated path to it would undermine Principle V everywhere it's used.
- **No route handler in `app/api/routers/*` (per the file tree above) contains a permission check
  or an audit write** — both decorators are applied at service-method definition time only,
  confirmed by design (§Shared Abstractions #2, #3) rather than left implicit.

No further violations found. **No new functionality was added while fixing the three issues
above** — each fix removed an invented field/value/exception rather than adding one, per this
turn's instruction.

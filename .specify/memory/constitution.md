<!--
Sync Impact Report
Version change: [TEMPLATE] → 1.0.0 (initial ratification)
Bump rationale: First concrete adoption of the constitution from a placeholder template — treated as
  MAJOR-equivalent baseline (1.0.0), not incremental, since no prior ratified principle set existed.
Modified principles: none renamed (initial fill)
Added sections:
  - Core Principles I–XII (derived verbatim from PLAN.md §2, constraints C1–C12)
  - Core Principles XIII (Scope Discipline) and XIV (Testing Proportionality) — new, not in PLAN.md §2
  - Authoritative Sources & Precedence (Section 2)
  - Development Workflow (Section 3)
  - Governance
Removed sections: none (all placeholder tokens replaced)
Templates requiring updates:
  - .specify/templates/plan-template.md — ✅ no change needed; its "Constitution Check" gate already
    reads this file at run time and needs no hardcoded principle list
  - .specify/templates/spec-template.md — ✅ no change needed; generic and principle-agnostic
  - .specify/templates/tasks-template.md — ✅ no change needed; Tier D exclusion is enforced by
    Principle XIII at generation time, not by template structure
  - .github/agents/*.md, .claude/skills/*/SKILL.md — ✅ no outdated agent-specific references found
Follow-up TODOs:
  - docs/DEBT.md does not exist yet. Principle XIII and PLAN.md §8 require it. Create it before the
    first Definition-of-Done check (PLAN.md §10) using PLAN.md §8's table as the seed content.
-->

# CRM-AZM-Solution Constitution

## Core Principles

### I. Bilingual String Externalization
Every user-facing string MUST be externalized to `ar`/`en` resource files. No hardcoded string
literals in application or template code. **Enforcement point**: lint rule + code review on every
PR touching user-facing code. *(PLAN.md §2, C1)*

### II. Reference-Data Bilingual Completeness
Every reference-data table MUST store both `label_ar` and `label_en`, both `NOT NULL`. A migration
introducing a reference table without both columns MUST be rejected. **Enforcement point**:
migration-level `NOT NULL` constraint. *(PLAN.md §2, C2)*

### III. Structural RTL/LTR Parity
**Enforcement point**: Tailwind configuration established in batch 4a. A scoped grep over
frontend source only (`frontend/**/*.{ts,tsx,css}`) for `\b(ml|mr|pl|pr)-` and `\b(left|right)-`
MUST return only lines carrying an inline `rtl-exempt:` justification comment.

Inherently-LTR content — reference numbers, email addresses, phone numbers, IBANs, URLs,
code — MUST be wrapped in a shared `<LtrText>` component that sets `dir="ltr"` locally.
Forcing direction through that component is correct; using `text-left`/`text-right` to
repair a layout is a violation.

### IV. Universal Tenant Attribution
Every table MUST carry the tenant columns dictated by its scoping pattern, as assigned in
PLAN.md §4.1. That assignment is exhaustive and authoritative; tables assigned S4 or S6 MUST
NOT carry `branch_id` or `department_id`. **Enforcement point**: migration schema convention
plus the shared base model; adding a table requires assigning it a pattern in PLAN.md §4.1.

### V. Repository-Layer Tenant Scoping
Tenant scoping MUST be applied inside the repository layer and MUST NEVER be left to the caller.
**Enforcement point**: the `ScopedRepository` base class is the only construct permitted to build
tenant-scoped queries — services and route handlers never add their own branch/department filter.
*(PLAN.md §2, C5)*

### VI. Immutable Event & Audit Trails
`ticket_events` and `audit_logs` MUST be insert-only. No `UPDATE` or `DELETE` path may exist at any
layer. **Enforcement point**: database role permissions revoke `UPDATE`/`DELETE` grants, backed by
a trigger. *(PLAN.md §2, C6)*

### VII. Atomic Audit Writes
Every audit row MUST be written in the same database transaction as the mutation it records; a
rolled-back transaction MUST leave no audit row. **Enforcement point**: a service-layer decorator
wraps every mutating service method. *(PLAN.md §2, C7)*

### VIII. Single AI Gateway
Every LLM or embedding call MUST route through the LiteLLM wrapper. No vendor SDK may be imported
anywhere in application code. **Enforcement point**: import lint rule scanning for vendor SDK
imports. *(PLAN.md §2, C8)*

### IX. Deterministic AI Degradation
**Enforcement point**: a per-feature acceptance criterion, verified two ways — pointing
`LITELLM_API_BASE` at an unreachable endpoint, and disconnecting the host from the network
entirely (stack.md rev 2: generative inference is remote, embeddings are local CPU).

### X. Service-Layer Permission Enforcement
Permissions MUST be checked in service code. UI-level hiding of controls is cosmetic only and
confers no security guarantee. **Enforcement point**: a service-layer guard decorator on every
mutating method, declaring its required permission. *(PLAN.md §2, C10)*

### XI. Data-Driven Status Transitions
Status transition legality MUST be encoded as rows in the `status_transitions` table, never as
hardcoded conditionals. A change to legal transitions is a data change, not a code change.
**Enforcement point**: the transition service consults `status_transitions` exclusively.
*(PLAN.md §2, C11)*

### XII. Stateless SLA Derivation
SLA state MUST be derived from stored timestamps and MUST be correct after a full container
restart. No in-memory timers may hold SLA state. **Enforcement point**: SLA due dates and breach
state are computed at query time from `created_at`, policy, and `sla_paused_ms` (PLAN.md §5 F05).
*(PLAN.md §2, C12)*

### XIII. Scope Discipline
Tier D capabilities (PLAN.md §3) are specified with acceptance criteria and accommodated in the
data model as reserved fields or tables, but generate no implementation tasks this sprint. Any
shortcut taken to fit the 48-hour budget MUST be recorded in `docs/DEBT.md` with an explicit
repayment trigger. An undocumented shortcut is a violation, not a neutral omission — the distinction
between deliberate debt and scope creep is whether it is written down. **Enforcement point**:
`/speckit.tasks` MUST refuse to emit implementation tasks for Tier D items; `docs/DEBT.md` is
checked against PLAN.md §8 as part of the Definition of Done (PLAN.md §10).

### XIV. Testing Proportionality
Business rules with branching logic — status transition legality, permission checks, SLA
computation, tenant scoping — MUST have tests. CRUD passthroughs MUST NOT be required to carry
tests; writing them anyway is unnecessary weight, not extra safety. AI features are validated
against a bilingual golden dataset (20 tickets, scored by script — PLAN.md §5 F07), not unit tests.
**Enforcement point**: code review rejects both untested branching logic and superfluous tests
wrapped around simple CRUD passthroughs; the golden-set score is recorded per its acceptance
criterion.

## Authoritative Sources & Precedence

`PLAN.md` is the single source of truth for scope, domain model, and business rules.
`docs/architecture/stack.md` is the single source of truth for technology and version choices. If
either of these and a generated artifact (spec, plan, tasks) disagree, the source document wins and
the artifact is regenerated — never patched around the disagreement. A dependency listed under
stack.md's "Explicitly not in this stack" MUST NOT be introduced without a justification entry in
`research.md`.

## Development Workflow

Delivery proceeds in the nine batches defined in PLAN.md §6 (4a–4i). Each batch has its own gate
condition that MUST be demonstrably true — not merely believed true — before the next batch starts
(e.g., "docker compose restart then re-query: every breach state is identical"). Commit and `/clear`
between every batch; context is not carried forward informally across a batch boundary. The
Definition of Done (PLAN.md §10) is the release checklist for the sprint, and it is not satisfied
until `docs/DEBT.md` matches PLAN.md §8.

## Governance

This constitution supersedes ad hoc practice. Principles I–XII are structural per PLAN.md §2:
violating one requires a schema or architecture rewrite, and MUST NOT be worked around with a
patch. Principle XIII is the boundary between deliberate 48-hour debt and silent scope creep.
Principle XIV keeps test effort proportional to actual branching risk instead of uniform coverage
theater.

**Amendment procedure**: a change to a PLAN.md §2 constraint (C1–C12) MUST be made in PLAN.md
first, then reflected here, then propagated to any spec, plan, or tasks artifact it affects. A new
principle not sourced from PLAN.md §2 (as with XIII and XIV) is added directly here and justified
in the amendment's Sync Impact Report.

**Versioning policy** (semantic versioning of this document):
- **MAJOR** — a principle is removed or redefined in a backward-incompatible way.
- **MINOR** — a principle is added, or existing guidance is materially expanded.
- **PATCH** — wording, clarification, or typo fixes with no semantic change.

**Compliance review**: every `/speckit.plan` Constitution Check gate and every PR is checked
against these principles before merge. A violation is resolved by either fixing the work, recording
a justification in that plan's Complexity Tracking table, or — for Tier D scope only — an entry in
`docs/DEBT.md` per Principle XIII.

**Version**: 1.2.0 | **Ratified**: 2026-08-25 | **Last Amended**: 2026-08-25

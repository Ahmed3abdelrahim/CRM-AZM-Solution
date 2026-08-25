# Spec Kit Prompts — Pointer Style

Because `PLAN.md` is the source of truth, every command is a short pointer. This supersedes the long-form prompts in `SPECKIT-PROMPTS.md` — keep that file only as a reference for what the pointers resolve to.

**Before starting:** `/model opus`. Enter plan mode with `Shift+Tab` twice before §3 and §4.

---

## §1 — Constitution

```
/speckit.constitution Read PLAN.md in the repository root. This is a bilingual Arabic/English customer support CRM built on-premise with Docker

Derive the constitution from PLAN.md section 2 (Non-Negotiable Constraints C1 through C12). Each constraint becomes a principle with its enforcement point stated explicitly.

Add two principles not in that table:

SCOPE DISCIPLINE — Tier D capabilities defined in PLAN.md section 3 are specified with acceptance criteria and accommodated in the data model, but generate no implementation tasks. Shortcuts taken for the timeline are recorded in docs/DEBT.md with their repayment trigger. Undocumented shortcuts are violations.

TESTING PROPORTIONALITY — Business rules with branching logic require tests: status transition legality, permission checks, SLA computation, tenant scoping. CRUD passthroughs do not. AI features are validated against a bilingual golden dataset, not unit tests.

Calibrate MVP. Do not mandate testcontainers, CI gates, or air-gap vendoring — those are debt items, not principles.
```

---

## §2 — Specify

```
/speckit.specify Read PLAN.md in the repository root and produce a complete product specification from it.

Treat the twelve feature areas F01 through F12 in PLAN.md section 5 as ONE integrated product, not twelve independent features. Specify all twelve. The tier markers control what gets implemented, not what gets specified.

For every feature: carry across its rules, its API surface, and its acceptance criteria as testable user stories. Preserve the tier marker on every requirement.

Tier D requirements must appear with full acceptance criteria and must be accommodated by the data model, so implementing them later is an extension rather than a rewrite. They must not generate implementation tasks.

Apply PLAN.md section 2 constraints and section 12 platform requirements to every feature — they are cross-cutting, not standalone.

Describe behavior and outcomes only. No database engines, frameworks, or API implementation shapes; those belong in the plan. Flag anything PLAN.md leaves ambiguous as [NEEDS CLARIFICATION] rather than guessing.
```

Then `/speckit.clarify` **twice**. Read `spec.md` end to end before continuing.

---

## §3 — Plan

```
/speckit.plan ultrathink

Follow docs/architecture/stack.md exactly. Introduce no dependency not listed there without recording the justification in research.md.

Build data-model.md directly from PLAN.md section 4. Every entity, every field, every constraint listed there is binding. Add indexes and foreign keys as needed but do not remove or rename what is specified.

Seed the status_transitions table from PLAN.md section 4.3. The workflow engine is that table — no hardcoded enums or match statements on status.

Enforce every constraint in PLAN.md section 2 at the layer named in its enforcement column.

The channel abstraction in F03 is a single interface with a normalized message shape. The email adapter implements it; WhatsApp, SMS, and live chat are declared and raise NotImplementedError. Adding a channel later must require zero changes to ticket creation logic.

Accommodate Tier D features in the schema — reserved columns, tables, or enum values — but produce no implementation design for them. The csat_score and csat_comment columns on tickets are examples.

Business logic in service classes. Route handlers validate, delegate, serialize.

Deliver: research.md with every technology decision and every Tier D accommodation; data-model.md complete; contracts/ with OpenAPI for all Tier M and Tier S endpoints; quickstart.md from docker compose up through seeded demo.
```

**Stop and read `data-model.md` against PLAN.md §4 field by field.** Once you proceed, changing it invalidates the task list.

---

## §4 — Tasks

```
/speckit.tasks Generate tasks for Tier M and Tier S requirements only. No tasks for anything marked Tier D.

Use the batch structure in PLAN.md section 6 exactly — batches 4a through 4i, in that order. Order tasks by dependency within each batch and mark which can run in parallel.

Each batch must end with the verification step named in PLAN.md section 6's gate column, expressed as something checkable without reading code.

Include the seed data in PLAN.md section 7 as tasks in batch 4i.
```

Then `/speckit.analyze`. Manually delete any Tier D task that leaked through.

---

## §5 — Implement

One batch per invocation. Never the whole list.

```
/speckit.implement Implement batch 4a only, as defined in PLAN.md section 6. Stop when every 4a task is complete and its gate passes. Do not begin 4b.
```

Between batches:

```
git add -A && git commit -m "batch 4a: infrastructure"
```

then `/clear`.

---

## §6 — Recovery

**Drift from the plan:**
```
Stop. Re-read PLAN.md sections 2 and 4, and .specify/memory/constitution.md. List every place the code you just wrote violates a constraint or diverges from the specified data model, then fix them. Add no new functionality.
```

**Behind schedule at the Day 1 gate:**
```
We are behind. Re-scope: drop all Tier S requirements from tasks.md. Defer batches 4g and 4i. Concentrate remaining effort on 4d, 4e, and 4h so the core ticket journey and the AI features are complete and demonstrable. Record what was cut in docs/DEBT.md.
```

**Entity model needs to change after §3:**
```
The entity model requires a change: <describe>. Assess the blast radius across PLAN.md section 4, data-model.md, contracts/, and tasks.md before editing anything. If more than three tasks are affected, update PLAN.md first and re-run /speckit.tasks rather than patching.
```

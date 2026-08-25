# Quickstart: Bilingual Support CRM — Core Product

Validates the sprint end-to-end, from a clean checkout to a demonstrable, seeded system, against
PLAN.md §10's Definition of Done. This is a run/validation guide — implementation code lives in
`backend/`/`frontend/` once built, not here.

## Prerequisites

- Docker + Docker Compose
- A configured LLM endpoint reachable from the host (`LITELLM_API_BASE`, `LITELLM_API_KEY`,
  `LITELLM_MODEL_CHAT`, `LITELLM_MODEL_CLASSIFY` — see `docs/architecture/stack.md` §AI layer).
  The system must remain fully usable without it (Scenario 6 below) — you do not need it for the
  first five scenarios.
- ≥16 GB RAM if using the `bge-m3` embedding path (`data-model.md` Research A1); otherwise the
  384-dim `e5-small` path, chosen *before* running the migration in Step 2.

## 1. Bring the stack up

```bash
docker compose up -d
```

**Expected**: PostgreSQL 16, Redis 7, MinIO, the FastAPI backend, the ARQ worker, and the Next.js
frontend all report healthy. `GET /api/v1/health` returns `{"status": "ok", "database": "ok",
"redis": "ok"}`.

## 2. Apply migrations

```bash
docker compose exec backend alembic upgrade head
```

**Expected**: every table in `data-model.md` §1 exists; `\d ticket_events` (via `psql`) shows no
`UPDATE`/`DELETE` grant for the application role (Principle VI); `pgvector`/`pg_trgm` extensions
are enabled.

## 3. Seed

```bash
docker compose exec backend python -m app.seed.seed
```

Idempotent — safe to re-run. Produces PLAN.md §7's exact seed set: 2 branches (different
timezones/business hours), 3 departments, 5 users across all four roles, 20 bilingual customers,
40 tickets across every status/priority/channel (some pre-breaching), 10 fully bilingual KB
articles, a 3-level category tree, 4 priorities, 7 statuses with the full `status_transitions`
table (`data-model.md` §4), 3 SLA policies, 8 quick replies, 2 `channel_configs` rows (one per
department), and the seeded permission set (`data-model.md` §5) — including `audit.read` and
`report.cross_branch` granted to the seeded `admin` user, per PLAN.md §7.

**Expected**: running the command twice produces identical row counts both times.

## 4. Validate the golden journey (spec.md Story 1–5, PLAN.md §1.2)

1. Log in as the seeded `admin` (`POST /auth/login`) and as a seeded `agent`.
2. As the agent, create a customer with an **Arabic** full name (`POST /customers`), then search
   for them using a 3-character Arabic substring of that name (`GET /customers?q=...`).
   **Expected**: the customer is returned (FR-012).
3. Raise a ticket for that customer in Arabic (`POST /tickets`, `source_locale: "ar"`).
   **Expected**: `ai_suggested_category_id` populates asynchronously within a few seconds (via the
   `categorization_job`) without having blocked the creation response (FR-049).
4. Attempt an illegal status change, e.g. `new` → `resolved` directly (`POST /tickets/{id}/status`).
   **Expected**: HTTP 422, `IllegalTransitionError` naming the current status and the permitted
   targets, localized to the caller's `Accept-Language` (FR-017).
5. Drive the ticket through a legal path to `closed` (`new → open → in_progress → resolved →
   closed`), adding a customer-visible reply along the way.
   **Expected**: `first_response_at` is stamped once, on that reply, and never changes after
   (FR-021). `GET /tickets/{id}/events` shows every step, in order, each attributed to the actor
   who performed it (FR-020).
6. Reopen the closed ticket as the `agent` (who does not hold `ticket.reopen` by default seed
   data) — expect 403 — then as the `lead` (who does) — expect success, with `reopened_count`
   incremented (FR-018).

## 5. Validate tenant scoping (spec.md Story 12, Platform-Wide Requirements)

1. As an `agent` scoped to branch A / department 1, `GET /tickets`.
   **Expected**: only tickets in branch A / department 1 (plus S2-scoped tickets from a
   department-`NULL` category/status configuration, per `data-model.md` §0.7) are returned.
2. As the same agent, attempt `GET /tickets/{id}` for a ticket in branch B.
   **Expected**: not found — no cross-branch leak.
3. As `admin` with `report.cross_branch`, `GET /reports/tickets-by-status?cross_branch=true`.
   **Expected**: figures span both seeded branches. Repeat as a user without that permission.
   **Expected**: 403 (FR-060).

## 6. Validate AI fallback (spec.md Story 7, PLAN.md F07 acceptance #1–2)

1. Stop the LLM endpoint (or point `LITELLM_API_BASE` at an unreachable address) **and**
   disconnect the host from the network.
2. Exercise all four AI-assisted capabilities: create a ticket (categorization), request a
   summary, request a suggested reply, open a ticket (suggested solution).
   **Expected**: every screen remains fully usable, no error dialogs; categorization leaves
   `ai_suggested_category_id = NULL`; summary shows the first 300 characters of the description;
   the reply composer opens empty; the suggested-solution panel does not render. Every attempted
   call still writes one `llm_calls` row with `fallback_used = true`.
3. Restore connectivity and repeat — all four now return real model output, in the ticket's
   `source_locale` (FR-048).

## 7. Validate SLA statelessness (spec.md Story 5, PLAN.md F05 acceptance #2)

1. Note the computed `sla_breach_state` and due dates for several tickets in various statuses
   (including one parked in `pending_customer`, an SLA-pausing status).
2. `docker compose restart backend`.
3. Re-query the same tickets.
   **Expected**: identical breach states and due dates — nothing was held only in memory
   (Principle XII).
4. Manually trigger `sla_sweep_job` twice in succession.
   **Expected**: at most one new `sla_breached` event per ticket per target — the second run
   writes zero new events (idempotency).

## 8. Validate bilingual KB search (spec.md Story 6, PLAN.md F06 acceptance #1–2, #4)

1. `GET /kb/search?q=<Arabic query>` for a topic covered by a seeded article.
   **Expected**: that article ranks above unrelated ones.
2. `GET /kb/search?q=<English query>` for the same underlying concept.
   **Expected**: the same article, matched via its English body.
3. Stop the embedding service only (leave the reranker/LLM alone).
   **Expected**: search still returns results, via lexical (`pg_trgm`) matching alone (FR-043).

## 9. Validate the channel abstraction (spec.md Story 8, PLAN.md F03 acceptance #1–4)

1. `POST /channels/inbound` with a normalized payload from an unrecognized sender, addressed to a
   configured `channel_configs` identifier.
   **Expected**: a new customer and ticket are created, scoped to that identifier's configured
   branch/department (FR-023a).
2. Repeat, addressed to an identifier with **no** `channel_configs` match.
   **Expected**: the ticket is created under the system default branch/department with
   `needs_triage = true`, and appears in the `Unassigned` dashboard view (FR-023a, FR-026).
3. `POST /channels/inbound` again, this time quoting an existing ticket's `reference_no` in the
   subject, addressed to a *different* branch's configured identifier than that ticket's own
   branch.
   **Expected**: the message appends to the existing ticket (not a new one), and a mismatch is
   recorded on the timeline rather than the append being blocked (FR-023b).

## 10. Definition of Done checklist (PLAN.md §10)

- [ ] `docker compose up` reaches a working, seeded system on a clean machine (Steps 1–3)
- [ ] Full ticket journey completes in Arabic (Step 4)
- [ ] Illegal status transition rejected with a localized reason (Step 4.4)
- [ ] Every mutation produces an audit row in the same transaction — spot-check via
      `SELECT * FROM audit_logs WHERE entity_id = '<id>'` after any admin CRUD action, and confirm
      a forced failure (e.g. a duplicate unique key) leaves none
- [ ] SLA breach state correct after full restart (Step 7)
- [ ] All four AI capabilities respond, and all four degrade gracefully with the model stopped
      (Step 6)
- [ ] Bilingual KB search returns relevant results in both locales (Step 8)
- [ ] OpenAPI at `/docs` and `/openapi.json` covers all Tier M and Tier S endpoints — diff against
      `specs/001-bilingual-support-crm/contracts/openapi.yaml`
- [ ] Codebase grep for direction-specific CSS utilities returns nothing:
      `grep -rE "\b(ml|mr|pl|pr|left|right)-" frontend/` (outside `<LtrText>`-wrapped,
      `rtl-exempt:`-commented lines, per the constitution's Principle III exception)
- [ ] `README.md` documents setup, seed, demo path, and the tier table from PLAN.md §3 (not
      produced by this plan — a Phase 2/implementation deliverable)
- [ ] `docs/DEBT.md` matches PLAN.md §8 (not produced by this plan — create before this checklist
      is run for real, per the constitution's Principle XIII)

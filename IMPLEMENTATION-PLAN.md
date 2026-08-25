# CRM-AZM-Solution — Implementation Plan

**Project:** Bilingual (AR/EN) Customer Support CRM
**Delivery model:** Spec-Driven Development via GitHub Spec Kit + Claude Code
**Deployment target:** On-premise, fully containerized (Docker)
**Time budget:** 2 days
**Source requirements:** `crm.txt` — 12 feature areas

---

## 0. The Governing Constraint

Two days does not produce a 12-area production CRM. It produces a **demonstrable vertical slice that proves the architecture and covers the highest-visibility requirements from every tier**.

This document therefore does two jobs at once:

1. **Preserve all 12 feature areas** from the source document as tracked requirements, so nothing is silently dropped and the specification stays complete.
2. **Tier them ruthlessly** into what gets built in 48 hours vs. what is designed-for but deferred.

A requirement being deferred is not a requirement being deleted. Deferred items appear in `spec.md` with acceptance criteria and appear in the data model as reserved fields or tables, so Phase 2+ is an extension rather than a rewrite.

---

## 1. Scope Tiering

Every capability in `crm.txt` is assigned exactly one tier.

### Tier M — MVP (built in 48 hours)

| Source area | What ships |
|---|---|
| 10. Security & Administration | JWT auth, 3 roles (admin / agent / customer), service-layer permission checks, append-only audit table |
| 1. Customer Management | Customer CRUD, multiple contact methods, notes, attachments, interaction history view |
| 2. Ticket Management | Ticket CRUD, reference number, category tree, priorities, assignment, configurable status lifecycle, immutable timeline |
| 4. Agent Dashboard | My tickets, team queue, filters, quick replies, internal notes |
| 5. SLA & Automation | SLA policy per category+priority, first-response and resolution targets, breach state computed from stored timestamps, auto-assignment (round-robin) |
| 6. Knowledge Base | Article CRUD, AR/EN content, full-text + semantic search |
| 7. AI Features | Auto-categorization, ticket summary, suggested reply, suggested KB solution — all via LiteLLM |
| 12. Platform | AR/EN i18n with true RTL, responsive web, `branch_id` + `department_id` on every domain table |

### Tier S — Scaffolded (contract + stub, not functional)

| Source area | What ships |
|---|---|
| 3. Communication Channels | Channel abstraction + `channel` enum on tickets + an inbound webhook endpoint that accepts a normalized payload. **Email adapter only**, polled. WhatsApp / SMS / live chat implement the interface but return `NotImplemented`. |
| 8. Customer Portal | Submit ticket + track by reference number. No portal auth beyond a magic-link stub; no feedback survey. |
| 9. Reports & Management | Three aggregate endpoints (tickets by status, SLA compliance %, per-agent volume) + one dashboard page. No CSAT, no scheduled reports. |
| 11. Integrations | Public OpenAPI contract published, API-key auth for machine clients. No ERP connector. |

### Tier D — Deferred (specified, not built)

- Live chat transport (WebSocket) and SMS gateway
- WhatsApp Business API adapter
- AI chatbot (conversational RAG over KB) — the *retrieval* half ships in Tier M as "suggested solutions"; the conversational loop does not
- CSAT collection and reporting
- Custom branding per branch
- ERP / external system connectors
- Full audit-log browsing UI (the table is written from day one; only the reader is deferred)

**Rule for the agent:** Tier D features must not appear in `tasks.md`. They must appear in `spec.md` and must be accommodated by `data-model.md`.

---

## 2. Dependency Graph

```
                 Security & Admin (roles, permissions, audit)
                                │
                    ┌───────────┴───────────┐
                    │                       │
            Customer Management      Category / Priority
                    │                  configuration
                    └───────────┬───────────┘
                                │
                        Ticket Management
                    (lifecycle, assignment, history)
                                │
        ┌───────────────┬───────┴───────┬────────────────┐
        │               │               │                │
  Agent Dashboard  SLA & Automation  Channels       Customer Portal
        │               │           (inbound)             │
        └───────┬───────┘                                 │
                │                                         │
            Reports  ◄───────────────────────────────────┘

     Knowledge Base ──► AI Features ──► Suggested solutions / Chatbot (Tier D)

     Platform (i18n, RTL, multi-branch, responsive) — CROSS-CUTTING, not a phase
```

**Critical reading:** *Platform* is not a phase. AR/EN and branch scoping are structural. Building them "at the end" means retrofitting every table, every query, and every component. They are constitution-level constraints enforced from commit one.

---

## 3. Architecture

### 3.1 Stack

| Layer | Technology | Rationale under the 48h constraint |
|---|---|---|
| API | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, Pydantic v2 | Single language across API and AI services |
| DB | PostgreSQL 16 + `pgvector` + `pg_trgm` | One datastore for OLTP, full-text, and KB vectors. No second system to operate. |
| Cache / jobs | Redis 7 + ARQ | SLA sweeps, auto-assignment, email polling |
| LLM gateway | LiteLLM | Every model call goes through it — enables self-hosted → cloud migration by config |
| Serving | vLLM (OpenAI-compatible) | Self-hosted now |
| Models | Qwen3 (chat/assist), Qwen3-4B (classification), BGE-M3 (embeddings) | Strong Arabic across all three |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui + next-intl | RTL via CSS logical properties |
| Auth | FastAPI JWT + RBAC (**not** Keycloak for MVP) | Keycloak is correct long-term; it costs half a day to wire. Deferred. |
| Files | MinIO | S3 API on-prem |
| Observability | Langfuse (LLM traces) + structured JSON logs | Full OTel/Prometheus deferred |
| Runtime | Docker Compose | On-prem, single-host |

### 3.2 Deviations from the production target (explicit debt)

These are conscious 48-hour decisions. Each is logged so it is repaid, not forgotten.

| Decision | Production target | Repayment trigger |
|---|---|---|
| JWT in-app auth | Keycloak SSO + AD | Before multi-tenant rollout |
| No testcontainers | Integration tests on real PG/Redis | Before first external user |
| SLA computed on read | Background timer + escalation worker | Phase 2 |
| Single Compose host | Kubernetes | Before HA requirement |
| No OTel tracing | Full distributed tracing | Phase 2 |
| Seeded demo data | Migration-driven reference data | Before UAT |

### 3.3 Core entity model (must be settled before any code)

```
Branch ──< Department ──< User ──< Role (M:N via UserRole)
                              │
Customer ──< ContactMethod    │
    │                         │
    └──< Ticket >─────────────┘  (requester, assignee)
           │
           ├──< TicketEvent      (append-only timeline)
           ├──< Attachment
           ├──> Category (self-referencing tree, AR/EN labels)
           ├──> Priority (AR/EN labels)
           ├──> SLAPolicy (derived from category + priority)
           └──> Channel (enum: web|email|whatsapp|sms|chat|portal)

KBArticle ──< KBArticleVersion   (AR/EN body, embedding vector)

AuditLog   (actor, action, entity_type, entity_id, before, after, correlation_id)
```

**Invariants enforced at the data layer, not the caller:**

- Every domain table carries `branch_id` and `department_id`.
- `TicketEvent` and `AuditLog` are INSERT-only. No UPDATE or DELETE grant.
- Audit rows are written in the same transaction as the mutation that caused them.
- Every user-facing label column exists as `label_ar` and `label_en`. Neither is nullable.

---

## 4. Execution Phases

### Phase 0 — Governance (60 min)

- `/speckit.constitution` with the 48-hour-calibrated principles (see `SPECKIT-PROMPTS.md`)
- Read and tighten `.specify/memory/constitution.md`
- Commit `docs/architecture/stack.md`

**Exit:** constitution committed; no code.

### Phase 1 — Specification (90 min)

- `/speckit.specify` with the full 12-area product prompt
- Read `spec.md` end to end
- `/speckit.clarify` twice — different gaps surface on each pass
- Verify every Tier M item has testable acceptance criteria and every Tier D item is present but marked deferred

**Exit:** `spec.md` reviewed and free of `[NEEDS CLARIFICATION]` markers on Tier M items.

### Phase 2 — Design (90 min)

- `/speckit.plan` with `ultrathink`
- Read `data-model.md` line by line — **this is the highest-leverage artifact in the project**
- Confirm `research.md` records the Tier S/D accommodations
- Confirm `contracts/` has OpenAPI for all Tier M + Tier S endpoints

**Exit:** entity model frozen. Changing it after this point invalidates the task list.

### Phase 3 — Task generation (45 min)

- `/speckit.tasks` with explicit tiering instruction
- `/speckit.analyze` to catch spec↔plan↔tasks drift
- Manually strip any Tier D task that leaked in

**Exit:** `tasks.md` with tasks grouped by phase and ordered by dependency.

### Phase 4 — Implementation (remainder)

Run `/speckit.implement` in **bounded batches**, never as one invocation:

| Batch | Content | Gate before proceeding |
|---|---|---|
| 4a | Docker Compose, PG + Redis + MinIO, Alembic baseline, health endpoints | `docker compose up` clean; migrations apply |
| 4b | Auth, users, roles, permissions, audit writer | Login works; audit row appears on every mutation |
| 4c | Customers, contact methods, notes, attachments | CRUD via API + Arabic names render correctly |
| 4d | Categories, priorities, tickets, lifecycle, assignment, timeline | Full ticket journey to closure; illegal transition rejected |
| 4e | Agent dashboard, quick replies, i18n + RTL shell | Interface fully usable in Arabic |
| 4f | SLA policy + breach computation + auto-assignment | Breach flag correct across a restart |
| 4g | Knowledge base + search + embeddings | AR and EN search both return relevant articles |
| 4h | AI endpoints via LiteLLM (categorize, summarize, suggest reply, suggest solution) | Each degrades gracefully when the model is unreachable |
| 4i | Portal submit/track, reports endpoints, inbound webhook stub | Demo path complete |

**After every batch:** commit, run the gate, `/clear` context. Do not carry batch 4b's context into 4g.

---

## 5. 48-Hour Schedule

### Day 1

| Time | Activity | Output |
|---|---|---|
| 09:00–10:00 | Phase 0 — constitution | `constitution.md`, `stack.md` |
| 10:00–11:30 | Phase 1 — specify + clarify ×2 | `spec.md` |
| 11:30–13:00 | Phase 2 — plan (`ultrathink`) | `plan.md`, `data-model.md`, `contracts/` |
| 13:00–13:45 | Phase 3 — tasks + analyze | `tasks.md` |
| 13:45–15:00 | Batch 4a + 4b | Infra + auth running |
| 15:00–17:00 | Batch 4c + 4d | Customers + tickets working |
| 17:00–18:00 | Batch 4e | Agent dashboard, Arabic UI |

**Day 1 exit gate:** an agent can log in, create a customer, raise a ticket, assign it, close it, and read the timeline — in Arabic. If this is not true by end of Day 1, **cut Tier S entirely** on Day 2 and deepen Tier M instead.

### Day 2

| Time | Activity | Output |
|---|---|---|
| 09:00–10:30 | Batch 4f | SLA + auto-assignment |
| 10:30–12:00 | Batch 4g | Knowledge base + search |
| 12:00–14:00 | Batch 4h | AI features |
| 14:00–15:30 | Batch 4i | Portal, reports, webhook |
| 15:30–16:30 | Seed data, demo script, README | Reproducible demo |
| 16:30–17:30 | Buffer — **do not schedule work here** | Absorbs one failed batch |
| 17:30–18:00 | Dry run of the demo | — |

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GPU for self-hosted vLLM not available on-prem in time | High | Blocks Tier M AI | LiteLLM makes the provider a config value. Point at a cloud endpoint for the demo; the code does not change. |
| Entity model churns after Phase 2 | Medium | Invalidates `tasks.md` | Freeze `data-model.md` explicitly. Any change requires re-running `/speckit.tasks`. |
| RTL retrofitted late | Medium | Multi-hour rework | Constitution principle. Enforced in batch 4a's Tailwind config, not batch 4e. |
| `/speckit.implement` drifts on a large batch | High | Silent architectural violation | Bounded batches + `/clear` + gate check between each. |
| Arabic full-text search quality poor | Medium | Weak KB demo | `pg_trgm` fallback plus BGE-M3 semantic search; do not rely on PG's Arabic stemmer alone. |
| Scope creep from stakeholder mid-sprint | High | Misses Day 1 gate | This tiering table is the agreed contract. Changes go to Phase 2 of the project, not this sprint. |

---

## 7. Definition of Done (48-hour deliverable)

- [ ] `docker compose up` brings the full stack up on a clean machine
- [ ] Seeded with 2 branches, 3 departments, 5 users, 20 customers, 40 tickets, 10 KB articles — bilingual content
- [ ] An agent completes the full ticket journey end to end in Arabic
- [ ] An illegal status transition is rejected with a localized reason
- [ ] Every mutation produces an audit row in the same transaction
- [ ] SLA breach state is correct after `docker compose restart`
- [ ] All four AI endpoints respond, and all four degrade gracefully with the model stopped
- [ ] OpenAPI served at `/docs`, covering Tier M + Tier S
- [ ] `README.md` documents setup, seed, demo path, and the deferred-scope table from §1
- [ ] `docs/DEBT.md` lists every item from §3.2

---

## 8. Command Sequence (reference)

```
# once
/speckit.constitution   <see SPECKIT-PROMPTS.md §1>
/speckit.specify        <see SPECKIT-PROMPTS.md §2>
/speckit.clarify
/speckit.clarify
/speckit.plan           <see SPECKIT-PROMPTS.md §3>
/speckit.tasks          <see SPECKIT-PROMPTS.md §4>
/speckit.analyze

# repeated per batch, with /clear between
/speckit.implement      <see SPECKIT-PROMPTS.md §5>
```

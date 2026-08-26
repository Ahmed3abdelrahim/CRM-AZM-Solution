# Deliberate Debt Register

Required by Constitution Principle XIII. Every entry is a conscious trade made to fit the 48-hour budget, with an explicit repayment trigger.

**This file is for architectural shortcuts, not deferred scope.** Features not being built are Tier D in `PLAN.md` §3 and belong there, not here. The distinction matters: Tier D is *functionality we chose not to build yet*; debt is *functionality we built the cheap way*.

An undocumented shortcut is a violation. If you take one during implementation, add a row before the batch commit.

---

## Register

| # | Shortcut taken | Production target | Repayment trigger | Est. effort |
|---|---|---|---|---|
| D01 | In-app JWT auth (access 15 min / refresh 7 days), Argon2 hashing, roles in local tables | Keycloak with SSO and Active Directory federation | Before multi-tenant rollout or first external customer | 1–2 days |
| D02 | SLA due dates and breach state derived at query time from `created_at`, policy, and `sla_paused_ms` | Background escalation worker maintaining materialized SLA state | Phase 2, or when ticket volume makes per-query derivation measurable in p95 latency | 1 day |
| D03 | No testcontainers; tests run against whatever PG/Redis the developer has up | Integration tests provisioning ephemeral PG and Redis per run | Before first external user, or the first CI pipeline | 0.5 day |
| D04 | Structured JSON logs with correlation ids; no distributed tracing | Full OpenTelemetry instrumentation exporting to Prometheus/Grafana | Phase 2. Correlation ids exist from commit one specifically so this does not require touching every call site | 1 day |
| D05 | Single-host Docker Compose | Kubernetes with per-service scaling and rolling deploys | Before any high-availability requirement | 2–3 days |
| D06 | Email ingestion by IMAP polling on an ARQ schedule | Push/webhook ingestion with retry and dead-letter queue | When inbound volume makes polling latency visible to customers | 0.5 day |
| D07 | Generative inference on a remote Qwen3 endpoint (OpenRouter/Together) via LiteLLM | Self-hosted vLLM serving Qwen3 on-premise | GPU hardware available on-prem. Model family deliberately matched now so prompts transfer unchanged — this is four environment variables, not a rewrite | 0.5 day |
| D08 | `llm_calls` table capturing model, prompt version, token counts, latency, and fallback usage | Langfuse for prompt versioning, trace trees, and evaluation runs | When the stack moves to a server with capacity for Langfuse's Postgres + ClickHouse + S3 dependencies | 0.5 day |
| D09 | Reranking behind a feature flag, default off; fused RRF order returned when disabled | `bge-reranker-v2-m3` always on | GPU available, or when retrieval quality measurably limits suggested-solution accuracy | 0.25 day |
| D10 | Audit rows written from day one, but no browsing interface | Searchable, filterable audit log UI with export | Before any compliance review. The data is complete — only the reader is missing | 0.5 day |
| D11 | i18n enforcement is a grep check, not an ESLint rule | Proper ESLint rule integrated in CI | Phase 2 |
| D12 | Admin configuration is API-only; no UI for branches, departments, users, roles, taxonomy, SLA policies, quick replies, or teams | Admin UI screens under `frontend/app/[locale]/(agent)/admin/`, one per `admin_config.py` router group | Before handover to non-technical administrators | 1–2 days |
---

## Standing constraints these shortcuts must not violate

Debt is acceptable where it can be repaid by adding code. It is **not** acceptable where repayment would require a schema migration across live data or a rewrite of a structural boundary. Specifically, no shortcut may compromise:

- Tenant columns present on every tenant-scoped table (Principle IV) — retrofitting these across populated tables is a migration nightmare
- Insert-only `ticket_events` and `audit_logs` (Principle VI) — history that was mutable cannot be made trustworthy retroactively
- The LiteLLM gateway boundary (Principle VIII) — this boundary is precisely what makes D07 a config change instead of a rewrite
- Bilingual columns on reference data (Principle II) — backfilling Arabic labels after the fact means re-deriving them by hand
- Data-driven status transitions (Principle XI) — hardcoding the lifecycle turns every future workflow variation into a code change

If a proposed shortcut touches any of the above, it is not debt. It is a design error, and it must be raised rather than logged.

---

## Review

This register is checked against `PLAN.md` §8 as part of the Definition of Done (`PLAN.md` §10). The sprint is not complete until the two agree.

**Last updated**: 2026-08-25 · **Constitution version**: 1.0.0

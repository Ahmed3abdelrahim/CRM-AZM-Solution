# Feature Specification: Audit Log Interface

**Feature Branch**: `006-audit-log-ui`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D and §8 D10; completes PLAN.md §5 F10
**Depends on**: 001 (`audit_logs` written from day one)

## Why this is small

The hard part is done. Sprint 001 wrote every audit row transactionally from the first commit
under Principle VII, with `before`/`after` JSONB and correlation ids. **This feature is a reader.**
No new writes, no backfill, no migration beyond indexes.

## Requirements

- **FR-1** An administrator MUST be able to search audit records by actor, action, entity type,
  entity id, date range, and correlation id.
- **FR-2** A record MUST render `before` and `after` as a readable field-level diff, not raw JSON.
- **FR-3** All records sharing a correlation id MUST be viewable together as one causal chain —
  this is what makes "what did that one request actually do" answerable.
- **FR-4** From any ticket or customer, an administrator MUST be able to jump to that entity's
  audit history.
- **FR-5** Results MUST be exportable to CSV, with the export itself written to `audit_logs`.
- **FR-6** Access MUST require a distinct `audit.read` permission, not merely the admin role.
- **FR-7** The interface MUST be read-only. No mutation path may exist, consistent with
  Principle VI.
- **FR-8** Retention policy MUST be configurable, with archival rather than deletion.

## New Indexes

`(actor_id, created_at)`, `(entity_type, entity_id, created_at)`, `(correlation_id)`

## Acceptance Criteria

1. Filtering by correlation id returns every record from one request in causal order.
2. The diff view shows only changed fields, with Arabic values rendered RTL.
3. A user with the admin role but without `audit.read` receives 403.
4. No endpoint in this feature accepts a mutation verb.
5. A CSV export writes its own audit row naming the exporter and the filter used.

## Out of Scope

Real-time streaming, anomaly detection, SIEM forwarding, tamper-evident hash chaining.

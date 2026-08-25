# Feature Specification: Customer Satisfaction & Feedback

**Feature Branch**: `005-csat-feedback`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D; completes PLAN.md §5 F08 and F09
**Depends on**: 001 (tickets, portal, reports)

## Why this is small

Sprint 001 reserved the columns. This feature is a survey, a portal form, and a report.

| Already reserved in 001 | Location |
|---|---|
| `csat_score INT NULL` | `tickets` |
| `csat_comment TEXT NULL` | `tickets` |
| Portal history view | F08 |
| Report aggregation pattern | F09 |

## New Schema

- `csat_surveys` — S1 scoped: `ticket_id`, `token` (single-use), `sent_at`, `responded_at`,
  `expires_at`, `channel_sent_via`

## Requirements

- **FR-1** On transition to a terminal status, a survey MUST be dispatched via the ticket's
  originating channel, after a configurable delay.
- **FR-2** The survey MUST be answerable without login, via a single-use token.
- **FR-3** A score (1–5) MUST be required; a comment MUST be optional.
- **FR-4** Surveys MUST expire after a configurable window; expired tokens return a localized
  message, not an error.
- **FR-5** One survey per ticket per closure. Reopening and re-closing MAY issue a new one,
  configurable per department.
- **FR-6** Responses MUST populate `tickets.csat_score` and `tickets.csat_comment` and write a
  `ticket_event`.
- **FR-7** CSAT MUST appear in reports by branch, department, agent, and category, with the
  response rate shown alongside the average — an average over 3 responses is not a metric.
- **FR-8** Survey content MUST be bilingual and sent in the customer's `preferred_locale`.

## Acceptance Criteria

1. Closing a ticket dispatches a survey after the configured delay, in the customer's locale.
2. A token works exactly once; the second attempt shows a localized already-answered message.
3. An expired token shows a localized expiry message rather than a 404 or a stack trace.
4. The per-agent CSAT report shows response rate next to average score.

## Out of Scope

NPS, CES, multi-question surveys, sentiment analysis of comments, survey A/B testing.

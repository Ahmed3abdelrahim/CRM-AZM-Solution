# Feature Specification: WhatsApp Channel Adapter

**Feature Branch**: `002-whatsapp-channel`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D; extends PLAN.md §5 F03
**Depends on**: 001-bilingual-support-crm (channel abstraction, `inbound_messages`, identity resolution)

## Why this is small

Sprint 001 built the channel abstraction and left a declared WhatsApp adapter raising
`NotImplementedError`. The following already exist and require **no migration**:

| Already reserved in 001 | Location |
|---|---|
| `channel` enum includes `whatsapp` | `tickets.channel` |
| `contact_methods.kind` includes `whatsapp` | `contact_methods` |
| Landing table for raw payloads | `inbound_messages` |
| Identity resolution by contact value | `ChannelAdapter` interface |
| Branch/department resolution by recipient | `channel_configs` |

This feature implements one interface. Ticket creation logic is not touched — that is the
acceptance test for whether 001's abstraction was correct.

## Requirements

- **FR-1** A WhatsApp Business API (or BSP) webhook MUST be accepted at a dedicated endpoint and
  its payload persisted raw to `inbound_messages` before any processing.
- **FR-2** The adapter MUST implement `ChannelAdapter.normalize(raw) → NormalizedMessage` and
  MUST NOT introduce a second path into ticket creation.
- **FR-3** Sender phone number MUST resolve against `contact_methods` where `kind = 'whatsapp'`;
  no match creates a customer with that contact method.
- **FR-4** Branch and department MUST resolve from `channel_configs` by the receiving WhatsApp
  number, falling back to the system default with `needs_triage` set.
- **FR-5** Media attachments MUST be downloaded and stored via the existing storage interface.
- **FR-6** Outbound replies MUST respect the 24-hour customer-service window; outside it, only
  approved message templates may be sent, and the agent MUST be told why.
- **FR-7** Delivery receipts (sent, delivered, read) MUST be recorded as `ticket_events`.
- **FR-8** Webhook signature MUST be verified; unverified payloads are rejected and logged.

## Acceptance Criteria

1. An inbound WhatsApp message from an unknown number creates a customer and a ticket with
   `channel = 'whatsapp'`.
2. A message from a known number within an open ticket's thread appends a `ticket_event` rather
   than creating a ticket.
3. Zero lines change in the ticket creation service.
4. Replying outside the 24-hour window without a template is blocked with a localized reason.
5. Arabic message bodies round-trip without mojibake or direction loss.

## Out of Scope

Interactive buttons and list messages, WhatsApp Flows, catalogue/commerce messages, group chats.

# Feature Specification: Live Chat & SMS Channels

**Feature Branch**: `004-live-chat-sms`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D; extends PLAN.md §5 F03
**Depends on**: 001 (channel abstraction, agent dashboard)

## Scope

Two channels sharing one prerequisite: real-time transport. SMS is trivial once the adapter
pattern exists; live chat is the substantial half because it introduces WebSockets, presence,
and queueing — infrastructure sprint 001 deliberately avoided.

## New Schema

- `chat_sessions` / `chat_messages` — shared with 003-ai-chatbot; build once
- `agent_presence` — `user_id`, `status` (available/busy/away), `active_chat_count`, `updated_at`

## Requirements — Live Chat

- **FR-1** A visitor MUST be able to open a chat from the portal without authenticating.
- **FR-2** Chats MUST queue when no agent is available, showing position and estimated wait.
- **FR-3** Routing MUST respect branch and department scoping and agent presence.
- **FR-4** An agent MUST handle multiple concurrent chats with a configurable cap.
- **FR-5** Transcripts MUST persist and attach to a ticket on escalation.
- **FR-6** Reconnection after network loss MUST resume the session, not start a new one.
- **FR-7** Typing indicators and read receipts MUST work correctly in RTL layout.

## Requirements — SMS

- **FR-8** Inbound SMS MUST implement `ChannelAdapter` with no change to ticket creation.
- **FR-9** Outbound MUST handle segmentation; Arabic uses UCS-2 at 70 characters per segment,
  and the agent MUST see segment count before sending.
- **FR-10** Delivery receipts MUST be recorded as `ticket_events`.

## Acceptance Criteria

1. A queued visitor sees an accurate position that decrements as agents free up.
2. Killing the visitor's network for 30 seconds and restoring it resumes the same session.
3. An Arabic SMS of 100 characters is correctly reported as 2 segments before sending.
4. Zero lines change in the ticket creation service for the SMS adapter.

## Out of Scope

Video chat, co-browsing, chatbot handoff (that is 003), proactive chat invitations.

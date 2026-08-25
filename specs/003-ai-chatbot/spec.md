# Feature Specification: AI Chatbot

**Feature Branch**: `003-ai-chatbot`
**Status**: Roadmap — not implemented in sprint 001
**Source**: PLAN.md §3 Tier D; completes PLAN.md §5 F07
**Depends on**: 001 (KB embeddings, LiteLLM wrapper, portal), ideally 004 (chat transport)

## Why this is small

Sprint 001 shipped the retrieval half of the chatbot as "suggested solutions". What is missing
is the conversational loop, not the intelligence.

| Already built in 001 | Reused as |
|---|---|
| `kb_article_chunks` with embeddings | Retrieval corpus |
| Hybrid search (trigram + vector + RRF) | Retrieval function |
| LiteLLM wrapper with fallbacks | Generation |
| `llm_calls` telemetry table | Chatbot observability |
| Customer portal | Delivery surface |

## New Schema

- `chat_sessions` — S5 scoped, `customer_id` nullable (anonymous visitors), `locale`,
  `ticket_id` nullable (set on escalation), `started_at`, `ended_at`
- `chat_messages` — S4 via `chat_sessions`, insert-only: `role`, `content`,
  `retrieved_article_ids` (JSONB), `llm_call_id`

## Requirements

- **FR-1** A customer MUST be able to ask a question in Arabic or English and receive an answer
  grounded in published KB articles, with the source articles cited.
- **FR-2** The bot MUST answer in the language the customer used, regardless of which locale
  the source article was written in.
- **FR-3** When retrieval confidence is below threshold, the bot MUST say it does not know and
  offer to open a ticket — it MUST NOT generate an ungrounded answer.
- **FR-4** Escalation MUST create a ticket with `channel = 'chat'`, attaching the full transcript
  as the description and linking `chat_sessions.ticket_id`.
- **FR-5** Conversation history MUST be passed on each turn; the model holds no server-side state.
- **FR-6** Every turn MUST be recorded in `llm_calls` with its prompt version.
- **FR-7** With the LLM endpoint unreachable, the chat widget MUST degrade to a plain ticket
  submission form rather than erroring.

## Acceptance Criteria

1. An Arabic question about a topic covered only by an English article returns a correct Arabic
   answer citing that article.
2. A question with no KB coverage produces a refusal plus an escalation offer, not a fabrication.
3. Escalation produces a ticket whose description contains the full transcript.
4. A bilingual golden set of 30 questions is scored for grounding accuracy and refusal rate.

## Out of Scope

Voice, multi-turn transactional actions (ticket status changes via chat), agent-facing copilot chat.

# Feature Specification: Bilingual Support CRM — Core Product

**Feature Branch**: `001-bilingual-support-crm`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Read PLAN.md in the repository root and produce a complete product
specification from it. Treat the twelve feature areas F01 through F12 in PLAN.md section 5 as ONE
integrated product, not twelve independent features. Specify all twelve. The tier markers control
what gets implemented, not what gets specified. For every feature: carry across its rules, its API
surface, and its acceptance criteria as testable user stories. Preserve the tier marker on every
requirement. Tier D requirements must appear with full acceptance criteria and must be accommodated
by the data model, so implementing them later is an extension rather than a rewrite. They must not
generate implementation tasks. Apply PLAN.md section 2 constraints and section 12 platform
requirements to every feature — they are cross-cutting, not standalone. Describe behavior and
outcomes only. No database engines, frameworks, or API implementation shapes; those belong in the
plan. Flag anything PLAN.md leaves ambiguous as [NEEDS CLARIFICATION] rather than guessing."

**Scope note**: This specification covers the whole product as PLAN.md defines it — one bilingual,
multi-branch, multi-department customer support CRM, described as a single integrated system across
its twelve feature areas (F01–F12). Every requirement below carries the tier marker (**Tier M** —
built this sprint, **Tier S** — contract/stub only, **Tier D** — specified but not built) assigned
to it in PLAN.md §3 and §5. Tier D requirements are written to the same acceptance-criteria standard
as the rest; they intentionally do not generate implementation tasks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Customer Management (Priority: P1) — Tier M

An agent finds or creates the person behind a ticket and can see everything that has ever happened
with them, in either language.

**Why this priority**: Every other journey in the product starts by identifying a customer. Without
this, no ticket can be correctly attributed or scoped.

**Independent Test**: Create a customer record with an Arabic name and a phone number, then search
for them using a partial Arabic name fragment and confirm they are found; separately, confirm their
full history page merges every ticket and every recorded event for them into one timeline.

**Acceptance Scenarios**:

1. **Given** a newly created customer with an Arabic full name, **When** staff search using a
   three-character fragment of that name, **Then** the customer is returned in the results.
2. **Given** a customer with multiple tickets and recorded events, **When** staff open that
   customer's history, **Then** they see a single chronological view merging every ticket and every
   event across all of them.
3. **Given** a customer who has one or more tickets, **When** anyone attempts to permanently delete
   that customer, **Then** no such action is available anywhere in the product — deactivation is the
   only removal path, and it is reversible.
4. **Given** a new customer is being created, **When** the record is saved, **Then** exactly one
   permanent, attributable audit record is produced as part of that same save.
5. **Given** a customer record being created, **When** no contact method is supplied, **Then** the
   save is rejected; **When** more than one contact method is marked primary, **Then** the save is
   rejected.

---

### User Story 2 - Ticket Management (Priority: P1) — Tier M

An agent raises a ticket, moves it through a controlled lifecycle toward resolution, and can always
reconstruct exactly what happened and who did it.

**Why this priority**: The ticket is the core record every other feature attaches to (customer
context, SLA, AI assistance, dashboards, reporting). Nothing else in the product is demonstrable
without it.

**Independent Test**: Create a ticket, attempt an illegal status change and confirm it is rejected
with an explanation, then drive it through a legal path to closure and confirm every step appears,
in order, on the ticket's own timeline.

**Acceptance Scenarios**:

1. **Given** a ticket created with Arabic content, **When** it is opened in the agent workspace or
   the customer portal, **Then** it renders correctly in right-to-left reading order.
2. **Given** a ticket in its initial status, **When** staff attempt to move it directly to a status
   not reachable from the current one, **Then** the change is rejected with an explanation, in the
   requester's own language, of the current status and which statuses are actually reachable.
3. **Given** a closed ticket, **When** a user holding the reopen permission reopens it, **Then** the
   reopen succeeds and the ticket's reopen count increases; **When** a user lacking that permission
   attempts the same action, **Then** it is refused.
4. **Given** a ticket with several recorded actions, **When** its timeline is requested, **Then**
   every mutation appears in order, each attributed to the person who performed it, with no separate
   history to fall out of sync.
5. **Given** any ticket, **When** any path in the product is attempted that would modify or remove an
   existing timeline entry, **Then** no such path exists.

---

### User Story 3 - Security, Permissions & Administration (Priority: P1) — Tier M *(audit-trail browsing UI is Tier D)*

An administrator configures who can do what, and every sensitive action leaves a permanent,
tamper-proof record of exactly what changed.

**Why this priority**: Every other story depends on authentication, permission enforcement, and
auditability existing first — it is the foundation the rest of the product is built on, and it is
delivered first in the implementation sequence for that reason.

**Independent Test**: Log in as an agent and call an administrative action directly; confirm it is
refused regardless of what any interface would have shown. Separately, perform any mutating action
and confirm exactly one audit record is produced, then force that action to fail partway through and
confirm no audit record remains.

**Acceptance Scenarios**:

1. **Given** a signed-in agent without administrative permission, **When** they attempt an
   administrative action directly, **Then** it is refused — even if no interface would have offered
   them the control in the first place.
2. **Given** any action that changes data, **When** it completes, **Then** exactly one audit record
   exists capturing both the state before and the state after, as part of that same action.
3. **Given** an action that changes data, **When** the action is rolled back or fails to complete,
   **Then** no audit record for it exists.
4. **Given** an existing audit record, **When** any attempt is made to change or remove it through
   any path, **Then** it fails — audit records are permanent from the moment they are written.
5. **Given** an administrator, **When** they configure branches, departments, users, roles,
   permissions, categories, priorities, statuses, transitions, SLA policies, or pre-written replies,
   **Then** the change takes effect for future activity without any code change.
6. *(Tier D — specified, not built)* **Given** a fully audited system, **When** an administrator
   wants to review the audit trail, **Then** they can browse and search it through the interface
   rather than only knowing it exists. Not implemented this sprint — audit records are captured from
   the first release regardless (Scenario 2), so this adds a viewer, not new data capture.

---

### User Story 4 - Agent Dashboard & Platform Experience (Priority: P1) — Tier M *(personal tasks/reminders is Tier D; custom branding is Tier D)*

An agent's entire working day — queues, filters, in-context customer info, quick replies — is fully
usable in Arabic or English, on any screen size, with no separate "Arabic version" to maintain.

**Why this priority**: This is where every other capability (tickets, SLA, AI suggestions, KB
search) is actually consumed by a human. Bilingual/RTL correctness is validated here, but it governs
every feature in this specification (see the Platform-Wide Requirements below).

**Independent Test**: Switch the interface language to Arabic mid-session and confirm the whole
dashboard flips to right-to-left with no reload and no broken layout, at both a desktop and a
375px-wide viewport; separately, confirm an internal note never appears anywhere a customer can see.

**Acceptance Scenarios**:

1. **Given** an agent viewing their dashboard, **When** they switch the display language to Arabic,
   **Then** the entire dashboard changes to right-to-left layout immediately, with no page reload and
   no broken layout, and switching back is equally immediate.
2. **Given** a ticket with an internal note, **When** that ticket is viewed through any
   customer-facing surface, **Then** the internal note is absent — verified against every
   customer-facing response, not just the primary one.
3. **Given** a set of tickets approaching their SLA deadline, **When** an agent opens the "breaching
   soon" view, **Then** tickets are ordered with the least time remaining first.
4. **Given** any filter combination (status, priority, category, assignee, channel, date range, free
   text), **When** an agent applies it, **Then** the same filtered view can be shared as a link that
   reproduces it for another authorized user.
5. **Given** a ticket in a given language, **When** an agent inserts a pre-written reply, **Then** the
   version matching that ticket's language is inserted with its placeholders (customer name,
   reference number, agent name) already filled in.
6. *(Tier D — specified, not built)* **Given** a ticket an agent is working, **When** they set a
   personal reminder linked to it for a future time, **Then** it later surfaces in their task list
   referencing that ticket. Not implemented this sprint; the data model reserves space for it so it
   can be added without touching ticket structure.
7. *(Tier D — specified, not built)* **Given** an organization deploying the product, **When** they
   apply their own logo and colors, **Then** customer-facing surfaces reflect that branding. Not
   implemented this sprint.

---

### User Story 5 - SLA & Automation (Priority: P1) — Tier M *(breach notification delivery is Tier D)*

Response and resolution targets are enforced automatically, correctly survive a full restart, and
unassigned work distributes itself fairly.

**Why this priority**: SLA correctness after a restart is one of the product's hardest and most
safety-critical guarantees (no in-memory state is trustworthy), and automatic distribution is what
lets a team operate without a dispatcher.

**Independent Test**: Park a ticket in a customer-waiting status for a fixed period, confirm its
deadline shifts out by exactly that period, then restart the entire system and confirm every ticket's
breach state reads identically before and after.

**Acceptance Scenarios**:

1. **Given** a ticket parked in a status that pauses its SLA clock for two hours, **When** it leaves
   that status, **Then** its resolution deadline is exactly two hours later than it would otherwise
   have been.
2. **Given** a running system with tickets in every breach state, **When** the entire system is
   restarted, **Then** every ticket reports the same breach state as before the restart — no state
   was held only in memory.
3. **Given** an SLA policy restricted to business hours, **When** time elapses outside the owning
   branch's configured hours or outside its time zone, **Then** that time does not count against the
   deadline.
4. **Given** a ticket that has breached its target, **When** the periodic breach check runs more than
   once, **Then** exactly one breach event is recorded for that ticket and that target, and the
   ticket's priority is raised and it is reassigned to the department's lead exactly once.
5. **Given** an unassigned ticket in a department with available agents holding the right permission,
   **When** auto-assignment runs, **Then** it is assigned to one of them in a fair rotating order,
   skipping anyone marked unavailable.
6. **Given** a Team Lead, **When** they override the SLA policy applied to one specific ticket by
   selecting a different existing SLA policy and supplying a reason, **Then** that ticket's
   deadlines are recomputed from the ticket's original creation time under the newly selected
   policy — applying its accumulated pause time exactly as usual — and the reason is recorded;
   **When** they attempt the override without supplying a reason, **Then** it is rejected.
   **Given** an override whose recomputed deadline has already passed, **When** the override is
   applied, **Then** the ticket is immediately recorded as breached rather than the override being
   blocked or the breach being suppressed.
7. *(Tier D — specified, not built)* **Given** a ticket that breaches or is about to breach its SLA,
   **When** the breach is recorded, **Then** the responsible agent or lead receives a notification
   through an external channel (e.g. email) containing the ticket's reference and the breached
   target. Not implemented this sprint; breach events are already recorded regardless (Scenario 4),
   so this adds delivery, not new detection logic.

---

### User Story 6 - Knowledge Base (Priority: P2) — Tier M

Agents (and the AI features in Story 7) find and reuse accurate answers, in whichever language the
question was asked in.

**Why this priority**: This directly reduces ticket handling time and is a prerequisite for the AI
suggested-solution capability, but the core ticket loop (Stories 1–5) is usable without it.

**Independent Test**: Publish one article with both an Arabic and an English body, then run a search
in each language and confirm the same article is returned as relevant for both; separately, stop any
optional ranking component and confirm search still returns usable results.

**Acceptance Scenarios**:

1. **Given** a published bilingual article, **When** a query is submitted in Arabic, **Then** it
   ranks above unrelated articles.
2. **Given** the same article, **When** an English query for the same underlying concept is
   submitted, **Then** it is returned via its English content.
3. **Given** an article being published, **When** its Arabic body is empty, **Then** publishing is
   rejected.
4. **Given** an optional ranking-refinement component is unavailable, **When** a search is run,
   **Then** results are still returned, ordered by the remaining (lexical/semantic) signal.

---

### User Story 7 - AI-Assisted Ticket Handling (Priority: P2) — Tier M *(conversational assistant is Tier D)*

Every AI-assisted capability speeds up an agent's work but never blocks it, and the product remains
fully usable with the AI service switched off entirely.

**Why this priority**: This is the product's key differentiator over a plain ticketing system, but
by design it is additive on top of Stories 1–6 — every fallback in this story assumes the
non-AI product already works.

**Independent Test**: Stop the AI service entirely (including disconnecting from any external
network it would otherwise need) and confirm every screen remains fully usable with no error dialogs
and every fallback engaged; separately, confirm an Arabic ticket produces an Arabic summary and an
Arabic draft reply.

**Acceptance Scenarios**:

1. **Given** the AI service is completely unreachable, **When** any of the four AI-assisted
   capabilities would normally run, **Then** its documented fallback engages instead, with no error
   shown to the user and no capability left in a broken or loading state.
2. **Given** a ticket written in Arabic, **When** a summary or a suggested reply is requested,
   **Then** both are produced in Arabic.
3. **Given** an AI-suggested category on a new ticket, **When** an agent accepts it, **Then** a
   distinct, attributable record captures that the suggestion was accepted, including the confidence
   level offered; **When** the agent instead picks a different category, **Then** the ticket's
   category reflects the agent's choice, never the raw suggestion.
4. **Given** the AI service is unreachable, **When** a new ticket is created, **Then** ticket creation
   completes at normal speed — it is never slowed or blocked by AI processing.
5. **Given** a fixed bilingual reference set of sample tickets, **When** categorization accuracy is
   measured against it, **Then** a recorded score results.
6. **Given** a ticket is opened, **When** the suggested-solution panel is requested, **Then** it
   offers up to three related knowledge-base articles drawn from Story 6's search.
7. *(Tier D — specified, not built)* **Given** a customer or agent with a question, **When** they
   engage a conversational assistant, **Then** it can answer using the knowledge base and report on
   ticket status, in the user's language. Not implemented this sprint; the knowledge base and the
   four AI capabilities above already provide everything this needs as building blocks.

---

### User Story 8 - Communication Channels (Priority: P3) — Tier S *(one adapter functional; others are stubs)*

A message arriving through an external channel becomes a ticket or a ticket update automatically,
proving that any future channel can be added without touching ticket logic.

**Why this priority**: This proves an architectural property (channel independence) rather than
adding new agent-facing capability beyond what Stories 1–2 already provide; one working channel is
enough to prove it.

**Independent Test**: Send an inbound message from an unrecognized sender and confirm both a new
customer and a new ticket are created from it, scoped to the receiving identifier's configured
branch/department; then send a second message that quotes an existing ticket from a *different*
branch's receiving identifier and confirm the ticket's own branch/department wins, with the mismatch
recorded rather than blocking the append.

**Acceptance Scenarios**:

1. **Given** an inbound message arriving at a recipient identifier (e.g. a mailbox address) that is
   configured to a specific branch and department, **When** it is processed and no matching contact
   method is found, **Then** a new customer and a new ticket are created from it, scoped to that
   configured branch and department.
2. **Given** an inbound message arriving at a recipient identifier with no matching channel
   configuration, **When** it is processed, **Then** the resulting customer and ticket are scoped to
   a designated system-default branch and department, and the ticket is flagged as needing triage so
   it surfaces in the Unassigned queue (Story 4) rather than being silently scoped incorrectly.
3. **Given** an inbound message that quotes an existing ticket's reference number, **When** it is
   processed, **Then** it is appended to that ticket's timeline rather than creating a new ticket,
   and the ticket's own branch and department govern the message — overriding whatever the
   receiving identifier's channel configuration would otherwise have assigned.
4. **Given** an inbound message that quotes an existing ticket's reference number, **When** the
   ticket's branch or department differs from the one the receiving identifier is configured to,
   **Then** the message is still appended to the ticket, and the mismatch is recorded as a timeline
   entry rather than blocking the append.
5. **Given** a customer who has legitimately contacted two different branches, **When** their
   contact details are looked up for a new inbound message, **Then** matching considers only the
   customer records already scoped to the branch/department the message resolves to — it never
   merges or matches across their separate, branch-specific customer records.
6. **Given** a ticket flagged as needing triage, **When** a staff member corrects its branch or
   department, **Then** the needs-triage flag is cleared and the correction is recorded on the
   ticket's timeline with both the old and the new values.
7. **Given** the one functioning channel today (email), **When** a hypothetical new channel is added
   later, **Then** doing so requires only that channel's own message-normalization behavior — no
   change to how tickets are created or updated.
8. **Given** a channel not yet built (e.g. WhatsApp, SMS, live chat), **When** it is selected or
   invoked, **Then** the system responds that it is not yet available, without affecting any other
   channel.

---

### User Story 9 - Customer Portal (Priority: P3) — Tier S *(full accounts, satisfaction rating, live chat are Tier D)*

A customer submits and tracks their own ticket, and reads published help articles, without needing
to create an account or speak to an agent.

**Why this priority**: Self-service reduces inbound volume but is not required for the core support
loop (Stories 1–5) to function; it depends on tickets, categories, and the knowledge base already
existing.

**Independent Test**: Submit a ticket through the portal as an anonymous visitor, then track it using
its reference number and the same contact method; confirm a mismatched contact method is treated
identically to an unknown reference number.

**Acceptance Scenarios**:

1. **Given** a visitor with no account, **When** they submit a ticket through the portal, **Then** a
   ticket is created and attributed to the portal as its origin.
2. **Given** a valid ticket reference number, **When** it is looked up with a contact method that
   does not match the one used to submit it, **Then** the response is identical to looking up an
   unknown reference number — it does not confirm or deny that the ticket exists.
3. **Given** a customer's own ticket history in the portal, **When** it is viewed, **Then** no
   internal-only note or communication ever appears in it.
4. **Given** a published knowledge-base article, **When** a visitor browses it through the portal,
   **Then** no authentication is required.
5. *(Tier D — specified, not built)* **Given** a returning customer, **When** they register and log
   into a persistent portal account, **Then** their historical tickets appear automatically without
   re-entering a reference number. Not implemented this sprint; tickets are already durably linked to
   a customer record, so this adds login, not new linkage.
6. *(Tier D — specified, not built)* **Given** a resolved ticket, **When** the customer is asked to
   rate their experience, **Then** their rating and comment are attached to the ticket and visible to
   staff. Not implemented this sprint; the ticket record already reserves space for a rating and a
   comment.
7. *(Tier D — specified, not built)* **Given** a customer needing live help, **When** they start a
   live chat from the portal, **Then** they can reach an agent in real time. Not implemented this
   sprint.

---

### User Story 10 - Reports & Management Oversight (Priority: P3) — Tier S *(satisfaction reporting, scheduled delivery, exports are Tier D)*

A Team Lead or Administrator sees ticket volume, SLA compliance, and per-agent performance, scoped to
what they are authorized to see.

**Why this priority**: This is an oversight capability consumed after the core operational loop is
already producing data; it has no independent value until Stories 1, 2, and 5 exist.

**Independent Test**: As a Team Lead, request the standard report set and confirm it only reflects
your own department; as an Administrator, request the same report with an explicit cross-branch scope
and confirm it reflects every branch.

**Acceptance Scenarios**:

1. **Given** a Team Lead requesting reports, **When** they view ticket counts by status, SLA
   compliance, or per-agent volume, **Then** the figures cover only their own department.
2. **Given** an Administrator who holds the separate cross-branch reporting permission and requests
   the same reports with an explicit cross-branch scope, **When** they view them, **Then** the
   figures cover every branch; **Given** an Administrator who does not hold that permission,
   **When** they attempt the same request, **Then** it is refused and their reports remain confined
   to their own branch/department, even though they hold other administrative permissions.
3. *(Tier D — specified, not built)* **Given** satisfaction ratings exist (Story 9), **When**
   reporting is viewed, **Then** satisfaction results appear alongside the existing report set. Not
   implemented this sprint.
4. *(Tier D — specified, not built)* **Given** any report, **When** a recipient wants it delivered
   automatically or downloaded, **Then** it can be scheduled for email delivery or exported to a
   file. Not implemented this sprint.

---

### User Story 11 - Integrations for Machine Clients (Priority: P3) — Tier S *(ERP connectors, outbound webhooks, retry/durable delivery are Tier D)*

An authorized external program integrates with the system using a scoped credential, without needing
a human's login.

**Why this priority**: Machine integration is a capability the product exposes once the core domain
exists; it has no standalone value ahead of Stories 1–2.

**Independent Test**: Issue a credential scoped only to reading tickets, confirm it can list tickets,
and confirm it is refused when it attempts to create one.

**Acceptance Scenarios**:

1. **Given** the system's documented capabilities, **When** an external, authorized program consults
   them, **Then** it can determine what integration is possible without needing source access.
2. **Given** a machine credential scoped only to reading tickets, **When** it is used to list
   tickets, **Then** it succeeds; **When** it is used to attempt creating one, **Then** it is refused.
3. *(Tier D — specified, not built)* **Given** an external ERP system, **When** integration is
   configured, **Then** data can be exchanged with it. Not implemented this sprint.
4. *(Tier D — specified, not built)* **Given** an event the system wants to announce externally,
   **When** it occurs, **Then** it can be delivered to a configured external endpoint, retried on
   failure, and durably held until delivered. Not implemented this sprint.

---

### User Story 12 - Bilingual & Multi-Tenant Platform Guarantee (Priority: P1) — Tier M *(custom branding is Tier D — see Story 4)*

This is not a standalone journey but a guarantee verified against every other story above: the whole
product — every screen, every query, every record — is correct in Arabic and English, in
right-to-left and left-to-right layout, on any supported screen size, and correctly confined to the
requester's branch and department.

**Why this priority**: PLAN.md treats Arabic as a co-equal locale and multi-branch/multi-department
operation as structural, not optional — both are load-bearing for every other story, not an add-on
tested once at the end.

**Independent Test**: For any feature above, switch language and confirm no untranslated text
appears; resize to 375px and confirm nothing breaks; and confirm a user scoped to one
branch/department never sees data from another.

**Acceptance Scenarios**:

1. **Given** any screen in the product, **When** the display language is Arabic, **Then** every
   piece of user-facing text is in Arabic — none is left in English by omission.
2. **Given** any screen, **When** it is viewed at a width as narrow as 375px, **Then** it remains
   usable with no broken layout.
3. **Given** any data query anywhere in the product, **When** it is run by a user scoped to a
   specific branch and department, **Then** it returns only data from that branch and department,
   with no feature-specific exception.
4. *(Tier D — specified, not built)* **Given** an organization deploying the product, **When** they
   configure their own branding, **Then** customer-facing surfaces show it instead of the default
   appearance. Not implemented this sprint (tracked under Story 4).

---

### Edge Cases

- What happens when an inbound channel message cannot be matched to any ticket or customer and also
  lacks enough information (e.g. no usable contact method) to create a new customer record?
- What happens when two staff members attempt to change the same ticket's status at the same moment
  along two different, individually legal paths?
- What happens when the agent or team a ticket is assigned to is deactivated while the ticket is
  still open?
- What happens when a customer's only contact method (marked primary) is removed or deactivated?
- What happens when a category or priority referenced by an existing ticket is later deactivated —
  does the existing ticket keep functioning, and can new tickets no longer choose it?
- What happens when no SLA policy at all matches a ticket's category or priority and no default
  policy has been configured?
- What happens when a branch's business hours or time zone configuration is changed after tickets
  already have SLA time accruing against the old configuration?
- What happens when an AI-assisted capability responds slowly or with a malformed result, rather
  than being cleanly unreachable — is that treated the same as "unreachable" for fallback purposes?
- What happens when a Team Lead (who has every Agent capability plus more) attempts an action that
  requires a permission tied specifically to the Agent role rather than granted to Team Leads by
  default?
- What happens when an attachment upload fails partway through — does the ticket or customer record
  end up referencing a missing file?
- What happens when a customer submits a second ticket through the portal using contact details that
  are extremely similar to, but not an exact match for, an existing customer (e.g. a typo)?

## Requirements *(mandatory)*

### Platform-Wide Requirements (apply to every feature, F01–F12 alike) — Tier M

- **FR-001**: Every user-facing string in the product MUST be available in both Arabic and English,
  with no screen left partially untranslated.
- **FR-002**: Every screen MUST render correctly in both right-to-left and left-to-right reading
  order from one shared layout definition — no separate "Arabic version" of any screen may exist.
- **FR-003**: The product MUST remain usable at a display width as narrow as 375px.
- **FR-004**: Every organizational record MUST belong to exactly one branch and one department (or be
  drawn from data explicitly shared across all of them, where that is the nature of the record), and
  every read or write MUST be confined to the branch(es)/department(s) the requester is authorized
  for, with no feature-specific exception.
- **FR-005**: Every action that creates, modifies, or removes data MUST produce a permanent,
  attributable record of what changed, who changed it, and when, as part of that same action — never
  written separately or after the fact.
- **FR-006**: Ticket activity records and administrative audit records MUST be permanent once
  written; no path anywhere in the product may edit or remove them.
- **FR-007**: Every permission check MUST be enforced by the system itself; what a particular
  interface chooses to show or hide MUST have no bearing on whether an action actually succeeds.
- **FR-008**: The legal next steps for a ticket's status MUST be determined by configurable rules,
  not fixed in the software, so an administrator can change the workflow without a new release.
- **FR-009**: Every AI-assisted capability MUST define a deterministic, non-AI fallback, and the
  product MUST remain fully usable — no broken screens, no blocked workflows — when the AI service is
  completely unreachable.
- **FR-010**: SLA timing and breach status MUST always be re-derivable from stored data alone, giving
  the same result before and after a full system restart.

### F01 — Customer Management — Tier M

- **FR-011**: The system MUST require at least one contact method when a customer record is created,
  with exactly one marked as the primary method.
- **FR-012**: Customer search MUST match against full name (in either language), organization name,
  and any contact detail, including close/approximate matches, so that partial Arabic names and
  alternate spellings both succeed.
- **FR-013**: A customer MUST never be permanently removable; deactivation MUST be the only removal
  path, MUST be reversible, and MUST preserve the customer's complete ticket history.
- **FR-014**: Staff MUST be able to view a customer's complete history as every ticket and every
  recorded event for that customer, merged into one chronological view.

### F02 — Ticket Management — Tier M

- **FR-015**: Every ticket MUST receive a unique, permanent, human-quotable reference number at the
  moment it is created.
- **FR-016**: A ticket's category and priority MUST both be required, MUST both be currently active,
  and, when scoped to a specific department, MUST match the ticket's own department.
- **FR-017**: A ticket MUST only move between statuses along a path explicitly permitted by
  configuration; any other attempted transition MUST be rejected with an explanation — in the
  requester's own language — of the current status and the statuses actually reachable from it.
- **FR-018**: Specific status transitions MUST be able to require the actor to hold a specific
  permission and/or supply a reason, as configured; reopening a closed ticket requires a permission by
  default.
- **FR-019**: A ticket MUST support independent assignment to an individual agent and to a team,
  including being queued to a team with no individual owner.
- **FR-020**: Every change made to a ticket (status, assignment, field edits, notes, replies,
  attachments) MUST append to that ticket's single ordered activity timeline; no separate history
  record may exist to fall out of sync with it.
- **FR-021**: The moment of the first customer-visible reply on a ticket MUST be captured exactly
  once and MUST never be overwritten by a later reply.

### F03 — Communication Channels — Tier S (one adapter functional this sprint)

- **FR-022**: The system MUST accept inbound messages from at least one real external channel and
  convert them into new tickets or into updates on existing tickets.
- **FR-023**: An inbound message MUST be linked to an existing ticket when it references that
  ticket's reference number, or matched to an existing customer when the sender matches a known
  contact method within the branch and department resolved for the message (FR-023a); otherwise, a
  new customer record MUST be created from the sender's details, scoped to that same branch and
  department. Contact-method matching MUST NOT be performed across branches: customer identity is
  per branch/department, not global — the same person legitimately contacting two different
  branches MUST produce two separate customer records, one per branch/department, never a single
  record shared or merged across them.
- **FR-023a**: Each channel's receiving identifier (e.g. a mailbox address or a phone number) MUST
  be configurable to a specific branch and department (and optionally a default category); an
  inbound message MUST be scoped to whatever branch and department its receiving identifier is
  configured to. A receiving identifier with no matching configuration MUST NOT block message
  intake — the resulting customer/ticket MUST instead be scoped to a designated system-default
  branch and department, and MUST be flagged as needing triage so it surfaces in the Unassigned
  queue (FR-026) instead of being silently mis-scoped.
- **FR-023b**: When an inbound message quotes a valid, existing ticket's reference number, that
  referenced ticket MUST determine the branch and department the message is scoped to (i.e. the
  ticket's own branch and department), overriding whatever branch/department the receiving
  identifier's channel configuration would otherwise have assigned. If the referenced ticket's
  branch or department differs from the receiving identifier's configured branch or department,
  that mismatch MUST be recorded as an entry on the ticket's timeline, but MUST NOT prevent the
  message from being appended to the ticket.
- **FR-023c**: Correcting a needs-triage ticket's branch or department (per FR-023a) MUST clear the
  needs-triage flag and MUST record the correction as a timeline entry showing both the old and the
  new branch/department values.
- **FR-024**: Adding a new channel in the future MUST require implementing only that channel's own
  message-normalization behavior, with no change to how tickets are created or updated.
- **FR-025**: A channel not yet built MUST be able to report that it is unavailable without affecting
  the operation of any other channel. *(Tier S — contract and stub only for every channel besides the
  one functioning this sprint.)*

### F04 — Agent Dashboard — Tier M (personal tasks/reminders is Tier D)

- **FR-026**: Agents MUST have distinct views for their own open tickets, their team's queue,
  unassigned tickets, tickets close to breaching SLA, and recently closed tickets.
- **FR-027**: Agents MUST be able to filter any ticket view by status, priority, category, assignee,
  channel, date range, and free text, and MUST be able to share a given filter combination as a link
  that reproduces it.
- **FR-028**: The ticket working view MUST show the related customer's identity and history without
  requiring navigation away from the ticket.
- **FR-029**: Agents MUST be able to insert a pre-written reply matching the ticket's own language,
  with placeholders (customer name, reference number, agent name) automatically filled in.
- **FR-030**: A note marked internal MUST be visually distinguishable from customer-facing
  communication and MUST never be exposed on any customer-facing surface.
- **FR-031**: A Team Lead MUST be able to do everything an Agent can do, additionally reassign
  tickets across their entire department (not only their own), and view their team's queue and
  performance.
- **FR-032** *(Tier D — specified, not built)*: Agents MUST be able to create a personal task or
  reminder linked to a ticket, to be surfaced back to them at a future time. The data model MUST
  reserve space for this so it can be added without restructuring existing ticket or agent records.

### F05 — SLA & Automation — Tier M (breach-notification delivery is Tier D)

- **FR-033**: A ticket's SLA targets MUST be resolved using the most specific matching policy
  available — category and priority together, then priority alone, then category alone, then a
  default — resolved once and reused consistently.
- **FR-034**: Time spent in a status designated as SLA-pausing MUST NOT count toward SLA deadlines;
  elapsed time MUST resume counting the instant the ticket leaves such a status.
- **FR-035**: A ticket's breach state (on track / at risk / breached) MUST always be computed from
  stored data at the moment it is requested, and MUST NOT depend on any state held only in running
  memory.
- **FR-036**: When an SLA policy is restricted to business hours, elapsed time MUST accrue only
  during the owning branch's configured open hours and time zone.
- **FR-037**: The system MUST periodically check open tickets against their SLA targets, MUST record
  a breach exactly once per ticket per target even if the check runs more than once, and MUST
  escalate a breached ticket by raising its priority and reassigning it to the department's lead.
- **FR-038**: Unassigned tickets in a department MUST be distributable automatically, in a fair
  rotating order, to active agents in that department who hold the relevant permission and are not
  marked unavailable.
- **FR-039**: A Team Lead MUST be able to override the SLA policy applied to an individual ticket by
  selecting a different existing SLA policy for it; a reason MUST be supplied and recorded for the
  override, and an override without a reason MUST be rejected. Custom, one-off SLA targets outside
  the organization's configured policies are out of scope. Following an override, the ticket's
  deadlines MUST be recomputed from the ticket's original creation time under the newly selected
  policy, applying the ticket's accumulated pause time exactly as it would for any other policy
  resolution (FR-033–FR-035) — the override changes which policy applies, never the ticket's
  elapsed clock. If recomputing under the new policy means the ticket is immediately in breach, that
  outcome MUST be permitted and the breach MUST be recorded (FR-037), the same as any other breach.
- **FR-040** *(Tier D — specified, not built)*: When a ticket breaches or nears breaching its SLA,
  the responsible agent or lead MUST be able to receive a notification through an external channel
  (e.g. email), containing the ticket's reference and the breached target. Breach events are already
  recorded regardless of this capability's existence (FR-037), so it adds delivery on top of
  detection already in place.

### F06 — Knowledge Base — Tier M

- **FR-041**: A knowledge-base article MUST require a non-empty title and body in both Arabic and
  English before it can be published.
- **FR-042**: Searching the knowledge base MUST return relevant results regardless of whether the
  query is written in Arabic or English, ranking closely related articles above unrelated ones.
- **FR-043**: Search MUST continue to return usable results when any optional
  ranking-refinement component is unavailable.

### F07 — AI-Assisted Ticket Handling — Tier M (conversational assistant is Tier D)

- **FR-044**: On ticket creation, the system MUST offer a suggested category together with a
  confidence indicator, and MUST NOT set the ticket's actual category directly; an agent MUST
  explicitly accept or override the suggestion, and acceptance MUST be recorded as a distinct,
  attributable action alongside the confidence that was offered.
- **FR-045**: On request, and automatically once a ticket has accumulated a large number of events,
  the system MUST be able to offer a summary of the ticket.
- **FR-046**: On request, the system MUST be able to offer a draft reply that an agent can edit before
  sending; a draft MUST NEVER be sent automatically under any configuration.
- **FR-047**: On opening a ticket, the system MUST be able to offer up to three related
  knowledge-base articles as a suggested solution, drawn from the same search behavior as F06.
- **FR-048**: Every AI-assisted output MUST be produced in the same language as the ticket it
  concerns.
- **FR-049**: None of the four AI-assisted capabilities (categorization, summary, suggested reply,
  suggested solution) MUST be allowed to delay or block the action that triggered them (e.g. creating
  a ticket), and each MUST have its own deterministic fallback per FR-009.
- **FR-050**: The system MUST be able to score categorization accuracy against a fixed bilingual
  reference set of sample tickets and record the resulting score.
- **FR-051** *(Tier D — specified, not built)*: Customers and agents MUST be able to interact with a
  conversational assistant capable of answering questions from the knowledge base and reporting on
  ticket status, in the user's own language. The knowledge base and the four capabilities above
  already provide the building blocks this needs, so it is additive.

### F08 — Customer Portal — Tier S (accounts, satisfaction rating, live chat are Tier D)

- **FR-052**: A customer MUST be able to submit a new ticket by supplying their name, a contact
  method, subject, description, category, and optional attachments, without needing an account.
- **FR-053**: A customer MUST be able to track a ticket using its reference number together with the
  contact method used to submit it; a valid reference number paired with a non-matching contact
  method MUST produce a response identical to an unknown reference number, revealing nothing about
  whether the ticket exists.
- **FR-054**: A customer's own ticket history MUST list only their own tickets and MUST never include
  any internal-only note or communication.
- **FR-055**: Published knowledge-base articles MUST be browsable without requiring authentication.
- **FR-056** *(Tier D — specified, not built)*: A returning customer MUST be able to register and log
  into a persistent portal account and see their historical tickets automatically. Tickets are
  already durably linked to a customer record, so this is additive.
- **FR-057** *(Tier D — specified, not built)*: A customer MUST be able to submit a satisfaction
  rating and comment after a ticket is resolved, visible to staff. The ticket record MUST reserve
  space for this rating and comment so it can be added without restructuring the ticket.
- **FR-058** *(Tier D — specified, not built)*: A customer MUST be able to start a live chat
  conversation with an agent from the portal.

### F09 — Reports & Management Oversight — Tier S (satisfaction reporting, scheduled delivery, exports are Tier D)

- **FR-059**: Management reporting MUST cover, at minimum: ticket counts by status (filterable by
  branch, department, and date range), SLA compliance percentage tracked separately for first
  response and for resolution, and per-agent volume (assigned, resolved, average resolution time).
- **FR-060**: A report MUST reflect only the branch(es)/department(s) the requester is authorized to
  see. Requesting a broader, explicit cross-branch view MUST require a distinct, separately
  grantable permission — holding other administrative permissions MUST NOT by itself grant this
  view.
- **FR-061** *(Tier D — specified, not built)*: Once customer satisfaction ratings exist (FR-057),
  reporting MUST include satisfaction results alongside the existing report set.
- **FR-062** *(Tier D — specified, not built)*: Reports MUST be schedulable for automatic delivery by
  email and exportable to a downloadable file.

### F10 — Security & Administration — Tier M (audit-trail browsing UI is Tier D)

- **FR-063**: Every user MUST authenticate before accessing any non-portal, non-public part of the
  product, with sessions that expire and can be renewed without re-entering credentials on every
  request.
- **FR-064**: Every action that mutates data MUST declare and enforce the specific permission it
  requires, independent of the interface used to invoke it (see FR-007).
- **FR-065**: Administrators MUST be able to fully configure branches, departments, users, roles,
  permissions, categories, priorities, statuses, status transitions, SLA policies, and pre-written
  replies.
- **FR-066**: Every mutating action MUST produce exactly one audit record capturing both the
  before-state and the after-state, written as part of that same action; if the action is rolled back
  or fails, no audit record MUST remain.
- **FR-067** *(Tier D — specified, not built)*: Administrators MUST be able to browse and search the
  audit trail through the interface. The audit trail itself is already captured from the first
  release regardless (FR-066), so this adds a viewer, not new data capture.

### F11 — Integrations for Machine Clients — Tier S (ERP connectors, outbound webhooks, retry/durable delivery are Tier D)

- **FR-068**: The system's capabilities MUST be documented and discoverable so that an authorized
  external program can determine what integration is possible.
- **FR-069**: A machine (non-human) client MUST authenticate with a credential scoped to a specific,
  limited set of permissions, and MUST be refused any action outside that scope.
- **FR-070** *(Tier D — specified, not built)*: The system MUST be able to exchange data with
  external ERP systems.
- **FR-071** *(Tier D — specified, not built)*: The system MUST be able to notify external systems of
  events via outbound calls, retrying on failure and durably holding a notification until it is
  successfully delivered.

### F12 — Platform-Wide Cross-Cutting Requirements — Tier M (custom branding is Tier D)

*(Restates and extends the Platform-Wide Requirements above as an explicit checklist verified against
every one of F01–F11, per PLAN.md §5 F12.)*

- **FR-072**: Every department-scoped and branch-scoped query anywhere in the product MUST honor the
  requester's actual authorized scope, with no feature-specific exception (reinforces FR-004).
- **FR-073**: Text specific to one reading direction (e.g. a reference number, an email address, a
  phone number, a URL) MUST still display correctly regardless of the surrounding layout's reading
  direction.
- **FR-074** *(Tier D — specified, not built)*: An organization MUST be able to apply its own visual
  branding (logo, colors) to customer-facing surfaces, in place of the default appearance.

### Key Entities *(data involved across every feature above)*

- **Branch**: A physical or organizational location the business operates from, with its own
  operating hours and time zone; the top-level unit tickets, customers, and staff are organized
  under.
- **Department**: A functional unit within a branch (e.g. billing, technical support) that tickets,
  categories, and staff assignments are organized under.
- **Team**: A named group of agents within a department, used for team-queued ticket assignment and
  team-level performance reporting.
- **User / Staff Account**: A person who can sign in — an Administrator, Team Lead, or Agent — who may
  hold different roles in different departments.
- **Role**: A named bundle of permissions (Administrator, Team Lead, Agent, Customer) assignable to a
  user.
- **Permission**: A single, specific capability (e.g. assigning a ticket, closing a ticket, deleting a
  customer, changing configuration) that can be required for an action and granted through a role.
- **Customer**: The person or organization a ticket is raised on behalf of, with one or more contact
  methods, in the language they prefer to be addressed in. Customer identity is scoped per branch
  and department, not global: the same person legitimately contacting two different
  branches/departments is represented as two separate customer records, each with its own
  independent contact methods and ticket history — there is no shared or merged identity across
  branches.
- **Contact Method**: A specific way to reach a customer (phone, email, WhatsApp, other), one of
  which is designated primary.
- **Category**: A classification applied to a ticket, organized into a hierarchy, optionally specific
  to one department or shared globally.
- **Priority**: An urgency level applied to a ticket, ordered by severity.
- **Ticket Status**: A named stage in a ticket's life (e.g. new, open, in progress, resolved, closed,
  reopened), some of which pause SLA accounting and some of which are terminal.
- **Status Transition Rule**: A configured, permitted move from one ticket status to another,
  optionally requiring a specific permission and/or a recorded reason — this rule set is what makes
  the workflow configurable rather than fixed in software.
- **Ticket**: The central support record — its subject, description, category, priority, status,
  assignment (to an individual and/or a team), originating channel, and language — that everything
  else in the product attaches to. A ticket may carry a needs-triage flag, set when it was created
  from a channel message whose receiving identifier had no matching Channel Configuration, so it is
  surfaced for a human to correct its branch/department assignment.
- **Channel Configuration**: A mapping from one channel's receiving identifier (e.g. a mailbox
  address or a phone number) to the branch, department, and optional default category that inbound
  messages arriving there are scoped to.
- **Ticket Activity Entry**: A single, permanent, ordered entry in a ticket's timeline (status change,
  assignment, field edit, note, reply, attachment, AI suggestion applied, SLA breach, reopen),
  attributed to whoever performed it.
- **Attachment**: A file associated with a ticket or a customer.
- **SLA Policy**: A configured first-response and resolution target, optionally restricted to
  business hours, resolved for a ticket based on its category and priority.
- **Pre-written Reply**: A reusable response template, in both languages, with placeholders, scoped to
  a department and optionally a category.
- **Knowledge Base Article**: A published (or unpublished/draft) help article with a title and body
  in both languages, organized by category, that both agents and the AI suggested-solution capability
  draw from.
- **Inbound Message Record**: The as-received form of a message arriving through an external channel,
  retained for traceability, before it is turned into a ticket or a ticket update.
- **AI Suggestion Record**: The record of an AI-offered category suggestion and its confidence level
  on a ticket, and whether/how it was acted on.
- **AI Usage Record**: A record of a single AI-assisted call sufficient to audit AI usage after the
  fact — at minimum, which capability was invoked, which model served it, timing, and outcome
  (success, fallback, or error) — independent of any specific tracing tool.
- **Machine Client Credential**: A scoped credential issued to a non-human integration, limited to a
  specific set of permissions.
- **Audit Record**: A permanent, before/after record of a single administrative or data-changing
  action, distinct from ticket activity entries, attributed to its actor.
- **Customer Satisfaction Rating** *(Tier D)*: A customer's post-resolution rating and comment on a
  ticket, reserved for in the data model ahead of being collected.
- **Personal Task / Reminder** *(Tier D)*: An agent's own reminder linked to a ticket, to resurface at
  a future time, reserved for in the data model ahead of being built.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent can complete the full journey — find or create a customer, raise a ticket,
  receive an AI category suggestion, have it assigned, move it through its lifecycle, and close it,
  with the full history reconstructible — entirely in Arabic, with no untranslated text encountered.
- **SC-002**: 100% of attempted illegal ticket status changes are rejected with an explanation, in
  the requester's language, of the current status and the valid next steps.
- **SC-003**: 100% of data-changing actions produce a permanent, complete, before/after audit record
  as part of that same action; a rolled-back action leaves none.
- **SC-004**: Every ticket's SLA breach state reads identically before and after a full system
  restart, with zero discrepancies across a representative seeded dataset.
- **SC-005**: With the AI service completely unreachable (including no external network access),
  every screen remains fully usable, and all four AI-assisted capabilities engage their fallback with
  zero user-facing errors.
- **SC-006**: A bilingual knowledge-base search returns the same relevant article for equivalent
  queries in Arabic and in English, and continues returning usable results with any optional ranking
  refinement disabled.
- **SC-007**: Switching the interface language changes reading direction and layout with no visible
  delay and no broken layout, at every screen width from 375px upward.
- **SC-008**: A Team Lead's report reflects only their own department's figures; an Administrator's
  report reflects every branch only when an explicit cross-branch view is requested.
- **SC-009**: A customer can submit and later track a ticket through the portal without ever creating
  an account, and never encounters any internal-only communication in doing so.
- **SC-010**: A freshly seeded system (2 branches, 3 departments, 20 customers, 40 tickets across all
  statuses/priorities/channels, 10 fully bilingual knowledge-base articles) is fully operable
  end-to-end within minutes of first startup, with no manual data entry required to demonstrate every
  Tier M and Tier S capability above.

## Assumptions

- PLAN.md is authoritative for scope, domain rules, and acceptance criteria; where this
  specification and PLAN.md appear to differ, PLAN.md governs and this document should be corrected.
- The 48-hour delivery window is what separates Tier M/S (built and demonstrable this sprint) from
  Tier D (specified and reserved for, but not built); a Tier D item is a guaranteed, low-friction
  future extension, not a discarded idea.
- Seed data volumes (2 branches, 3 departments, 5 users across all four roles, 20 customers, 40
  tickets, 10 knowledge-base articles) represent the minimum fixture needed to demonstrate every
  capability in this specification, not a target scale ceiling.
- Business hours are configured per branch as a recurring weekly open/close schedule; public holidays
  and one-off exceptions are out of scope for this sprint.
- Reasonable, unspecified operational limits (e.g. attachment file size and type restrictions) follow
  ordinary industry-standard defaults for a business support tool, since PLAN.md does not set them
  explicitly.
- A ticket's language is captured once, from whatever context is available at creation (the channel
  it arrived through, or the customer's stated preference), and is not re-detected automatically
  afterward.
- Arabic and English are the only two locales in scope; no third language is anticipated by this
  specification.
- The scoping pattern that assigns each entity to a tenant-scoping category (PLAN.md §4.1) governs
  which entities are branch/department-scoped, globally shared, or transitively scoped through a
  parent; this specification describes entities in business terms and depends on, but does not
  restate or override, that assignment.
- The Deliberate Debt table and Definition of Done already published in PLAN.md (§8, §10) govern what
  "sprint-complete" means for this product and are not duplicated here.

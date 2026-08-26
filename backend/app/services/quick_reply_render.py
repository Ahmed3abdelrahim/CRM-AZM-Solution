from __future__ import annotations

from app.models.quick_reply import QuickReply
from app.models.ticket import Ticket


def render(quick_reply: QuickReply, ticket: Ticket) -> str:
    """F04 — quick replies insert `body_ar`/`body_en` matching the ticket's `source_locale`,
    with `{{customer_name}}`/`{{reference_no}}`/`{{agent_name}}` substitution. Pure function: no
    session access, no I/O — `ticket.customer` is read only if the caller already attached it
    (as `TicketService.get` does for FR-028), and a missing assignee simply substitutes an empty
    string rather than triggering a lookup. The frontend reply composer (T086) performs the
    identical substitution client-side against the already-fetched ticket/customer, so this
    function is the shared source of truth for future backend callers (e.g. a dedicated render
    endpoint) rather than something wired into a route this batch.
    """

    body = quick_reply.body_ar if ticket.source_locale == "ar" else quick_reply.body_en

    customer = getattr(ticket, "customer", None)
    customer_name = ""
    if customer is not None:
        if ticket.source_locale == "ar":
            customer_name = customer.full_name_ar
        else:
            customer_name = customer.full_name_en or customer.full_name_ar

    agent_name = getattr(ticket, "assignee_name", None) or ""

    replacements = {
        "{{customer_name}}": customer_name,
        "{{reference_no}}": ticket.reference_no,
        "{{agent_name}}": agent_name,
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value)
    return body

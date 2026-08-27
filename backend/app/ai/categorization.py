"""Prompt template + parsing for the categorization capability (plan.md §Shared Abstractions #5 /
§Service Classes `AiService.categorize`). `AiService` owns the DB access (which categories are
eligible, writing the suggestion back); this module only builds the prompt and parses the
response, so the identical logic can be run against a live ticket's own taxonomy or against
`tests/golden/bilingual_tickets.json`'s self-contained taxonomy (T113) for the categorization
benchmark (FR-050)."""

from __future__ import annotations

import json
import re

PROMPT_VERSION = "categorize-v1"

# (key, label_ar, label_en) — key is the DB category_id (str) for a real ticket, or the golden
# set's own stable string key for a benchmark run; either way it is opaque to this module.
CategoryOption = tuple[str, str, str]


def build_prompt(subject: str, description: str, source_locale: str, options: list[CategoryOption]) -> str:
    listing = "\n".join(
        f"{index}. {label_ar} / {label_en}" for index, (_, label_ar, label_en) in enumerate(options)
    )
    return (
        "You are a support-ticket categorization assistant for a bilingual (Arabic/English) "
        "helpdesk. Choose the single best-matching category for the ticket below from the "
        "numbered list. Consider the ticket text regardless of which language it is written in.\n\n"
        f"Ticket language: {source_locale}\n"
        f"Subject: {subject}\n"
        f"Description: {description}\n\n"
        f"Categories:\n{listing}\n\n"
        'Respond with ONLY a JSON object of the exact form {"index": <integer>, "confidence": '
        "<float between 0 and 1>} — no other text, no markdown fencing."
    )


def parse_response(text: str | None, options: list[CategoryOption]) -> tuple[str | None, float | None]:
    """Never raises. Returns (None, None) on any malformed/out-of-range model output — this is
    what `AiService.categorize` treats as a fallback (leaves both suggestion columns NULL,
    FR-049) even when the call itself did not time out."""

    if not text or not options:
        return None, None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None, None
    try:
        payload = json.loads(match.group(0))
        index = int(payload["index"])
        confidence = float(payload["confidence"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None
    if not (0 <= index < len(options)) or not (0.0 <= confidence <= 1.0):
        return None, None
    return options[index][0], confidence

"""Prompt template + fallback for the ticket-summary capability (FR-045/FR-047/FR-048)."""

from __future__ import annotations

PROMPT_VERSION = "summarize-v1"

FALLBACK_CHARS = 300


def build_prompt(subject: str, description: str, source_locale: str) -> str:
    language = "Arabic" if source_locale == "ar" else "English"
    return (
        f"Summarize the following support ticket in {language}, in two to three sentences, for "
        f"an agent who is picking it up for the first time. Respond in {language} only, with the "
        "summary text alone — no preamble, no headings.\n\n"
        f"Subject: {subject}\n"
        f"Description: {description}"
    )


def fallback_summary(description: str) -> str:
    """FR-047's documented fallback when the LLM is unreachable: the first 300 characters of the
    ticket's own description."""

    return description[:FALLBACK_CHARS]

"""Prompt template + fallback for the suggested-reply capability (FR-046/FR-048). The result is
always a draft an agent reviews before sending — nothing in this module or its caller
(`AiService.suggest_reply`) ever sends anything."""

from __future__ import annotations

PROMPT_VERSION = "suggest-reply-v1"

FALLBACK_DRAFT = ""


def build_prompt(subject: str, description: str, source_locale: str) -> str:
    language = "Arabic" if source_locale == "ar" else "English"
    return (
        f"Draft a polite, professional customer-facing reply in {language} for the support "
        "ticket below. This is only a suggestion — an agent will review and edit it before "
        f"anything is sent. Respond in {language} only, with the reply body alone — no preamble, "
        "no subject line, no signature block.\n\n"
        f"Subject: {subject}\n"
        f"Description: {description}"
    )

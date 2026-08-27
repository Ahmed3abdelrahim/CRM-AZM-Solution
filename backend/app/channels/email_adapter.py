"""plan.md §Shared Abstractions #4 / PLAN.md F03 — the one functional `ChannelAdapter` this
sprint. Polls a real mailbox via `imaplib` (stdlib) and sends replies via `smtplib` (stdlib);
`ChannelService.ingest()` (Batch 4i, T122) never imports either module directly — this adapter is
the only place IMAP/SMTP protocol details live, matching how `LiteLlmWrapper` is the only module
that imports an LLM HTTP client (plan.md §Shared Abstractions #5)."""

from __future__ import annotations

import email
import imaplib
import smtplib
from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from uuid import UUID

import structlog

from app.channels.base import ChannelEnum, NormalizedAttachment, NormalizedMessage
from app.config import settings

logger = structlog.get_logger(__name__)

_ARABIC_BLOCK = range(0x0600, 0x0700)


def _decode_mime_words(raw: str | None) -> str | None:
    if not raw:
        return raw
    parts = decode_header(raw)
    decoded = "".join(
        chunk.decode(encoding or "utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        for chunk, encoding in parts
    )
    return decoded


def _detect_locale(*texts: str | None) -> str:
    for text in texts:
        for char in text or "":
            if ord(char) in _ARABIC_BLOCK:
                return "ar"
    return "en"


def _extract_body_and_attachments(message: Message) -> tuple[str, list[NormalizedAttachment]]:
    body = ""
    attachments: list[NormalizedAttachment] = []

    if message.is_multipart():
        for part in message.walk():
            content_disposition = str(part.get("Content-Disposition") or "")
            content_type = part.get_content_type()
            if "attachment" in content_disposition or (
                part.get_filename() and content_type != "text/plain"
            ):
                payload = part.get_payload(decode=True)
                attachments.append(
                    NormalizedAttachment(
                        filename=_decode_mime_words(part.get_filename()) or "attachment",
                        content_type=content_type,
                        data=payload,
                        source_url=None,
                    )
                )
            elif content_type == "text/plain" and not body:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace") if payload else ""
    else:
        payload = message.get_payload(decode=True)
        charset = message.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace") if payload else ""

    return body, attachments


class EmailAdapter:
    """`ChannelAdapter` (app/channels/base.py). `normalize()` accepts either shape raw might take:
    a `raw_message` (the exact bytes IMAP handed back, from `fetch_unseen()` below) or an
    already-normalized dict matching `NormalizedMessagePayload` — the shape `POST
    /channels/inbound` (contracts/openapi.yaml) is documented as accepting, "a pre-normalized
    payload" an external system produced itself before calling in (FR-024's whole point: the
    endpoint's caller may already know how to normalize its own channel, so `ingest()` always
    routes through `adapter.normalize()` regardless of which shape arrives)."""

    channel: ClassVar[ChannelEnum] = ChannelEnum.EMAIL

    def normalize(self, raw: dict[str, Any]) -> NormalizedMessage:
        if "raw_message" in raw:
            return self._normalize_raw_email(raw["raw_message"])
        return NormalizedMessage(
            external_id=raw["external_id"],
            channel=ChannelEnum.EMAIL,
            from_identity=raw["from_identity"],
            to_identity=raw["to_identity"],
            subject=raw.get("subject"),
            body=raw["body"],
            locale=raw["locale"],
            attachments=[],
            received_at=datetime.now(UTC),
        )

    def _normalize_raw_email(self, raw_message: bytes) -> NormalizedMessage:
        message = email.message_from_bytes(raw_message)
        subject = _decode_mime_words(message.get("Subject"))
        from_identity = email.utils.parseaddr(message.get("From", ""))[1]
        to_identity = email.utils.parseaddr(message.get("To", ""))[1]
        external_id = message.get("Message-Id") or message.get("Message-ID") or ""
        body, attachments = _extract_body_and_attachments(message)

        date_header = message.get("Date")
        try:
            received_at = parsedate_to_datetime(date_header) if date_header else datetime.now(UTC)
        except (TypeError, ValueError):
            received_at = datetime.now(UTC)

        return NormalizedMessage(
            external_id=external_id.strip("<>") or f"{from_identity}:{received_at.isoformat()}",
            channel=ChannelEnum.EMAIL,
            from_identity=from_identity,
            to_identity=to_identity,
            subject=subject,
            body=body,
            locale=_detect_locale(subject, body),
            attachments=attachments,
            received_at=received_at,
        )

    def fetch_unseen(self) -> list[dict[str, Any]]:
        """Not part of the `ChannelAdapter` protocol — `ChannelService.poll_email()` (T122) calls
        this directly on the concrete email adapter it registered, since polling is inherently
        channel-specific. Returns `[]` (never raises) when `IMAP_HOST` is unconfigured or
        unreachable — the same "degrade, never block" shape `LiteLlmWrapper` uses for an
        unreachable model (plan.md §Shared Abstractions #5)."""

        if not settings.IMAP_HOST:
            return []

        try:
            with imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT) as connection:
                connection.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
                connection.select(settings.IMAP_MAILBOX)
                status, data = connection.search(None, "UNSEEN")
                if status != "OK":
                    return []
                raw_messages: list[dict[str, Any]] = []
                for message_id in data[0].split():
                    fetch_status, fetch_data = connection.fetch(message_id, "(RFC822)")
                    if fetch_status != "OK" or not fetch_data or fetch_data[0] is None:
                        continue
                    raw_bytes = fetch_data[0][1]
                    raw_messages.append({"raw_message": raw_bytes})
                    connection.store(message_id, "+FLAGS", "\\Seen")
                return raw_messages
        except Exception as exc:  # noqa: BLE001 — a mailbox outage must never crash the poll job
            logger.warning("email_imap_poll_failed", error=str(exc))
            return []

    async def send_reply(self, ticket_id: UUID, body: str, locale: str) -> None:
        """No-op (logged) when `SMTP_HOST`/`EMAIL_FROM_ADDRESS` are unconfigured — never raises,
        matching `fetch_unseen()`'s degrade-rather-than-block shape."""

        if not settings.SMTP_HOST or not settings.EMAIL_FROM_ADDRESS:
            logger.info("email_send_reply_skipped_unconfigured", ticket_id=str(ticket_id))
            return

        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = f"Re: Ticket {ticket_id}"
        message["From"] = settings.EMAIL_FROM_ADDRESS
        message["To"] = settings.EMAIL_FROM_ADDRESS  # placeholder — no reply-to address is threaded through this batch's schema

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as connection:
                connection.starttls()
                if settings.SMTP_USER:
                    connection.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                connection.send_message(message)
        except Exception as exc:  # noqa: BLE001 — an outbound SMTP failure must never raise to the caller
            logger.warning("email_send_reply_failed", ticket_id=str(ticket_id), error=str(exc))

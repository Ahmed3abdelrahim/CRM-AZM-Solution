import time
from enum import Enum
from typing import Any
from uuid import UUID

import litellm
import structlog
from pydantic import BaseModel

from app.db import async_session_factory
from app.models.llm_call import LlmCall

logger = structlog.get_logger(__name__)


class LlmCapability(str, Enum):
    CATEGORIZE = "categorize"
    SUMMARIZE = "summarize"
    SUGGEST_REPLY = "suggest_reply"


class LlmResult(BaseModel):
    text: str | None
    structured: dict[str, Any] | None
    fallback_used: bool
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


class LiteLlmWrapper:
    """Plan.md §Shared Abstractions #5. The only module in the codebase that imports an LLM
    HTTP client; app/core/lint_no_vendor_sdk.py fails CI if any other module imports one
    directly."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_chat: str,
        model_classify: str,
        timeout_s: float = 10.0,
        max_retries: int = 1,
    ) -> None:
        self.api_base = api_base
        self.api_key = api_key
        self.model_chat = model_chat
        self.model_classify = model_classify
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    async def complete(
        self,
        capability: LlmCapability,
        prompt: str,
        prompt_version: str,
        ticket_id: UUID | None,
        correlation_id: UUID,
    ) -> LlmResult:
        """NEVER raises to the caller. On timeout, HTTP error, or retry exhaustion, returns
        LlmResult(text=None, structured=None, fallback_used=True, ...) instead of propagating.
        Every call — success or failure — inserts exactly one llm_calls row via its own
        short-lived session, committed immediately (not tied to the caller's transaction)."""
        model = self.model_classify if capability is LlmCapability.CATEGORIZE else self.model_chat
        started = time.monotonic()
        error: str | None = None
        text: str | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        fallback_used = False

        try:
            response = await litellm.acompletion(
                model=model,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout_s,
                num_retries=self.max_retries,
            )
            text = response.choices[0].message.content
            usage = getattr(response, "usage", None)
            if usage is not None:
                input_tokens = getattr(usage, "prompt_tokens", None)
                output_tokens = getattr(usage, "completion_tokens", None)
        except Exception as exc:  # noqa: BLE001 — must never raise to the caller
            fallback_used = True
            error = str(exc)
            logger.warning("llm_call_failed", capability=capability.value, error=error)

        latency_ms = int((time.monotonic() - started) * 1000)

        await self._record_call(
            ticket_id=ticket_id,
            capability=capability,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            error=error,
            correlation_id=correlation_id,
        )

        return LlmResult(
            text=text,
            structured=None,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _record_call(
        self,
        *,
        ticket_id: UUID | None,
        capability: LlmCapability,
        model: str,
        prompt_version: str,
        input_tokens: int | None,
        output_tokens: int | None,
        latency_ms: int,
        fallback_used: bool,
        error: str | None,
        correlation_id: UUID,
    ) -> None:
        async with async_session_factory() as session:
            session.add(
                LlmCall(
                    ticket_id=ticket_id,
                    capability=capability.value,
                    model=model,
                    prompt_version=prompt_version,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    fallback_used=fallback_used,
                    error=error,
                    correlation_id=correlation_id,
                )
            )
            await session.commit()

import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.exceptions import (
    AIProviderNotConfiguredError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AIResponseValidationError,
)
from app.services.ai.prompts.templates import (
    SYSTEM_GUARDRAIL,
    classify_prompt,
    compare_prompt,
    extract_prompt,
    order_prompt,
    suggest_filename_prompt,
    summarize_prompt,
)
from app.services.ai.schemas import (
    ClassificationResult,
    ComparisonResult,
    DocumentOrderInput,
    ExtractionResult,
    FilenameSuggestionResult,
    OrderSuggestionResult,
    SummaryResult,
)
from app.services.ai.usage_tracker import usage_tracker

logger = logging.getLogger("documenthub.ai.openrouter")

TModel = TypeVar("TModel", bound=BaseModel)


def _strip_markdown_fences(raw: str) -> str:
    """Remove optional ```json ... ``` wrappers from model output."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return text


class OpenRouterProvider(AIProvider):
    """OpenRouter implementation of the abstract AIProvider contract."""

    provider_name = "openrouter"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def _call_chat_completion(self, user_prompt: str, schema: type[TModel]) -> TModel:
        if not settings.openrouter_api_key.strip():
            raise AIProviderNotConfiguredError(
                "OPENROUTER_API_KEY is not configured on the server."
            )

        usage_tracker.check_and_increment()

        url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://documenthub.app",
            "X-Title": "DocumentHub",
        }
        payload = {
            "model": settings.openrouter_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_GUARDRAIL},
                {"role": "user", "content": user_prompt},
            ],
        }

        last_exc: Exception | None = None
        for attempt in range(settings.ai_max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.ai_timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(url, headers=headers, json=payload)

                # Never log API keys or document text; log only status & attempt.
                logger.info(
                    "OpenRouter call model=%s status=%s attempt=%s",
                    settings.openrouter_model,
                    response.status_code,
                    attempt + 1,
                )

                if response.status_code == 429:
                    if attempt < settings.ai_max_retries:
                        continue
                    raise AIRateLimitError("OpenRouter rate limit reached. Please try again later.")

                if response.status_code >= 500:
                    if attempt < settings.ai_max_retries:
                        continue
                    raise AIProviderUnavailableError("OpenRouter service is temporarily unavailable.")

                if response.status_code >= 400:
                    raise AIProviderUnavailableError(
                        f"OpenRouter rejected the request (HTTP {response.status_code})."
                    )

                body = response.json()
                raw_content = body["choices"][0]["message"]["content"]
                parsed = json.loads(_strip_markdown_fences(raw_content))
                if isinstance(parsed, dict):
                    parsed["model_used"] = settings.openrouter_model
                return schema.model_validate(parsed)

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < settings.ai_max_retries:
                    continue
                raise AIProviderUnavailableError("Timed out waiting for OpenRouter.") from exc
            except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
                raise AIResponseValidationError(
                    "AI provider returned an invalid or unexpected response format."
                ) from exc

        raise AIProviderUnavailableError("OpenRouter request failed.") from last_exc

    async def summarize_document(self, text: str) -> SummaryResult:
        prompt, truncated = summarize_prompt(text, settings.ai_max_input_chars)
        result = await self._call_chat_completion(prompt, SummaryResult)
        result.truncated = truncated
        return result

    async def classify_document(self, text: str) -> ClassificationResult:
        prompt = classify_prompt(text, settings.ai_max_input_chars)
        return await self._call_chat_completion(prompt, ClassificationResult)

    async def extract_information(self, text: str) -> ExtractionResult:
        prompt = extract_prompt(text, settings.ai_max_input_chars)
        return await self._call_chat_completion(prompt, ExtractionResult)

    async def suggest_filename(self, text: str, current_filename: str = "") -> FilenameSuggestionResult:
        prompt = suggest_filename_prompt(text, current_filename, settings.ai_max_input_chars)
        return await self._call_chat_completion(prompt, FilenameSuggestionResult)

    async def compare_documents(self, text_a: str, text_b: str) -> ComparisonResult:
        prompt = compare_prompt(text_a, text_b, settings.ai_max_input_chars)
        return await self._call_chat_completion(prompt, ComparisonResult)

    async def suggest_document_order(self, documents: list[DocumentOrderInput]) -> OrderSuggestionResult:
        summary_lines = "\n".join(
            f"- id={d.id} | filename={d.filename} | snippet={d.summary_or_snippet[:300]}"
            for d in documents
        )
        prompt = order_prompt(summary_lines)
        return await self._call_chat_completion(prompt, OrderSuggestionResult)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.services.ai.ai_factory import get_ai_provider
from app.services.ai.exceptions import (
    AIProviderNotConfiguredError,
    AIProviderUnavailableError,
    AIQuotaExceededError,
    AIRateLimitError,
    AIResponseValidationError,
    AIServiceError,
)
from app.services.ai.schemas import DocumentOrderInput
from app.services.ai.usage_tracker import usage_tracker

router = APIRouter(prefix="/api/v1/ai", tags=["AI Assistant"])


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100_000)


class FilenameRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100_000)
    current_filename: str = ""


class CompareRequest(BaseModel):
    text_a: str = Field(..., min_length=1, max_length=100_000)
    text_b: str = Field(..., min_length=1, max_length=100_000)


class OrderRequest(BaseModel):
    documents: list[DocumentOrderInput] = Field(..., min_length=2, max_length=20)


def _raise_http_for_ai_error(exc: AIServiceError) -> None:
    if isinstance(exc, (AIProviderNotConfiguredError, AIProviderUnavailableError)):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if isinstance(exc, (AIRateLimitError, AIQuotaExceededError)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    if isinstance(exc, AIResponseValidationError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/status")
async def ai_status() -> dict:
    """Report AI provider status, remaining daily quota, and external privacy disclosure."""
    provider_name = settings.ai_provider.strip().lower()
    configured = provider_name == "mock" or bool(settings.openrouter_api_key.strip())
    return {
        "provider": provider_name,
        "configured": configured,
        "model": settings.openrouter_model if provider_name == "openrouter" else "mock-local-v1",
        "usage": usage_tracker.get_status(),
        "privacy_disclosure": (
            "AI outputs are suggestions only and require your approval. "
            "When using OpenRouter, minimized text is sent externally over HTTPS."
        ),
    }


@router.post("/summarize")
async def summarize_endpoint(
    payload: TextRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().summarize_document(payload.text)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)


@router.post("/classify")
async def classify_endpoint(
    payload: TextRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().classify_document(payload.text)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)


@router.post("/extract")
async def extract_endpoint(
    payload: TextRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().extract_information(payload.text)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)


@router.post("/suggest-filename")
async def suggest_filename_endpoint(
    payload: FilenameRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().suggest_filename(payload.text, payload.current_filename)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)


@router.post("/compare")
async def compare_endpoint(
    payload: CompareRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().compare_documents(payload.text_a, payload.text_b)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)


@router.post("/suggest-order")
async def suggest_order_endpoint(
    payload: OrderRequest,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
):
    try:
        return await get_ai_provider().suggest_document_order(payload.documents)
    except AIServiceError as exc:
        _raise_http_for_ai_error(exc)

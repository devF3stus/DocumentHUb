from app.core.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.exceptions import AIProviderNotConfiguredError
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.openrouter_provider import OpenRouterProvider


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Return the configured AIProvider implementation without coupling callers to OpenRouter."""
    selected = (provider_name or settings.ai_provider).strip().lower()
    if selected == "openrouter":
        return OpenRouterProvider()
    if selected == "mock":
        return MockAIProvider()
    raise AIProviderNotConfiguredError(f"Unknown AI provider '{selected}'.")

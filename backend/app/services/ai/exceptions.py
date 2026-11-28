class AIServiceError(Exception):
    """Base exception for all AI service failures."""


class AIProviderNotConfiguredError(AIServiceError):
    """Raised when the selected AI provider lacks required credentials or config."""


class AIRateLimitError(AIServiceError):
    """Raised when the external AI provider returns a rate limit (429)."""


class AIQuotaExceededError(AIServiceError):
    """Raised when DocumentHub's internal daily AI usage quota is reached."""


class AIResponseValidationError(AIServiceError):
    """Raised when the AI provider returns malformed or unparseable output."""


class AIProviderUnavailableError(AIServiceError):
    """Raised when the external AI provider times out or returns 5xx errors."""

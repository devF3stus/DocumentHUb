from abc import ABC, abstractmethod

from app.services.ai.schemas import (
    ClassificationResult,
    ComparisonResult,
    DocumentOrderInput,
    ExtractionResult,
    FilenameSuggestionResult,
    OrderSuggestionResult,
    SummaryResult,
)


class AIProvider(ABC):
    """Common contract that every AI provider must implement."""

    provider_name: str = "base"

    @abstractmethod
    async def summarize_document(self, text: str) -> SummaryResult:
        """Return a concise summary and bullet key points."""

    @abstractmethod
    async def classify_document(self, text: str) -> ClassificationResult:
        """Classify the document into a category (e.g. CV, Invoice, Certificate)."""

    @abstractmethod
    async def extract_information(self, text: str) -> ExtractionResult:
        """Extract key entities, dates, and monetary amounts."""

    @abstractmethod
    async def suggest_filename(self, text: str, current_filename: str = "") -> FilenameSuggestionResult:
        """Suggest a clean, descriptive filename (suggestion only)."""

    @abstractmethod
    async def compare_documents(self, text_a: str, text_b: str) -> ComparisonResult:
        """Compare two documents for similarities, differences, and formatting inconsistencies."""

    @abstractmethod
    async def suggest_document_order(self, documents: list[DocumentOrderInput]) -> OrderSuggestionResult:
        """Recommend an optimal ordering for a set of documents."""

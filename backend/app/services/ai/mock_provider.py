import re

from app.services.ai.base import AIProvider
from app.services.ai.schemas import (
    ClassificationResult,
    ComparisonResult,
    DocumentOrderInput,
    ExtractionResult,
    FilenameSuggestionResult,
    OrderedDocumentItem,
    OrderSuggestionResult,
    SummaryResult,
)
from app.services.ai.usage_tracker import usage_tracker


class MockAIProvider(AIProvider):
    """Deterministic offline AI provider used for tests and provider-swap demos."""

    provider_name = "mock"

    async def summarize_document(self, text: str) -> SummaryResult:
        usage_tracker.check_and_increment()
        clean = " ".join(text.split())
        snippet = clean[:180] + ("..." if len(clean) > 180 else "")
        return SummaryResult(
            summary=f"Mock summary: {snippet}",
            key_points=["Offline deterministic summary", f"Character count: {len(clean)}"],
            model_used="mock-local-v1",
            truncated=False,
        )

    async def classify_document(self, text: str) -> ClassificationResult:
        usage_tracker.check_and_increment()
        lower = text.lower()
        if "curriculum vitae" in lower or "experience" in lower or "resume" in lower:
            category = "CV/Resume"
        elif "invoice" in lower or "total due" in lower:
            category = "Invoice"
        elif "certificate" in lower or "degree" in lower:
            category = "Academic Certificate"
        else:
            category = "General Document"
        return ClassificationResult(
            category=category,
            confidence=0.88,
            reasoning="Matched deterministic keyword heuristics (mock provider).",
            model_used="mock-local-v1",
        )

    async def extract_information(self, text: str) -> ExtractionResult:
        usage_tracker.check_and_increment()
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        amounts = re.findall(r"\$\d+(?:,\d{3})*(?:\.\d{2})?", text)
        return ExtractionResult(
            document_type="Document",
            entities=[],
            dates=dates[:5],
            amounts=amounts[:5],
            model_used="mock-local-v1",
        )

    async def suggest_filename(self, text: str, current_filename: str = "") -> FilenameSuggestionResult:
        usage_tracker.check_and_increment()
        words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", text)[:4]]
        slug = "-".join(words) if words else "document"
        return FilenameSuggestionResult(
            suggested_filename=f"{slug}-processed",
            alternatives=[f"{slug}-v1", "documenthub-export"],
            model_used="mock-local-v1",
        )

    async def compare_documents(self, text_a: str, text_b: str) -> ComparisonResult:
        usage_tracker.check_and_increment()
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        common = sorted(words_a & words_b)[:5]
        return ComparisonResult(
            similarities=[f"Shared terms: {', '.join(common)}"] if common else ["No shared words"],
            differences=[f"Length difference: {abs(len(text_a) - len(text_b))} chars"],
            inconsistencies=[],
            model_used="mock-local-v1",
        )

    async def suggest_document_order(self, documents: list[DocumentOrderInput]) -> OrderSuggestionResult:
        usage_tracker.check_and_increment()
        ordered = [
            OrderedDocumentItem(
                id=doc.id,
                filename=doc.filename,
                position=idx,
                reason="Ordered deterministically by mock provider.",
            )
            for idx, doc in enumerate(documents, start=1)
        ]
        return OrderSuggestionResult(
            ordered_documents=ordered,
            rationale="Preserved input sequence (mock provider).",
            model_used="mock-local-v1",
        )

from pydantic import BaseModel, Field


class SummaryResult(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    model_used: str = ""
    truncated: bool = False


class ClassificationResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    model_used: str = ""


class ExtractionResult(BaseModel):
    document_type: str
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    amounts: list[str] = Field(default_factory=list)
    model_used: str = ""


class FilenameSuggestionResult(BaseModel):
    suggested_filename: str
    alternatives: list[str] = Field(default_factory=list)
    model_used: str = ""


class ComparisonResult(BaseModel):
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    model_used: str = ""


class DocumentOrderInput(BaseModel):
    id: str
    filename: str
    summary_or_snippet: str


class OrderedDocumentItem(BaseModel):
    id: str
    filename: str
    position: int
    reason: str = ""


class OrderSuggestionResult(BaseModel):
    ordered_documents: list[OrderedDocumentItem] = Field(default_factory=list)
    rationale: str = ""
    model_used: str = ""

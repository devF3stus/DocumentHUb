# DocumentHub — Independent AI Service Architecture

## 1. Core Architectural Rule
The AI service (`backend/app/services/ai/`) is **completely decoupled** from PDF, Word, OCR, database, and frontend code. Core document tools never depend on AI.

## 2. Provider Abstraction Pattern
- **`base.py` (`AIProvider`):** Defines the contract (`summarize_document`, `classify_document`, `extract_information`, `suggest_filename`, `compare_documents`, `suggest_document_order`).
- **`openrouter_provider.py`:** Default implementation calling OpenRouter over HTTPS with timeouts, bounded retries, and Pydantic response validation.
- **`mock_provider.py`:** Offline deterministic implementation proving any provider can replace OpenRouter without touching callers.
- **`ai_factory.py`:** Selects the active provider from `AI_PROVIDER` in `.env`.

### How to Add Another AI Provider Later
1. Create `backend/app/services/ai/my_provider.py` subclassing `AIProvider`.
2. Implement the 6 contract methods returning the Pydantic schemas in `schemas.py`.
3. Register it in `ai_factory.py` and set `AI_PROVIDER=my_provider` in `.env`.

## 3. AI Security & Privacy Controls
- `OPENROUTER_API_KEY` is strictly server-side (`backend/.env`).
- Document text is minimized (`AI_MAX_INPUT_CHARS`) and wrapped in `<untrusted_document>` delimiters with a system guardrail against prompt injection.
- Responses are validated against Pydantic schemas and never executed as code.
- Logs record model and HTTP status only—never API keys or document contents.

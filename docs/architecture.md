# DocumentHub — System Architecture

## 1. High-Level Architecture
DocumentHub uses a **decoupled client-server architecture** across four specialized services:

- **Frontend (Next.js on Vercel):** Renders the UI, handles drag-and-drop uploads, previews, and downloads. Contains **zero** secret keys and performs **no** authoritative security checks.
- **Backend (FastAPI + Docker on Render):** Validates uploaded files, runs PDF/Word/OCR processing in isolated temporary directories, enforces rate limits, and coordinates with Supabase and the AI service.
- **Database & Auth (Supabase PostgreSQL & Auth):** Manages optional user accounts (guest access supported for basic tools), job metadata, and Row Level Security (RLS).
- **Storage (Supabase Storage):** Private buckets for temporary/user files, accessed only via short-lived signed URLs and cleaned up automatically.
- **Independent AI Service (OpenRouter behind `AIProvider`):** Isolated under `backend/app/services/ai/`. The rest of the application communicates only with the abstract interface (`base.py`), never directly with OpenRouter.

## 2. Communication Flow
1. **Browser <-> Vercel:** HTTPS loads the Next.js web application.
2. **Browser <-> Supabase Auth:** Optional sign-in issues a JWT token.
3. **Browser <-> Render (FastAPI):** Frontend uploads files directly to FastAPI (avoiding Vercel's ~4.5 MB serverless payload limit) and sends the JWT in the `Authorization` header when logged in.
4. **Render <-> Supabase:** Backend validates ownership, logs job metadata, stores/fetches files in private buckets, and issues short-lived signed download URLs.
5. **Render <-> OpenRouter:** Only when an AI feature is requested, FastAPI's AI service sends minimized text over HTTPS using a server-side API key.

## 3. Proposed Repository Structure
```text
documenthub/
├── .github/workflows/       # PR compare CI & Release Please automation
├── frontend/                # Next.js + React + TypeScript + Tailwind CSS
├── backend/                 # Python + FastAPI + Docker
│   ├── app/
│   │   ├── api/             # HTTP route handlers
│   │   ├── core/            # Config, security, logging, rate limiting
│   │   ├── models/          # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── pdf/         # PDF processing
│   │   │   ├── word/        # Word & LibreOffice conversions
│   │   │   ├── ocr/         # OpenCV + Tesseract OCR
│   │   │   ├── storage/     # Supabase storage & temp cleanup
│   │   │   └── ai/          # Independent AI abstraction
│   │   │       ├── base.py
│   │   │       ├── openrouter_provider.py
│   │   │       ├── ai_factory.py
│   │   │       ├── schemas.py
│   │   │       ├── prompts/
│   │       │       └── exceptions.py
│   │   └── main.py
│   ├── tests/
│   └── Dockerfile
└── docs/                    # Architecture, security, learning notes & phase reports
```

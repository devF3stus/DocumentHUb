# DocumentHub — Security & Privacy Architecture

DocumentHub handles potentially sensitive user documents. Security is built in layers (**Defense in Depth**). No system is 100% immune to attack; our goal is to minimize risk, contain failures, and be transparent about residual risks.

## 1. File Upload Security
- **Never trust the frontend or file extensions:** Attackers can rename `.exe` to `.pdf` or bypass the browser UI using `curl`.
- **Server-side validation:** Every upload is checked on the FastAPI backend for:
  - Allowed extension & MIME type
  - **Magic-byte / file-signature verification** (e.g., `%PDF-` for PDFs, `MZ` rejected)
  - Strict file-size and page-count limits (preventing decompression bombs and memory exhaustion)
- **Safe storage & paths:** Files are renamed with server-generated random UUIDs and processed inside isolated temporary directories to prevent path traversal (`../`).

## 2. Storage & Cleanup Security
- Private Supabase Storage buckets only (no public document URLs).
- Short-lived signed download URLs.
- Automatic deletion of temporary files immediately after processing—including when processing fails.

## 3. API & Database Security
- **HTTPS** everywhere in production.
- **CORS** restricted to our trusted frontend origin.
- **Rate limiting** to prevent abuse and resource exhaustion.
- **Supabase Row Level Security (RLS):** Enforced in PostgreSQL so users can only access their own records, even if an API bug occurs.
- **Safe logging:** Never log API keys, JWTs, passwords, or full document contents.

## 4. AI Security & Privacy
- **Server-side keys only:** OpenRouter API keys never exist in frontend code.
- **Untrusted data & Prompt Injection:** Uploaded document text is treated strictly as untrusted data, never as system instructions. AI outputs are schema-validated and never executed as code.
- **Data minimization & disclosure:** Only necessary text is sent to OpenRouter, and users are informed before external AI processing occurs.

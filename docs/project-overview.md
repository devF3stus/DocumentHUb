# DocumentHub — Project Overview & Roadmap

## 1. Product Vision
**DocumentHub** is a free, browser-based intelligent document processing platform. Users can upload, convert, merge, split, organize, OCR-scan, and optionally AI-analyze documents without installing desktop software or paying for subscriptions.

## 2. Target Audience
- Students & educators
- Professionals & researchers
- Small businesses & educational institutions
- General internet users

## 3. Core Functionalities
1. **PDF Engine:** Merge, split, extract/delete/rearrange/rotate pages, compress, PDF-to-image, image extraction, password protection & unlocking (with user-supplied password).
2. **Document Conversion & Word Management:** DOCX <-> PDF, DOCX <-> TXT/HTML, Image <-> PDF, Word merging & formatting-aware generation.
3. **OCR Studio:** Preprocess scanned images/PDFs (deskew, denoise, orient) with OpenCV and recognize text with Tesseract, with side-by-side review and export to DOCX, TXT, and searchable PDF.
4. **Independent AI Assistant (Optional):** Summarize, classify, extract info, suggest filenames, compare documents, and suggest document ordering. Always presented as user-approved suggestions; never required for core operations.
5. **Smart Workflows:** Multi-document pipelines (e.g., CV + certificates + ID + letter -> classify -> rename -> order -> merge into one PDF).

## 4. Pricing & Resource Philosophy
- **100% Free:** No subscriptions, paywalls, or payment gateways.
- **Abuse Prevention:** File size limits, page limits, rate limiting, and transparent AI usage quotas keep hosting costs sustainable.

## 5. Development Roadmap
- **Phase 0:** Project Discovery & Architecture *(Current)*
- **Phase 1:** Development Environment & Project Foundation (Next.js, FastAPI, Docker, Git/CI)
- **Phase 2:** Database, Authentication & Private File Storage (Supabase + RLS + Upload Security)
- **Phase 3:** Core PDF Engine
- **Phase 4:** Document Conversion & Word Processing (LibreOffice, python-docx)
- **Phase 5:** OCR Studio (OpenCV + Tesseract)
- **Phase 6:** Independent AI Service (OpenRouter behind abstract provider)
- **Phase 7:** Smart Document Workflows & Background Jobs
- **Phase 8:** Security Hardening & Performance Review
- **Phase 9:** Deployment & Production Readiness (Vercel + Render + Supabase)

# DocumentHub — Technology Stack & Justifications

| Layer | Choice | Why We Chose It | Hosting / Runtime |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS | Fast, responsive UI with strong type safety (TypeScript) to catch bugs early and clean utility styling (Tailwind). | Vercel |
| **Backend** | Python, FastAPI, Docker | Python has the strongest ecosystem for PDF, Word, OpenCV, and OCR. FastAPI gives automatic validation, async support, and clear API docs. Docker guarantees identical Linux environments locally and on Render. | Render |
| **Database & Auth** | Supabase (PostgreSQL, Auth, Storage) | Free-tier friendly relational database with built-in authentication, private file buckets, and Row Level Security (RLS). | Supabase Cloud |
| **PDF Processing** | `pypdf`, `PyMuPDF`, `pdfplumber` | Installed progressively as needed: `pypdf` for merge/split/rotate, `PyMuPDF` for fast rendering & compression, `pdfplumber` for structured extraction. | Backend Docker |
| **Word & Conversion** | `python-docx`, `docxcompose`, `mammoth`, LibreOffice | Industry-standard open-source tools for reading, generating, merging, and converting `.docx` files. | Backend Docker |
| **OCR & Imaging** | OpenCV, Pillow, Tesseract OCR | OpenCV/Pillow clean, deskew, and denoise scanned pages; Tesseract extracts text and produces searchable PDFs. | Backend Docker |
| **AI Service** | OpenRouter (via `AIProvider` interface) | Access to multiple models behind one API, isolated behind `base.py` so any other provider can replace it without touching core app logic. | External HTTPS API |

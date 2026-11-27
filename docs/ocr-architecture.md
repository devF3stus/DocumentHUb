# DocumentHub — OCR Studio Architecture

## 1. Pipeline Overview
1. **Upload Validation:** Accepts `.jpg`, `.jpeg`, `.png`, `.tiff`/`.tif`, and `.pdf` via `validate_upload` (extension, MIME, magic bytes, size limit).
2. **Page Extraction (`extract_images_from_upload`):**
   - Scanned PDFs are rendered to PNG pages using `PyMuPDF` (enforcing `MAX_PDF_PAGES`).
   - Multi-frame TIFFs and standard images are normalized to PNG frames using `Pillow`.
3. **OpenCV Preprocessing (`preprocess_image`):**
   - Converts to grayscale, denoises (`medianBlur`), detects & corrects tilt angle (deskew), and applies adaptive thresholding for crisp black-on-white text.
4. **Tesseract Recognition (`run_ocr` & `generate_searchable_pdf`):**
   - Validates language against an explicit allowlist (`eng`, `fra`, `deu`, `spa`, `por`, `ita`).
   - Extracts per-page text and word confidence scores (`0–100%`).
   - Optionally generates a multi-page searchable PDF with an invisible text layer.
5. **Human-in-the-Loop Review:** Users inspect side-by-side preview + extracted text and fix any recognition errors before exporting to `.txt` or `.docx`.

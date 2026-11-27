from dataclasses import dataclass
from io import BytesIO
import shutil

import cv2
from fastapi import HTTPException, status
import fitz
import numpy as np
from PIL import Image, ImageSequence, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
import pytesseract
from pytesseract import Output

from app.core.config import settings

SUPPORTED_OCR_LANGUAGES: set[str] = {"eng", "fra", "deu", "spa", "por", "ita"}


@dataclass(frozen=True)
class OcrPageResult:
    """Extracted text and confidence score for a single page."""

    page_number: int
    text: str
    confidence: float


@dataclass(frozen=True)
class OcrDocumentResult:
    """Aggregated OCR result across all pages of an uploaded document."""

    pages: list[OcrPageResult]
    full_text: str
    average_confidence: float
    language: str


def _validate_language(language: str) -> str:
    lang = language.strip().lower()
    if lang not in SUPPORTED_OCR_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OCR language '{language}'. Supported: {sorted(SUPPORTED_OCR_LANGUAGES)}.",
        )
    return lang


def _require_tesseract() -> None:
    if not shutil.which("tesseract"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tesseract OCR is not installed in this environment (included in Docker production build).",
        )


def preprocess_image(image_bytes: bytes) -> bytes:
    """Clean a scanned image (grayscale, denoise, deskew, adaptive threshold) for higher OCR accuracy."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode image for OCR preprocessing.",
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.medianBlur(gray, 3)

    # Estimate skew angle from foreground pixels and deskew if tilted > 0.5 degrees.
    coords = np.column_stack(np.where(denoised < 200))
    if len(coords) > 20:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if 0.5 < abs(angle) < 45:
            h, w = denoised.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            denoised = cv2.warpAffine(
                denoised,
                matrix,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    ok, encoded = cv2.imencode(".png", binary)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encode preprocessed image.",
        )
    return encoded.tobytes()


def extract_images_from_upload(data: bytes, extension: str, dpi: int = 200) -> list[bytes]:
    """Convert an uploaded scanned PDF or image (including multi-page TIFF) into PNG page bytes."""
    ext = extension.lower()
    if ext == ".pdf":
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted PDF file.",
            ) from exc
        try:
            if doc.needs_pass:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please unlock the PDF before running OCR.",
                )
            if doc.page_count == 0 or doc.page_count > settings.max_pdf_pages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF page count must be between 1 and {settings.max_pdf_pages}.",
                )
            return [doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png") for i in range(doc.page_count)]
        finally:
            doc.close()

    # Handle PNG, JPG, JPEG, and single/multi-frame TIFF via Pillow.
    try:
        with Image.open(BytesIO(data)) as img:
            pages: list[bytes] = []
            for frame in ImageSequence.Iterator(img):
                if len(pages) >= settings.max_pdf_pages:
                    break
                buf = BytesIO()
                frame.convert("RGB").save(buf, format="PNG")
                pages.append(buf.getvalue())
            if not pages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image contains no readable frames.",
                )
            return pages
    except HTTPException:
        raise
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file.",
        ) from exc


def run_ocr(
    data: bytes,
    extension: str,
    language: str = "eng",
    preprocess: bool = True,
) -> OcrDocumentResult:
    """Run OpenCV preprocessing + Tesseract OCR across all pages of a document."""
    lang = _validate_language(language)
    _require_tesseract()

    page_images = extract_images_from_upload(data, extension)
    results: list[OcrPageResult] = []

    for idx, raw_png in enumerate(page_images, start=1):
        img_bytes = preprocess_image(raw_png) if preprocess else raw_png
        with Image.open(BytesIO(img_bytes)) as pil_img:
            ocr_data = pytesseract.image_to_data(pil_img, lang=lang, output_type=Output.DICT)
            text = pytesseract.image_to_string(pil_img, lang=lang).strip()

        confidences = [
            float(c)
            for c in ocr_data.get("conf", [])
            if str(c).lstrip("-").isdigit() and int(c) >= 0
        ]
        avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else 0.0
        results.append(OcrPageResult(page_number=idx, text=text, confidence=avg_conf))

    full_text = "\n\n".join(p.text for p in results if p.text)
    overall_conf = (
        round(sum(p.confidence for p in results) / len(results), 1) if results else 0.0
    )
    return OcrDocumentResult(
        pages=results,
        full_text=full_text,
        average_confidence=overall_conf,
        language=lang,
    )


def generate_searchable_pdf(
    data: bytes,
    extension: str,
    language: str = "eng",
    preprocess: bool = True,
) -> bytes:
    """Create a multi-page searchable PDF with an invisible OCR text layer."""
    lang = _validate_language(language)
    _require_tesseract()

    page_images = extract_images_from_upload(data, extension)
    writer = PdfWriter()

    for raw_png in page_images:
        img_bytes = preprocess_image(raw_png) if preprocess else raw_png
        with Image.open(BytesIO(img_bytes)) as pil_img:
            pdf_page_bytes = pytesseract.image_to_pdf_or_hocr(pil_img, lang=lang, extension="pdf")
        reader = PdfReader(BytesIO(pdf_page_bytes))
        for page in reader.pages:
            writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()

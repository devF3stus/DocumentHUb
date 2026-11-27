import asyncio
from io import BytesIO

import fitz
import httpx
from PIL import Image, ImageDraw
import pytest

from app.main import app
from app.services.ocr import ocr_service
from app.services.word import word_service


def _make_sample_png_with_text() -> bytes:
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 280, 80], outline=(0, 0, 0), width=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    img.close()
    return buf.getvalue()


def _make_sample_tiff() -> bytes:
    img = Image.new("RGB", (100, 60), color=(240, 240, 240))
    buf = BytesIO()
    img.save(buf, format="TIFF")
    img.close()
    return buf.getvalue()


def _make_scanned_pdf(pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(1, pages + 1):
        page = doc.new_page(width=300, height=300)
        page.insert_text((40, 80), f"Scan Page {i}", fontsize=16)
    data = doc.tobytes()
    doc.close()
    return data


async def _post(
    endpoint: str,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    data: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(endpoint, files=files, data=data)


def test_opencv_preprocess_and_tiff_extraction() -> None:
    png_bytes = _make_sample_png_with_text()
    cleaned = ocr_service.preprocess_image(png_bytes)
    assert cleaned.startswith(b"\x89PNG\r\n\x1a\n")

    tiff_bytes = _make_sample_tiff()
    frames = ocr_service.extract_images_from_upload(tiff_bytes, ".tiff")
    assert len(frames) == 1
    assert frames[0].startswith(b"\x89PNG\r\n\x1a\n")


def test_pdf_page_extraction_for_ocr() -> None:
    pdf_bytes = _make_scanned_pdf(pages=2)
    pages = ocr_service.extract_images_from_upload(pdf_bytes, ".pdf", dpi=100)
    assert len(pages) == 2
    assert all(p.startswith(b"\x89PNG\r\n\x1a\n") for p in pages)


def test_invalid_ocr_language_rejected_with_400() -> None:
    png_bytes = _make_sample_png_with_text()
    res = asyncio.run(
        _post(
            "/api/v1/ocr/extract",
            files=[("file", ("scan.png", png_bytes, "image/png"))],
            data={"language": "eng; rm -rf /"},
        )
    )
    assert res.status_code == 400


def test_ocr_returns_503_when_tesseract_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    png_bytes = _make_sample_png_with_text()
    res = asyncio.run(
        _post(
            "/api/v1/ocr/extract",
            files=[("file", ("scan.png", png_bytes, "image/png"))],
        )
    )
    assert res.status_code == 503


def test_ocr_extract_and_searchable_pdf_with_mock_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tesseract" if name == "tesseract" else None)
    monkeypatch.setattr(
        "pytesseract.image_to_data",
        lambda _img, lang, output_type: {"conf": ["95", "90", "-1"]},
    )
    monkeypatch.setattr(
        "pytesseract.image_to_string",
        lambda _img, lang: "DocumentHub Invoice #102",
    )

    sample_pdf = _make_scanned_pdf(pages=2)
    monkeypatch.setattr(
        "pytesseract.image_to_pdf_or_hocr",
        lambda _img, lang, extension: _make_scanned_pdf(pages=1),
    )

    extract_res = asyncio.run(
        _post(
            "/api/v1/ocr/extract",
            files=[("file", ("scan.pdf", sample_pdf, "application/pdf"))],
            data={"language": "eng", "preprocess": "true"},
        )
    )
    assert extract_res.status_code == 200
    body = extract_res.json()
    assert body["average_confidence"] == 92.5
    assert len(body["pages"]) == 2
    assert "DocumentHub Invoice #102" in body["full_text"]

    searchable_res = asyncio.run(
        _post(
            "/api/v1/ocr/searchable-pdf",
            files=[("file", ("scan.pdf", sample_pdf, "application/pdf"))],
            data={"language": "eng"},
        )
    )
    assert searchable_res.status_code == 200
    assert searchable_res.content.startswith(b"%PDF-")


def test_ocr_export_corrected_text_to_txt_and_docx() -> None:
    txt_res = asyncio.run(
        _post(
            "/api/v1/ocr/export",
            data={"text": "Corrected OCR text.", "export_format": "txt"},
        )
    )
    assert txt_res.status_code == 200
    assert txt_res.text == "Corrected OCR text."

    docx_res = asyncio.run(
        _post(
            "/api/v1/ocr/export",
            data={"text": "Corrected OCR text.", "export_format": "docx", "title": "OCR Scan"},
        )
    )
    assert docx_res.status_code == 200
    assert docx_res.content.startswith(b"PK\x03\x04")
    assert "Corrected OCR text." in word_service.extract_docx_text(docx_res.content)

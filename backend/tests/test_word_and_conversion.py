import asyncio
from io import BytesIO
from pathlib import Path
import subprocess

from docx import Document
import fitz
import httpx
from PIL import Image
from pypdf import PdfReader
import pytest

from app.main import app
from app.services.word import word_service

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_sample_docx(heading: str, paragraph: str) -> bytes:
    doc = Document()
    doc.add_heading(heading, level=1)
    doc.add_paragraph(paragraph)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Col1"
    table.rows[0].cells[1].text = "Col2"
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_sample_png() -> bytes:
    img = Image.new("RGB", (60, 40), color=(20, 120, 220))
    buf = BytesIO()
    img.save(buf, format="PNG")
    img.close()
    return buf.getvalue()


def _make_sample_pdf(text: str = "Hello DocumentHub") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((50, 100), text, fontsize=16)
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


def test_merge_docx_and_extract_text() -> None:
    doc1 = _make_sample_docx("Part One", "First document body.")
    doc2 = _make_sample_docx("Part Two", "Second document body.")

    merged = asyncio.run(
        _post(
            "/api/v1/word/merge",
            files=[
                ("files", ("one.docx", doc1, DOCX_MIME)),
                ("files", ("two.docx", doc2, DOCX_MIME)),
            ],
        )
    )
    assert merged.status_code == 200
    extracted = word_service.extract_docx_text(merged.content)
    assert "First document body." in extracted
    assert "Second document body." in extracted
    assert "Col1 | Col2" in extracted


def test_generate_word_and_docx_to_txt_and_html() -> None:
    generated = asyncio.run(
        _post(
            "/api/v1/word/generate",
            data={"title": "Study Notes", "text": "Line 1\nLine 2"},
        )
    )
    assert generated.status_code == 200

    txt_res = asyncio.run(
        _post(
            "/api/v1/convert/docx-to-txt",
            files=[("file", ("notes.docx", generated.content, DOCX_MIME))],
        )
    )
    assert txt_res.status_code == 200
    assert "Study Notes" in txt_res.text
    assert "Line 2" in txt_res.text

    html_res = asyncio.run(
        _post(
            "/api/v1/convert/docx-to-html",
            files=[("file", ("notes.docx", generated.content, DOCX_MIME))],
        )
    )
    assert html_res.status_code == 200
    assert "<h1>Study Notes</h1>" in html_res.text


def test_txt_to_docx_and_txt_to_pdf() -> None:
    txt_bytes = b"Hello from plain text.\nSecond line."

    docx_res = asyncio.run(
        _post(
            "/api/v1/convert/txt-to-docx",
            files=[("file", ("note.txt", txt_bytes, "text/plain"))],
            data={"title": "Imported"},
        )
    )
    assert docx_res.status_code == 200
    assert "Hello from plain text." in word_service.extract_docx_text(docx_res.content)

    pdf_res = asyncio.run(
        _post(
            "/api/v1/convert/txt-to-pdf",
            files=[("file", ("note.txt", txt_bytes, "text/plain"))],
        )
    )
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(pdf_res.content)).pages) == 1


def test_images_to_pdf() -> None:
    png1 = _make_sample_png()
    png2 = _make_sample_png()
    res = asyncio.run(
        _post(
            "/api/v1/convert/images-to-pdf",
            files=[
                ("files", ("a.png", png1, "image/png")),
                ("files", ("b.png", png2, "image/png")),
            ],
        )
    )
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(res.content)).pages) == 2


def test_pdf_to_docx() -> None:
    pdf_bytes = _make_sample_pdf("Digital PDF Content")
    res = asyncio.run(
        _post(
            "/api/v1/convert/pdf-to-docx",
            files=[("file", ("sample.pdf", pdf_bytes, "application/pdf"))],
        )
    )
    assert res.status_code == 200
    assert res.content.startswith(b"PK\x03\x04")
    assert "Digital PDF Content" in word_service.extract_docx_text(res.content)


def test_docx_to_pdf_requires_libreoffice_or_runs_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_docx = _make_sample_docx("Title", "Body")

    # 1. When LibreOffice is not installed, return clean 503
    monkeypatch.setattr("shutil.which", lambda _name: None)
    missing_res = asyncio.run(
        _post(
            "/api/v1/convert/docx-to-pdf",
            files=[("file", ("doc.docx", sample_docx, DOCX_MIME))],
        )
    )
    assert missing_res.status_code == 503

    # 2. When LibreOffice is available, verify shell=False and timeout are passed
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/soffice" if name == "soffice" else None)

    def fake_run(cmd, **kwargs):
        assert kwargs.get("shell") is False
        assert kwargs.get("timeout") == 30
        out_dir = Path(cmd[cmd.index("--outdir") + 1])
        (out_dir / "input.pdf").write_bytes(b"%PDF-1.4\nfake")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    ok_res = asyncio.run(
        _post(
            "/api/v1/convert/docx-to-pdf",
            files=[("file", ("doc.docx", sample_docx, DOCX_MIME))],
        )
    )
    assert ok_res.status_code == 200
    assert ok_res.content.startswith(b"%PDF-")

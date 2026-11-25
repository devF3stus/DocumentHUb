import asyncio
from io import BytesIO
import zipfile

import fitz
import httpx
from pypdf import PdfReader

from app.main import app


def _make_sample_pdf(num_pages: int = 3, label_prefix: str = "Page") -> bytes:
    """Create a real multi-page PDF in memory with visible text on each page."""
    doc = fitz.open()
    for i in range(1, num_pages + 1):
        page = doc.new_page(width=400, height=400)
        page.insert_text((72, 100), f"{label_prefix} {i}", fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


async def _post_pdf(
    endpoint: str,
    files: list[tuple[str, tuple[str, bytes, str]]],
    data: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(endpoint, files=files, data=data or {})


def test_merge_pdfs() -> None:
    pdf1 = _make_sample_pdf(2, "DocA")
    pdf2 = _make_sample_pdf(3, "DocB")
    res = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/merge",
            files=[
                ("files", ("a.pdf", pdf1, "application/pdf")),
                ("files", ("b.pdf", pdf2, "application/pdf")),
            ],
        )
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    reader = PdfReader(BytesIO(res.content))
    assert len(reader.pages) == 5


def test_split_pdf_returns_zip() -> None:
    pdf = _make_sample_pdf(4)
    res = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/split",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"ranges": "1-2;3-4"},
        )
    )
    assert res.status_code == 200
    with zipfile.ZipFile(BytesIO(res.content)) as zf:
        names = zf.namelist()
        assert names == ["split_part_1.pdf", "split_part_2.pdf"]
        assert len(PdfReader(BytesIO(zf.read("split_part_1.pdf"))).pages) == 2
        assert len(PdfReader(BytesIO(zf.read("split_part_2.pdf"))).pages) == 2


def test_extract_delete_and_rearrange_pages() -> None:
    pdf = _make_sample_pdf(3)

    extracted = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/extract",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"pages": "1,3"},
        )
    )
    assert extracted.status_code == 200
    assert len(PdfReader(BytesIO(extracted.content)).pages) == 2

    deleted = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/delete",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"pages": "2"},
        )
    )
    assert deleted.status_code == 200
    assert len(PdfReader(BytesIO(deleted.content)).pages) == 2

    rearranged = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/rearrange",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"order": "3,1,2"},
        )
    )
    assert rearranged.status_code == 200
    doc = fitz.open(stream=rearranged.content, filetype="pdf")
    assert "Page 3" in doc[0].get_text()
    assert "Page 1" in doc[1].get_text()
    doc.close()


def test_rotate_pages() -> None:
    pdf = _make_sample_pdf(2)
    res = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/rotate",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"angle": "90", "pages": "1"},
        )
    )
    assert res.status_code == 200
    reader = PdfReader(BytesIO(res.content))
    assert reader.pages[0].rotation == 90
    assert reader.pages[1].rotation == 0


def test_compress_pdf() -> None:
    pdf = _make_sample_pdf(3)
    res = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/compress",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
        )
    )
    assert res.status_code == 200
    assert len(PdfReader(BytesIO(res.content)).pages) == 3


def test_pdf_to_images() -> None:
    pdf = _make_sample_pdf(2)
    res = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/to-images",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"image_format": "png", "dpi": "100"},
        )
    )
    assert res.status_code == 200
    with zipfile.ZipFile(BytesIO(res.content)) as zf:
        assert zf.namelist() == ["page_1.png", "page_2.png"]
        assert zf.read("page_1.png").startswith(b"\x89PNG\r\n\x1a\n")


def test_protect_and_unlock_pdf() -> None:
    pdf = _make_sample_pdf(2)
    protected = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/protect",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"new_password": "secret123"},
        )
    )
    assert protected.status_code == 200
    assert PdfReader(BytesIO(protected.content)).is_encrypted

    # Wrong password returns 400
    wrong = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/unlock",
            files=[("file", ("locked.pdf", protected.content, "application/pdf"))],
            data={"password": "wrong"},
        )
    )
    assert wrong.status_code == 400

    # Correct password unlocks
    unlocked = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/unlock",
            files=[("file", ("locked.pdf", protected.content, "application/pdf"))],
            data={"password": "secret123"},
        )
    )
    assert unlocked.status_code == 200
    unlocked_reader = PdfReader(BytesIO(unlocked.content))
    assert not unlocked_reader.is_encrypted
    assert len(unlocked_reader.pages) == 2


def test_invalid_pdf_and_out_of_range_page_return_400() -> None:
    # Corrupted bytes with %PDF- prefix
    corrupt = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/compress",
            files=[("file", ("bad.pdf", b"%PDF-1.4\ncorrupt", "application/pdf"))],
        )
    )
    assert corrupt.status_code == 400

    # Out-of-range page deletion
    pdf = _make_sample_pdf(2)
    oob = asyncio.run(
        _post_pdf(
            "/api/v1/pdf/delete",
            files=[("file", ("doc.pdf", pdf, "application/pdf"))],
            data={"pages": "5"},
        )
    )
    assert oob.status_code == 400

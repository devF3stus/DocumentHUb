import asyncio
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.core.file_security import isolated_temp_dir, sanitize_display_filename
from app.main import app


async def _upload(filename: str, content: bytes, content_type: str, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/v1/uploads/validate",
            files={"file": (filename, content, content_type)},
            headers=headers,
        )


async def _get(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=headers)


def test_valid_pdf_upload_passes() -> None:
    """Real PDF signature (%PDF-) should pass validation in guest mode."""
    response = asyncio.run(_upload("report.pdf", b"%PDF-1.4\n%test\n", "application/pdf"))
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["extension"] == ".pdf"
    assert data["user_mode"] == "guest"
    assert data["safe_filename"].endswith(".pdf")
    assert data["safe_filename"] != "report.pdf"


def test_valid_png_upload_passes() -> None:
    """Real PNG magic bytes should pass validation."""
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    response = asyncio.run(_upload("scan.png", png_bytes, "image/png"))
    assert response.status_code == 200
    assert response.json()["extension"] == ".png"


def test_spoofed_exe_renamed_to_pdf_is_rejected() -> None:
    """An .exe (MZ magic bytes) disguised as .pdf must be rejected with 400."""
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00This is an exe"
    response = asyncio.run(_upload("homework.pdf", fake_pdf, "application/pdf"))
    assert response.status_code == 400
    assert "Executable" in response.json()["detail"]


def test_path_traversal_filename_is_neutralized() -> None:
    """Path traversal sequences (../../) must be stripped from display name and replaced by UUID on disk."""
    assert sanitize_display_filename("../../app/main.py") == "main.py"
    assert sanitize_display_filename("..\\..\\secret.pdf") == "secret.pdf"

    response = asyncio.run(_upload("../../secret.pdf", b"%PDF-1.7\ncontent", "application/pdf"))
    assert response.status_code == 200
    data = response.json()
    assert data["display_filename"] == "secret.pdf"
    assert "/" not in data["safe_filename"]
    assert ".." not in data["safe_filename"]


def test_empty_file_is_rejected() -> None:
    """Empty files must be rejected with 400."""
    response = asyncio.run(_upload("empty.pdf", b"", "application/pdf"))
    assert response.status_code == 400


def test_oversized_file_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files exceeding MAX_UPLOAD_SIZE_MB must be rejected with 413."""
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    oversized = b"%PDF-1.4\n" + (b"A" * (1024 * 1024 + 100))
    response = asyncio.run(_upload("huge.pdf", oversized, "application/pdf"))
    assert response.status_code == 413


def test_isolated_temp_dir_cleans_up_even_on_error() -> None:
    """Temporary directories must be deleted automatically after success or failure."""
    created_path: Path | None = None
    with pytest.raises(RuntimeError):
        with isolated_temp_dir() as temp_dir:
            created_path = temp_dir
            (temp_dir / "temp.pdf").write_bytes(b"%PDF-1.4")
            assert temp_dir.exists()
            raise RuntimeError("Simulated processing failure")

    assert created_path is not None
    assert not created_path.exists()


def test_auth_me_guest_and_invalid_token() -> None:
    """Guest requests succeed without a token; invalid Bearer tokens return 401 or 503."""
    guest_res = asyncio.run(_get("/api/v1/auth/me"))
    assert guest_res.status_code == 200
    assert guest_res.json()["mode"] == "guest"

    bad_token_res = asyncio.run(
        _get("/api/v1/auth/me", headers={"Authorization": "Bearer fake-token"})
    )
    assert bad_token_res.status_code in (401, 503)

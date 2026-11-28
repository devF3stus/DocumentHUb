import asyncio
from io import BytesIO

import fitz
import httpx
from PIL import Image
from pypdf import PdfReader
import pytest

from app.core.config import settings
from app.main import app
from app.services.ai.usage_tracker import usage_tracker


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((40, 80), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def _make_png() -> bytes:
    img = Image.new("RGB", (80, 60), color=(40, 140, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    img.close()
    return buf.getvalue()


async def _run_full_workflow(use_ai: bool) -> tuple[dict, bytes]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        analyze_res = await client.post(
            "/api/v1/workflows/analyze",
            files=[
                ("files", ("cv.pdf", _make_pdf("Curriculum Vitae"), "application/pdf")),
                ("files", ("photo.png", _make_png(), "image/png")),
                ("files", ("letter.txt", b"Application Letter", "text/plain")),
            ],
            data={"use_ai": str(use_ai).lower()},
        )
        assert analyze_res.status_code == 200
        analyzed = analyze_res.json()
        assert len(analyzed["documents"]) == 3

        # User reverses order manually before building
        reversed_ids = [d["id"] for d in reversed(analyzed["documents"])]
        build_res = await client.post(
            "/api/v1/workflows/build",
            json={
                "workflow_id": analyzed["workflow_id"],
                "ordered_ids": reversed_ids,
                "output_filename": "application_bundle.pdf",
            },
        )
        assert build_res.status_code == 202
        job_id = build_res.json()["job_id"]

        status_res = await client.get(f"/api/v1/workflows/jobs/{job_id}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "completed"
        assert status_res.json()["progress"] == 100

        dl_res = await client.get(f"/api/v1/workflows/jobs/{job_id}/download")
        assert dl_res.status_code == 200
        return analyzed, dl_res.content


def test_smart_workflow_with_mock_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    usage_tracker.reset()
    monkeypatch.setattr(settings, "ai_provider", "mock")
    analyzed, merged_pdf = asyncio.run(_run_full_workflow(use_ai=True))
    assert analyzed["ai_used"] is True
    assert len(PdfReader(BytesIO(merged_pdf)).pages) == 3


def test_smart_workflow_graceful_fallback_without_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    analyzed, merged_pdf = asyncio.run(_run_full_workflow(use_ai=True))
    assert analyzed["ai_used"] is False
    assert "unavailable" in analyzed["ai_note"].lower()
    assert len(PdfReader(BytesIO(merged_pdf)).pages) == 3

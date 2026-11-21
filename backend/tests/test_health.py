import asyncio

import httpx

from app.main import app


async def _request(method: str, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    """Send an in-memory HTTP request directly to the FastAPI ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers)


def test_health_check_returns_ok() -> None:
    """Verify GET /health returns 200 OK and expected metadata."""
    response = asyncio.run(_request("GET", "/health"))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "DocumentHub API"
    assert "version" in data


def test_cors_allows_configured_origin() -> None:
    """Verify CORS headers are returned for the configured frontend origin."""
    response = asyncio.run(
        _request("GET", "/health", headers={"Origin": "http://localhost:3000"})
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

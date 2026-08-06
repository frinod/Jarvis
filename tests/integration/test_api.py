"""Integration tests for JARVIS API."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
class TestAPI:
    async def test_status_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["identity"] == "JARVIS"

    async def test_chat_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/chat", json={"message": "Hello"})
            assert resp.status_code == 200
            assert "response" in resp.json()

    async def test_tools_list(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tools")
            assert resp.status_code == 200
            assert "tools" in resp.json()

    async def test_agents_list(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/agents")
            assert resp.status_code == 200
            assert "agents" in resp.json()

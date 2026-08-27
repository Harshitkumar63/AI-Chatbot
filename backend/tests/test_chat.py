"""
Tests for Chat API Endpoint and SSE Streaming Protocol.

These tests verify:
- Health check
- Request validation
- SSE event streaming (start, mode, token, sources, end)
- Mode events across course_data, rag, and direct modes
- Conversation listing and detail endpoints
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.db.init_db import init_database
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_database()


@pytest.mark.anyio
async def test_health_check():
    """Test that the health endpoint returns correct status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.anyio
async def test_chat_requires_message():
    """Test that the chat endpoint rejects empty messages."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": ""},
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_streaming_sse_course_data_mode():
    """Test full SSE streaming lifecycle for Course Data queries."""
    async def mock_stream(*args, **kwargs):
        for token in ["Python ", "Development ", "costs ", "₹2,499."]:
            yield token

    transport = ASGITransport(app=app)
    with patch("app.core.chat_service.llm_service.generate_stream", side_effect=mock_stream):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"message": "What is the price of Python Development?"},
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse SSE events from response text
    lines = response.text.strip().split("\n")
    events = [json.loads(line.replace("data: ", "")) for line in lines if line.startswith("data: ")]

    event_types = [e["event"] for e in events]
    assert "start" in event_types
    assert "mode" in event_types
    assert "token" in event_types
    assert "sources" in event_types
    assert "end" in event_types

    # Verify mode is course_data
    mode_event = next(e for e in events if e["event"] == "mode")
    assert mode_event["answer_mode"] == "course_data"

    # Verify sources event has Course Catalog
    sources_event = next(e for e in events if e["event"] == "sources")
    assert len(sources_event["sources"]) >= 1
    assert sources_event["sources"][0]["document"] == "Eduzyra Course Catalog"


@pytest.mark.anyio
async def test_chat_streaming_sse_direct_mode():
    """Test full SSE streaming lifecycle for Direct General LLM queries."""
    async def mock_stream(*args, **kwargs):
        for token in ["Recursion ", "is ", "a ", "technique."]:
            yield token

    transport = ASGITransport(app=app)
    with patch("app.core.chat_service.llm_service.generate_stream", side_effect=mock_stream):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"message": "Explain recursion in computer science"},
            )

    assert response.status_code == 200

    lines = response.text.strip().split("\n")
    events = [json.loads(line.replace("data: ", "")) for line in lines if line.startswith("data: ")]

    mode_event = next(e for e in events if e["event"] == "mode")
    assert mode_event["answer_mode"] == "direct"

    sources_event = next(e for e in events if e["event"] == "sources")
    assert sources_event["sources"] == []


@pytest.mark.anyio
async def test_list_conversations():
    """Test listing conversations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/conversations")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_get_nonexistent_conversation():
    """Test getting a conversation that doesn't exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/conversations/nonexistent-id-12345")

    assert response.status_code == 404

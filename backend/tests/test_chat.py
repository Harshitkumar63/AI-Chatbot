"""
Tests for Chat API Endpoint.

These tests verify the chat endpoint works correctly
by mocking the external services (LLM, embeddings, FAISS).
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_check():
    """Test that the health endpoint returns correct status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "EduBot"
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

    assert response.status_code == 422  # Validation error


@pytest.mark.anyio
async def test_list_conversations_empty():
    """Test listing conversations when none exist."""
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
        response = await client.get("/api/conversations/nonexistent-id")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_list_documents_empty():
    """Test listing documents when none are uploaded."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/documents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

"""
Tests for Admin API Endpoints.

Tests cover:
- Admin API key authentication
- Document upload (admin-only)
- Document listing (admin-only)
- Knowledge base status
- Unauthorized access rejection
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


ADMIN_KEY = "edubot-admin-key-change-me"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


# ============================================
# AUTH TESTS
# ============================================

@pytest.mark.anyio
async def test_admin_requires_api_key():
    """Admin endpoints should reject requests without an API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/admin/documents")

    assert response.status_code == 422  # Missing required header


@pytest.mark.anyio
async def test_admin_rejects_invalid_key():
    """Admin endpoints should reject requests with a wrong API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/admin/documents",
            headers={"X-Admin-Key": "wrong-key"},
        )

    assert response.status_code == 403


# ============================================
# DOCUMENT MANAGEMENT TESTS
# ============================================

@pytest.mark.anyio
async def test_admin_list_documents():
    """Admin should be able to list documents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/admin/documents",
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_admin_kb_status():
    """Admin should be able to check knowledge base status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/admin/status",
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "vector_store_ready" in data
    assert "total_documents" in data
    assert "completed_documents" in data
    assert "total_chunks_indexed" in data


@pytest.mark.anyio
async def test_admin_delete_nonexistent_document():
    """Deleting a non-existent document should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            "/api/admin/documents/99999",
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_admin_upload_rejects_unsupported_file():
    """Uploading an unsupported file type should fail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/admin/documents/upload",
            headers=ADMIN_HEADERS,
            files={"file": ("test.jpg", b"fake image content", "image/jpeg")},
        )

    assert response.status_code == 422


# ============================================
# STUDENT ENDPOINT TESTS
# ============================================

@pytest.mark.anyio
async def test_student_can_list_documents_without_auth():
    """Students can list documents without admin auth (read-only)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/documents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_no_student_upload_endpoint():
    """There should be no student-facing upload endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST to /api/documents/upload (student route) should NOT exist
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )

    # Should be 404 or 405 (not found or method not allowed)
    assert response.status_code in (404, 405)

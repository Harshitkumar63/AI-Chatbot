"""
Tests for Course Data Integration & Single Source of Truth.

Tests cover:
- Course database model & seed verification
- Course API endpoints (/api/courses, /api/courses/{code}, /api/courses/compare)
- CourseService queries, filters, and searches
- Single source of truth formatting for LLM prompt context
- Handling of non-existent courses (404 / no-hallucination message)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.init_db import init_database
from app.db.session import async_session_factory
from app.main import app
from app.models.database import Course
from app.services.course_service import course_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database tables and initial seed data are initialized."""
    await init_database()


@pytest.mark.anyio
async def test_courses_seeded():
    """Verify that authoritative courses are seeded in the database."""
    async with async_session_factory() as session:
        result = await session.execute(select(Course))
        courses = list(result.scalars().all())

    assert len(courses) >= 8
    codes = [c.code for c in courses]
    assert "PY-DEV" in codes
    assert "ML-FOUND" in codes
    assert "FS-WEB" in codes
    assert "DSA-PRO" in codes


@pytest.mark.anyio
async def test_list_courses_api():
    """Test GET /api/courses returns seeded courses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] >= 8
    assert len(data["courses"]) >= 8


@pytest.mark.anyio
async def test_filter_courses_by_category():
    """Test filtering courses by category (e.g. Programming)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses?category=Programming")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(c["category"].lower() == "programming" for c in data["courses"])


@pytest.mark.anyio
async def test_filter_courses_by_level():
    """Test filtering courses by difficulty level."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses?level=Beginner")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all("beginner" in c["level"].lower() for c in data["courses"])


@pytest.mark.anyio
async def test_get_course_detail_by_code():
    """Test GET /api/courses/{code} returns full course details."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses/PY-DEV")

    assert response.status_code == 200
    course = response.json()
    assert course["code"] == "PY-DEV"
    assert "Python" in course["title"]
    assert course["current_price"] == 2499.0
    assert course["instructor"] == "Dr. Rajesh Sharma"
    assert len(course["syllabus"]) > 0
    assert len(course["learning_outcomes"]) > 0


@pytest.mark.anyio
async def test_get_nonexistent_course():
    """Test GET /api/courses/INVALID-CODE returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses/NON-EXISTENT-XYZ")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_compare_courses_endpoint():
    """Test GET /api/courses/compare."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses/compare?q=Python+vs+Machine+Learning")

    assert response.status_code == 200
    data = response.json()
    assert "courses" in data
    assert len(data["courses"]) >= 2


@pytest.mark.anyio
async def test_categories_and_levels_endpoint():
    """Test GET /api/courses/categories/list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/courses/categories/list")

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "levels" in data
    assert "Programming" in data["categories"]


@pytest.mark.anyio
async def test_course_service_search():
    """Test CourseService search function."""
    async with async_session_factory() as session:
        results = await course_service.search_courses_by_query(session, "machine learning algorithms")
        assert len(results) > 0
        assert any(c.code == "ML-FOUND" for c in results)


@pytest.mark.anyio
async def test_course_context_formatter():
    """Test formatting courses into LLM context."""
    async with async_session_factory() as session:
        course = await course_service.get_course_by_id_or_code(session, "PY-DEV")
        assert course is not None

        formatted = course_service.format_courses_for_context([course])
        assert "Python Development Masterclass" in formatted
        assert "₹2,499" in formatted
        assert "Dr. Rajesh Sharma" in formatted
        assert "Syllabus" in formatted

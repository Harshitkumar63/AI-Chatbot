"""
Course API Endpoints (Student-Facing, Authoritative Data).

=== SINGLE SOURCE OF TRUTH ===
Provides direct REST access to the live course catalog in SQLite.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.schemas import (
    CourseComparisonResponse,
    CourseDetailResponse,
    CourseListResponse,
    CourseResponse,
)
from app.services.course_service import course_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get(
    "",
    response_model=CourseListResponse,
    summary="List all courses with filters",
    description="Retrieve all available courses with optional filtering by category, level, price, or search query.",
)
async def list_courses(
    category: Optional[str] = Query(None, description="Filter by category"),
    level: Optional[str] = Query(None, description="Filter by level (Beginner, Intermediate, Advanced)"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    search: Optional[str] = Query(None, description="Search term for title, instructor, or description"),
    session: AsyncSession = Depends(get_session),
) -> CourseListResponse:
    """
    Get all active courses from the authoritative database.
    """
    if search:
        courses = await course_service.search_courses_by_query(
            session=session,
            query_text=search,
            limit=20,
        )
    else:
        courses = await course_service.get_all_courses(
            session=session,
            category=category,
            level=level,
            max_price=max_price,
            is_available=True,
        )

    serialized = [
        CourseResponse(
            id=c.id,
            code=c.code,
            title=c.title,
            description=c.description,
            category=c.category,
            level=c.level,
            instructor=c.instructor,
            duration=c.duration,
            lessons_count=c.lessons_count,
            rating=c.rating,
            enrolled_students=c.enrolled_students,
            current_price=c.current_price,
            original_price=c.original_price,
            currency=c.currency,
            discount_percent=c.discount_percent,
            is_available=c.is_available,
        )
        for c in courses
    ]

    return CourseListResponse(total=len(serialized), courses=serialized)


@router.get(
    "/categories/list",
    summary="List all course categories and levels",
    description="Get unique categories and levels available in the course catalog.",
)
async def get_categories_and_levels(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get all available course categories and difficulty levels.
    """
    return await course_service.get_all_categories_and_levels(session)


@router.get(
    "/compare",
    response_model=CourseComparisonResponse,
    summary="Compare courses",
    description="Compare multiple courses by search query or course codes.",
)
async def compare_courses(
    q: str = Query(..., description="Comparison query, e.g. 'Python vs Machine Learning'"),
    session: AsyncSession = Depends(get_session),
) -> CourseComparisonResponse:
    """
    Compare courses based on attributes like price, instructor, duration, and outcomes.
    """
    return await course_service.compare_courses_by_query(session, q)


@router.get(
    "/{course_id_or_code}",
    response_model=CourseDetailResponse,
    summary="Get full course details",
    description="Retrieve full details for a course by its UUID or unique course code (e.g. 'PY-DEV').",
)
async def get_course_details(
    course_id_or_code: str,
    session: AsyncSession = Depends(get_session),
) -> CourseDetailResponse:
    """
    Get comprehensive details for a specific course.
    """
    course = await course_service.get_course_by_id_or_code(
        session=session,
        identifier=course_id_or_code,
    )

    if not course:
        raise HTTPException(
            status_code=404,
            detail=f"Course with ID or code '{course_id_or_code}' not found in the course catalog.",
        )

    return course_service.serialize_course(course)

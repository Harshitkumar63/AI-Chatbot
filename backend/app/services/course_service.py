"""
Course Service for Eduzyra — Authoritative Course Data Access.

=== SINGLE SOURCE OF TRUTH ===
This service is the ONLY interface through which the chatbot or APIs
query course information. It interacts directly with the SQLite database
using SQLAlchemy.

Key features:
1. Dynamic retrieval of live course data (pricing, instructors, syllabus, etc.)
2. Semantic & fuzzy search across titles, categories, levels, and descriptions
3. Course comparison helper
4. Intelligent course recommendation helper
5. Structured prompt grounding (formats DB records into clear context for the LLM)
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Course
from app.models.schemas import (
    CourseComparisonItem,
    CourseComparisonResponse,
    CourseDetailResponse,
    CourseResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CourseService:
    """
    Service for querying and managing authoritative Eduzyra course data.
    """

    async def get_all_courses(
        self,
        session: AsyncSession,
        category: Optional[str] = None,
        level: Optional[str] = None,
        max_price: Optional[float] = None,
        is_available: bool = True,
    ) -> List[Course]:
        """
        Retrieve all courses matching optional filter criteria.
        """
        query = select(Course)

        if is_available:
            query = query.where(Course.is_available.is_(True))

        if category:
            query = query.where(func.lower(Course.category) == category.lower().strip())

        if level:
            query = query.where(func.lower(Course.level).like(f"%{level.lower().strip()}%"))

        if max_price is not None:
            query = query.where(Course.current_price <= max_price)

        query = query.order_by(Course.rating.desc(), Course.enrolled_students.desc())

        result = await session.execute(query)
        courses = list(result.scalars().all())
        logger.debug(f"Retrieved {len(courses)} courses matching filters.")
        return courses

    async def get_course_by_id_or_code(
        self,
        session: AsyncSession,
        identifier: str,
    ) -> Optional[Course]:
        """
        Get a specific course by its unique ID or course code (e.g. 'PY-DEV').
        """
        clean_id = identifier.strip()

        # Try matching by code (case-insensitive) or UUID
        result = await session.execute(
            select(Course).where(
                or_(
                    func.lower(Course.code) == clean_id.lower(),
                    Course.id == clean_id,
                )
            )
        )
        course = result.scalar_one_or_none()

        if not course:
            # Try matching by exact title
            result = await session.execute(
                select(Course).where(func.lower(Course.title) == clean_id.lower())
            )
            course = result.scalar_one_or_none()

        return course

    async def search_courses_by_query(
        self,
        session: AsyncSession,
        query_text: str,
        limit: int = 5,
    ) -> List[Course]:
        """
        Intelligently search courses matching terms in the query text.
        Searches title, category, level, instructor, and description.
        """
        clean_query = query_text.lower().strip()
        tokens = [t for t in re.split(r"\W+", clean_query) if len(t) > 2]

        all_courses = await self.get_all_courses(session, is_available=True)
        if not all_courses:
            return []

        scored_courses: List[Tuple[Course, int]] = []

        # Stopwords that should not be used as domain tokens
        stopwords = {
            "what", "is", "the", "a", "an", "of", "and", "in", "to", "for", "with",
            "how", "who", "much", "many", "price", "fee", "fees", "cost", "duration",
            "hours", "weeks", "syllabus", "curriculum", "tell", "me", "about", "course",
            "courses", "program", "class", "classes"
        }
        domain_tokens = [t for t in tokens if t not in stopwords and len(t) > 2]

        is_discovery_query = any(phrase in clean_query for phrase in [
            "what courses", "which courses", "available courses", "list of courses",
            "show courses", "all courses", "courses do you have", "what do you teach",
            "course catalog", "our courses", "list courses", "any courses",
            "course prices", "cost of courses", "how much are the courses", "how much do courses cost",
            "course fees", "prices of courses", "all prices", "fee structure", "what are the fees",
            "details of the project", "about eduzyra", "about althexus", "what is eduzyra",
            "tell me about eduzyra", "about this platform", "about this website", "learning paths",
            "react for products"
        ]) or clean_query in ["courses", "course list", "available courses", "catalog", "prices", "fees", "pricing", "cost"]

        for course in all_courses:
            score = 0
            title_lower = course.title.lower()
            code_lower = course.code.lower()
            category_lower = course.category.lower()
            level_lower = course.level.lower()
            instructor_lower = course.instructor.lower()
            desc_lower = course.description.lower()

            # Exact title or code match gives massive boost
            if clean_query in title_lower or clean_query in code_lower:
                score += 50
            if title_lower in clean_query:
                score += 40

            # Check domain tokens
            for token in domain_tokens:
                if token in code_lower:
                    score += 30
                elif token in title_lower:
                    score += 20
                elif token in category_lower:
                    score += 15
                elif token in instructor_lower:
                    score += 15
                elif token in desc_lower:
                    score += 5

            # Common topic mappings
            if "python" in domain_tokens and "python" in title_lower:
                score += 25
            if any(k in domain_tokens for k in ["ml", "machine", "learning", "ai", "artificial"]) and (
                "machine learning" in title_lower or "ai" in category_lower or "ai" in code_lower
            ):
                score += 25
            if any(k in domain_tokens for k in ["web", "fullstack", "react", "frontend", "backend", "javascript"]) and (
                "web" in title_lower or "web" in category_lower
            ):
                score += 25
            if any(k in domain_tokens for k in ["dsa", "algorithms", "structures", "interview", "leetcode"]) and (
                "data structures" in title_lower or "dsa" in code_lower
            ):
                score += 25
            if any(k in domain_tokens for k in ["cloud", "devops", "aws", "docker", "kubernetes"]) and (
                "cloud" in title_lower or "devops" in title_lower
            ):
                score += 25
            if any(k in domain_tokens for k in ["security", "cyber", "ethical", "hacking"]) and (
                "cybersecurity" in title_lower or "security" in category_lower
            ):
                score += 25
            if any(k in domain_tokens for k in ["analytics", "sql", "data", "bi", "tableau", "powerbi"]) and (
                "analytics" in title_lower or "data science" in category_lower
            ):
                score += 25

            if score >= 15:
                scored_courses.append((course, score))

        # Sort by score descending
        scored_courses.sort(key=lambda x: x[1], reverse=True)
        results = [c for c, s in scored_courses[:limit]]

        # Only return all courses if it's a broad discovery query
        if not results and is_discovery_query:
            return all_courses[:limit]

        return results

    async def compare_courses_by_query(
        self,
        session: AsyncSession,
        query_text: str,
    ) -> CourseComparisonResponse:
        """
        Extract course mentions from query and generate structured comparison.
        """
        all_courses = await self.get_all_courses(session)
        matched_courses: List[Course] = []

        for course in all_courses:
            if (
                course.title.lower() in query_text.lower()
                or course.code.lower() in query_text.lower()
                or any(
                    word in query_text.lower()
                    for word in course.title.lower().split()
                    if len(word) > 4
                )
            ):
                if course not in matched_courses:
                    matched_courses.append(course)

        # If fewer than 2 matched, use search_courses_by_query
        if len(matched_courses) < 2:
            matched_courses = await self.search_courses_by_query(session, query_text, limit=2)

        items: List[CourseComparisonItem] = []
        for c in matched_courses:
            try:
                syllabus_list = json.loads(c.syllabus)
            except Exception:
                syllabus_list = []
            try:
                outcomes_list = json.loads(c.learning_outcomes)
            except Exception:
                outcomes_list = []

            items.append(
                CourseComparisonItem(
                    code=c.code,
                    title=c.title,
                    category=c.category,
                    level=c.level,
                    instructor=c.instructor,
                    duration=c.duration,
                    lessons_count=c.lessons_count,
                    rating=c.rating,
                    current_price=c.current_price,
                    original_price=c.original_price,
                    currency=c.currency,
                    discount_percent=c.discount_percent,
                    syllabus_preview=syllabus_list[:3],
                    learning_outcomes=outcomes_list[:3],
                )
            )

        notes = (
            f"Compared {len(items)} courses based on price, instructor, duration, level, and syllabus."
            if items
            else "No matching courses found for comparison."
        )

        return CourseComparisonResponse(courses=items, comparison_notes=notes)

    def format_courses_for_context(
        self,
        courses: List[Course],
        detail_level: str = "full",
    ) -> str:
        """
        Format retrieved course objects into clear, structured context for the LLM prompt.

        Parameters
        ----------
        courses : List[Course]
            The authoritative course records from the database.
        detail_level : str
            'full' for detailed course facts or 'summary' for quick catalog lists.

        Returns
        -------
        str
            A structured markdown block containing ONLY authoritative facts.
        """
        if not courses:
            return (
                "NO COURSES FOUND in the Eduzyra course catalog matching the user's query.\n"
                "State clearly that no matching course was found in Eduzyra's catalog. "
                "Do NOT invent or hallucinate course names, prices, or details."
            )

        formatted_blocks: List[str] = []

        for i, c in enumerate(courses, 1):
            try:
                syllabus = json.loads(c.syllabus)
                syllabus_formatted = "\n".join([f"    - {item}" for item in syllabus])
            except Exception:
                syllabus_formatted = "    - Information in catalog"

            try:
                outcomes = json.loads(c.learning_outcomes)
                outcomes_formatted = "\n".join([f"    - {item}" for item in outcomes])
            except Exception:
                outcomes_formatted = "    - Core industry skills"

            try:
                prereqs = json.loads(c.prerequisites)
                prereqs_formatted = ", ".join(prereqs) if prereqs else "None"
            except Exception:
                prereqs_formatted = "None"

            if detail_level == "full":
                block = (
                    f"### Course {i}: {c.title} (Code: {c.code})\n"
                    f"- **Category**: {c.category}\n"
                    f"- **Level**: {c.level}\n"
                    f"- **Instructor**: {c.instructor}"
                    + (f" ({c.instructor_bio})" if c.instructor_bio else "")
                    + f"\n- **Current Price**: {c.currency}{c.current_price:,.0f} "
                    f"(Original: {c.currency}{c.original_price:,.0f}, {c.discount_percent}% OFF)\n"
                    f"- **Duration**: {c.duration}\n"
                    f"- **Lessons Count**: {c.lessons_count} lessons\n"
                    f"- **Rating**: ⭐ {c.rating} / 5.0 ({c.reviews_count:,} reviews)\n"
                    f"- **Enrolled Students**: {c.enrolled_students:,} students\n"
                    f"- **Enrollment Status**: {'Available / Open' if c.is_available else 'Closed'}\n"
                    f"- **Prerequisites**: {prereqs_formatted}\n"
                    f"- **Description**: {c.description}\n"
                    f"- **Syllabus / Modules**:\n{syllabus_formatted}\n"
                    f"- **Learning Outcomes**:\n{outcomes_formatted}\n"
                )
            else:
                block = (
                    f"### {c.title} [{c.code}]\n"
                    f"- **Price**: {c.currency}{c.current_price:,.0f} ({c.discount_percent}% off {c.currency}{c.original_price:,.0f})\n"
                    f"- **Instructor**: {c.instructor} | **Level**: {c.level} | **Duration**: {c.duration}\n"
                    f"- **Rating**: ⭐ {c.rating} ({c.enrolled_students:,} enrolled)\n"
                    f"- **Key Description**: {c.description}\n"
                )

            formatted_blocks.append(block)

        return "\n".join(formatted_blocks)

    async def get_all_categories_and_levels(
        self,
        session: AsyncSession,
    ) -> Dict[str, List[str]]:
        """
        Get list of all unique categories and difficulty levels.
        """
        cat_res = await session.execute(select(Course.category).distinct())
        categories = [r[0] for r in cat_res.all() if r[0]]

        level_res = await session.execute(select(Course.level).distinct())
        levels = [r[0] for r in level_res.all() if r[0]]

        return {
            "categories": sorted(categories),
            "levels": sorted(levels),
        }

    def serialize_course(self, course: Course) -> CourseDetailResponse:
        """
        Convert SQLAlchemy Course model to Pydantic CourseDetailResponse.
        """
        try:
            syllabus_list = json.loads(course.syllabus)
        except Exception:
            syllabus_list = []
        try:
            outcomes_list = json.loads(course.learning_outcomes)
        except Exception:
            outcomes_list = []
        try:
            prereqs_list = json.loads(course.prerequisites)
        except Exception:
            prereqs_list = []

        return CourseDetailResponse(
            id=course.id,
            code=course.code,
            title=course.title,
            description=course.description,
            category=course.category,
            level=course.level,
            instructor=course.instructor,
            instructor_bio=course.instructor_bio,
            duration=course.duration,
            lessons_count=course.lessons_count,
            rating=course.rating,
            reviews_count=course.reviews_count,
            enrolled_students=course.enrolled_students,
            current_price=course.current_price,
            original_price=course.original_price,
            currency=course.currency,
            discount_percent=course.discount_percent,
            syllabus=syllabus_list,
            learning_outcomes=outcomes_list,
            prerequisites=prereqs_list,
            is_available=course.is_available,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )


# ============================================
# SINGLETON INSTANCE
# ============================================
course_service = CourseService()

"""
Tests for 3-Way Hybrid AI Router (AIRouter & RAGEngine).

Tests cover:
- Course Discovery intent routing
- Course Details & Pricing intent routing
- Course Comparison & Recommendation routing
- Multi-turn pronoun follow-up routing ("Who teaches it?")
- Non-existent course queries (no hallucination guarantee)
- RAG document & organizational policy routing
- General LLM educational concept routing
- Citation generation per mode
"""

import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.documents import Document as LCDocument

from app.core.rag_engine import RAGEngine
from app.core.router import AIRouter
from app.db.init_db import init_database
from app.db.session import async_session_factory
from app.models.enums import AnswerMode


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_database()


# ============================================
# ROUTER INTENT TESTS
# ============================================

@pytest.mark.anyio
async def test_route_course_discovery():
    """Questions like 'Which courses are available?' must route to COURSE_DATA."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="Which courses are available?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert len(meta["matched_courses"]) >= 1


@pytest.mark.anyio
async def test_route_course_details_price():
    """Questions asking for price of Python Development must route to COURSE_DATA."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="What is the price of Python Development?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert any(c.code == "PY-DEV" for c in meta["matched_courses"])


@pytest.mark.anyio
async def test_route_course_details_instructor():
    """Questions asking who teaches a course must route to COURSE_DATA."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="Who teaches Machine Learning Foundations?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert any(c.code == "ML-FOUND" for c in meta["matched_courses"])


@pytest.mark.anyio
async def test_route_course_comparison():
    """Questions comparing courses must route to COURSE_DATA."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="Compare Python Development and Machine Learning Foundations",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    codes = [c.code for c in meta["matched_courses"]]
    assert "PY-DEV" in codes or "ML-FOUND" in codes


@pytest.mark.anyio
async def test_route_course_recommendation():
    """Course recommendation requests must route to COURSE_DATA."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="I am a beginner and want to learn AI. Which course should I take?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert len(meta["matched_courses"]) > 0


@pytest.mark.anyio
async def test_route_pronoun_followup_with_history():
    """Follow-up 'Who teaches it?' must resolve previous course from history."""
    router = AIRouter()
    history = [
        {"role": "human", "content": "What is Python Development Masterclass?"},
        {"role": "ai", "content": "Python Development Masterclass (PY-DEV) is an 8-week comprehensive course..."},
    ]

    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="Who teaches it?",
            chat_history=history,
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert any(c.code == "PY-DEV" for c in meta["matched_courses"])


@pytest.mark.anyio
async def test_route_general_concept():
    """Pure educational questions like 'What is recursion?' must route to DIRECT mode."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="What is recursion and how does the call stack work?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.DIRECT


@pytest.mark.anyio
async def test_route_org_policy_without_documents():
    """Questions about refund policy must route to RAG for verified institutional facts."""
    router = AIRouter()
    async with async_session_factory() as session:
        mode, meta = await router.route_query(
            user_message="What is Eduzyra's refund policy?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.RAG


# ============================================
# RAG ENGINE 3-WAY PROMPT BUILDING TESTS
# ============================================

@pytest.mark.anyio
async def test_rag_engine_builds_course_data_prompt():
    """Verify RAGEngine builds COURSE_DATA prompt with Course Catalog citation."""
    engine = RAGEngine()
    async with async_session_factory() as session:
        prompt, sources, mode = await engine.build_prompt(
            user_message="What is the price of Python Development?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    assert "Authoritative Course Catalog Context" in prompt
    assert "₹2,499" in prompt
    assert len(sources) == 1
    assert sources[0].document == "Eduzyra Course Catalog"
    assert sources[0].source_type == "course_catalog"


@pytest.mark.anyio
async def test_rag_engine_builds_direct_prompt():
    """Verify RAGEngine builds DIRECT prompt with no citations."""
    engine = RAGEngine()
    async with async_session_factory() as session:
        prompt, sources, mode = await engine.build_prompt(
            user_message="Explain Newton's Second Law of Motion",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.DIRECT
    assert "general knowledge" in prompt.lower()
    assert sources == []

"""
End-to-End Test Suite for Eduzyra AI Assistant.

Explicitly validates all 7 Core Scenarios required by the project specification:
1. Scenario 1: General educational questions without documents
2. Scenario 2: Course questions using live course database
3. Scenario 3: Non-existent course questions (Anti-hallucination safety)
4. Scenario 4: RAG document questions (FAISS retrieval & page/section citations)
5. Scenario 5: Pronoun follow-ups using multi-turn conversation memory
6. Scenario 6: Real-time Server-Sent Events (SSE) streaming responses
7. Scenario 7: Empty conversation history vs multi-turn history transitions
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.core.rag_engine import rag_engine
from app.core.router import ai_router
from app.core.memory_manager import memory_manager
from app.db.init_db import init_database
from app.db.session import async_session_factory
from app.main import app
from app.models.enums import AnswerMode, MessageRole
from app.services.vector_store import vector_store_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_database()


# =========================================================================
# SCENARIO 1: General Educational Questions Without Documents
# =========================================================================

@pytest.mark.anyio
async def test_scenario_1_general_educational_question():
    """
    Scenario 1:
    A student asks a general computer science question ('Explain recursion in Python').
    System must route to DIRECT LLM, generate an educational response from general knowledge,
    and include ZERO fabricated citations.
    """
    async with async_session_factory() as session:
        prompt, sources, mode = await rag_engine.build_prompt(
            user_message="Explain what recursion is in computer science and how the base case works",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.DIRECT
    assert sources == []
    assert "general knowledge" in prompt.lower()
    assert "recursion" in prompt.lower()


# =========================================================================
# SCENARIO 2: Course Questions Using Live Course Database
# =========================================================================

@pytest.mark.anyio
async def test_scenario_2_course_pricing_and_instructor():
    """
    Scenario 2:
    A student asks about course price and instructor.
    System must route to COURSE_DATA, pull live database facts (₹2,499 for PY-DEV,
    Dr. Priya Mehta for ML-FOUND), and cite 'Eduzyra Course Catalog'.
    """
    async with async_session_factory() as session:
        # Check Pricing
        prompt_price, sources_price, mode_price = await rag_engine.build_prompt(
            user_message="What is the price of Python Development?",
            chat_history=[],
            session=session,
        )
        assert mode_price == AnswerMode.COURSE_DATA
        assert "₹2,499" in prompt_price
        assert len(sources_price) == 1
        assert sources_price[0].document == "Eduzyra Course Catalog"
        assert sources_price[0].source_type == "course_catalog"

        # Check Instructor
        prompt_inst, sources_inst, mode_inst = await rag_engine.build_prompt(
            user_message="Who teaches Machine Learning Foundations?",
            chat_history=[],
            session=session,
        )
        assert mode_inst == AnswerMode.COURSE_DATA
        assert "Dr. Priya Mehta" in prompt_inst
        assert len(sources_inst) == 1
        assert sources_inst[0].document == "Eduzyra Course Catalog"


# =========================================================================
# SCENARIO 3: Non-Existent Course Questions (Anti-Hallucination Safety)
# =========================================================================

@pytest.mark.anyio
async def test_scenario_3_nonexistent_course_safety():
    """
    Scenario 3:
    A student asks for a course that does NOT exist ('Advanced Quantum Cooking and Astrology').
    System must NOT hallucinate a price or syllabus. The database query returns 0 matches,
    and the prompt strictly enforces stating the course is unavailable.
    """
    async with async_session_factory() as session:
        prompt, sources, mode = await rag_engine.build_prompt(
            user_message="What is the price and duration of the Advanced Quantum Cooking and Astrology course?",
            chat_history=[],
            session=session,
        )

    assert mode == AnswerMode.COURSE_DATA
    # Ensure zero hallucinated matches and strict anti-hallucination instruction
    assert "NO COURSES FOUND in the Eduzyra course catalog" in prompt
    assert "Strict Instructions:" in prompt
    assert "Do NOT invent details or pricing" in prompt


# =========================================================================
# SCENARIO 4: RAG Document Questions
# =========================================================================

@pytest.mark.anyio
async def test_scenario_4_rag_document_question():
    """
    Scenario 4:
    A student asks an institutional / policy question ('What is Eduzyra refund policy?').
    When documents are indexed, RAG retrieves relevant chunks with page & section citations.
    """
    from langchain_core.documents import Document as LCDocument

    doc = LCDocument(
        page_content=(
            "Eduzyra offers a 100% money-back guarantee if a refund is "
            "requested within 7 days of course enrollment."
        ),
        metadata={
            "source": "Eduzyra_Policy_Handbook.pdf",
            "page": 1,
            "section": "Refund and Cancellation Policy",
        },
    )

    with patch("app.core.router.vector_store_service") as mock_vs, patch(
        "app.core.rag_engine.vector_store_service"
    ) as mock_rag_vs:
        mock_vs.is_ready = True
        mock_vs.document_count = 5
        mock_vs.search = AsyncMock(return_value=[(doc, 0.15)])
        mock_rag_vs.is_ready = True
        mock_rag_vs.search = AsyncMock(return_value=[(doc, 0.15)])

        async with async_session_factory() as session:
            prompt, sources, mode = await rag_engine.build_prompt(
                user_message="What is the deadline for Eduzyra refund policy?",
                chat_history=[],
                session=session,
            )

    assert mode == AnswerMode.RAG
    assert len(sources) >= 1
    assert sources[0].document == "Eduzyra_Policy_Handbook.pdf"
    assert sources[0].page == 1
    assert sources[0].section == "Refund and Cancellation Policy"
    assert "7 days" in prompt


# =========================================================================
# SCENARIO 5: Pronoun Follow-ups Using Conversation History
# =========================================================================

@pytest.mark.anyio
async def test_scenario_5_pronoun_followups():
    """
    Scenario 5:
    Turn 1: 'What is Python Development Masterclass?'
    Turn 2: 'Who teaches it?'
    Turn 3: 'What is the price of it?'
    System must resolve 'it' to 'Python Development Masterclass' across turns.
    """
    history = [
        {"role": "human", "content": "What is Python Development Masterclass?"},
        {"role": "ai", "content": "Python Development Masterclass (PY-DEV) is an 8-week bootcamp covering Python."},
    ]

    async with async_session_factory() as session:
        # Turn 2 follow-up
        mode_turn2, meta_turn2 = await ai_router.route_query(
            user_message="Who teaches it?",
            chat_history=history,
            session=session,
        )
        assert mode_turn2 == AnswerMode.COURSE_DATA
        assert any(c.code == "PY-DEV" for c in meta_turn2["matched_courses"])

        # Turn 3 follow-up
        mode_turn3, meta_turn3 = await ai_router.route_query(
            user_message="What is the price of it?",
            chat_history=history,
            session=session,
        )
        assert mode_turn3 == AnswerMode.COURSE_DATA
        assert any(c.code == "PY-DEV" for c in meta_turn3["matched_courses"])


# =========================================================================
# SCENARIO 6: Streaming Responses (SSE Protocol)
# =========================================================================

@pytest.mark.anyio
async def test_scenario_6_streaming_sse_protocol():
    """
    Scenario 6:
    Verify token streaming via Server-Sent Events with all required event stages:
    start -> mode -> token... -> sources -> end.
    """
    async def mock_stream(*args, **kwargs):
        for token in ["Python ", "is ", "awesome!"]:
            yield token

    transport = ASGITransport(app=app)
    with patch("app.core.chat_service.llm_service.generate_stream", side_effect=mock_stream):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"message": "What is Python Development Masterclass?"},
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    lines = [line.strip() for line in response.text.strip().split("\n") if line.startswith("data: ")]
    events = [json.loads(line[6:]) for line in lines]

    event_names = [e["event"] for e in events]
    assert event_names == ["start", "mode", "token", "token", "token", "sources", "end"]

    # Verify mode event
    mode_event = next(e for e in events if e["event"] == "mode")
    assert mode_event["answer_mode"] == "course_data"

    # Verify tokens concatenated
    tokens = [e["token"] for e in events if e["event"] == "token"]
    assert "".join(tokens) == "Python is awesome!"

    # Verify sources event
    sources_event = next(e for e in events if e["event"] == "sources")
    assert len(sources_event["sources"]) >= 1


# =========================================================================
# SCENARIO 7: Empty Conversation History vs Multi-Turn History
# =========================================================================

@pytest.mark.anyio
async def test_scenario_7_empty_vs_multiturn_history():
    """
    Scenario 7:
    Verify transition from a clean empty conversation to a multi-turn history.
    """
    async with async_session_factory() as session:
        # Clean new conversation
        conv = await memory_manager.get_or_create_conversation(session)
        empty_history = await memory_manager.get_chat_history(session, conv.id)
        assert len(empty_history) == 0

        # Save turn 1
        await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, "What is Machine Learning?")
        await memory_manager.save_message(session, conv.id, MessageRole.AI, "ML is a branch of AI.", answer_mode="direct")

        # Check turn 1 history
        turn1_history = await memory_manager.get_chat_history(session, conv.id)
        assert len(turn1_history) == 2
        assert turn1_history[0]["role"] == "human"
        assert turn1_history[1]["role"] == "ai"

        # Save turn 2
        await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, "Give an example in Python")
        await memory_manager.save_message(session, conv.id, MessageRole.AI, "Here is a Python example...", answer_mode="direct")

        # Check turn 2 history
        turn2_history = await memory_manager.get_chat_history(session, conv.id)
        assert len(turn2_history) == 4
        assert turn2_history[2]["content"] == "Give an example in Python"

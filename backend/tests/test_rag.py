"""
Tests for RAG Engine — Including Intelligent Routing.

Tests cover:
- Chat history formatting
- System prompt content
- Similarity score calculation
- Intelligent routing (RAG vs Direct mode)
- Prompt building for each mode
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.documents import Document as LCDocument

from app.core.rag_engine import RAGEngine
from app.models.enums import AnswerMode


def test_format_chat_history_empty():
    """Empty history should return a default message."""
    engine = RAGEngine()
    result = engine._format_chat_history([])
    assert result == "No previous conversation."


def test_format_chat_history():
    """Chat history should be formatted as 'Role: Content'."""
    engine = RAGEngine()
    history = [
        {"role": "human", "content": "Hello"},
        {"role": "ai", "content": "Hi there!"},
    ]
    result = engine._format_chat_history(history)
    assert "Human: Hello" in result
    assert "Ai: Hi there!" in result


def test_get_system_prompt():
    """System prompt should contain EduBot identity."""
    engine = RAGEngine()
    prompt = engine.get_system_prompt()
    assert "EduBot" in prompt
    assert "educational" in prompt.lower()


def test_get_best_similarity_score_empty():
    """Empty search results should return 0.0."""
    engine = RAGEngine()
    score = engine._get_best_similarity_score([])
    assert score == 0.0


def test_get_best_similarity_score():
    """Should return the highest similarity score (lowest L2 distance)."""
    engine = RAGEngine()
    doc = LCDocument(page_content="test", metadata={"source": "test.pdf"})

    # L2 distance: lower = more similar
    # similarity = 1 / (1 + distance)
    results = [
        (doc, 1.0),  # similarity = 0.5
        (doc, 0.5),  # similarity = 0.667
        (doc, 2.0),  # similarity = 0.333
    ]

    score = engine._get_best_similarity_score(results)
    # Best = lowest distance (0.5) → similarity = 1/(1+0.5) ≈ 0.667
    assert abs(score - (1.0 / 1.5)) < 0.001


def test_get_best_similarity_score_perfect_match():
    """A distance of 0.0 should give similarity of 1.0 (perfect match)."""
    engine = RAGEngine()
    doc = LCDocument(page_content="test", metadata={"source": "test.pdf"})
    results = [(doc, 0.0)]

    score = engine._get_best_similarity_score(results)
    assert score == 1.0


@pytest.mark.anyio
async def test_build_prompt_empty_vector_store():
    """When vector store is empty, should use DIRECT mode."""
    engine = RAGEngine()

    with patch("app.core.rag_engine.vector_store_service") as mock_vs:
        mock_vs.is_ready = False
        mock_vs.document_count = 0

        prompt, sources, mode = await engine.build_prompt(
            user_message="What is Python?",
            chat_history=[],
        )

    assert mode == AnswerMode.DIRECT
    assert sources == []
    assert "What is Python?" in prompt


@pytest.mark.anyio
async def test_build_prompt_no_search_results():
    """When FAISS returns no results, should use DIRECT mode."""
    engine = RAGEngine()

    with patch("app.core.rag_engine.vector_store_service") as mock_vs:
        mock_vs.is_ready = True
        mock_vs.document_count = 10
        mock_vs.search = AsyncMock(return_value=[])

        prompt, sources, mode = await engine.build_prompt(
            user_message="Random unrelated question?",
            chat_history=[],
        )

    assert mode == AnswerMode.DIRECT
    assert sources == []


@pytest.mark.anyio
async def test_build_prompt_low_similarity_uses_direct():
    """When retrieval scores are low, should skip RAG and use DIRECT mode."""
    engine = RAGEngine()
    doc = LCDocument(
        page_content="Some unrelated content",
        metadata={"source": "random.pdf", "page": 1},
    )

    with patch("app.core.rag_engine.vector_store_service") as mock_vs:
        mock_vs.is_ready = True
        mock_vs.document_count = 10
        # High L2 distance = low similarity → below threshold
        mock_vs.search = AsyncMock(return_value=[(doc, 5.0)])

        prompt, sources, mode = await engine.build_prompt(
            user_message="What is Python?",
            chat_history=[],
        )

    assert mode == AnswerMode.DIRECT
    assert sources == []


@pytest.mark.anyio
async def test_build_prompt_high_similarity_uses_rag():
    """When retrieval scores are high, should use RAG mode with citations."""
    engine = RAGEngine()
    doc = LCDocument(
        page_content="Python is a programming language created by Guido.",
        metadata={"source": "python_intro.pdf", "page": 3},
    )

    with patch("app.core.rag_engine.vector_store_service") as mock_vs:
        mock_vs.is_ready = True
        mock_vs.document_count = 10
        # Low L2 distance = high similarity → above threshold
        mock_vs.search = AsyncMock(return_value=[(doc, 0.2)])

        prompt, sources, mode = await engine.build_prompt(
            user_message="What is Python?",
            chat_history=[],
        )

    assert mode == AnswerMode.RAG
    assert len(sources) > 0
    assert sources[0].document == "python_intro.pdf"
    assert sources[0].page == 3
    assert "Python is a programming language" in prompt


def test_build_direct_prompt_contains_question():
    """Direct prompt should include the user's question."""
    engine = RAGEngine()
    prompt = engine._build_direct_prompt(
        user_message="Explain recursion",
        chat_history=[],
    )
    assert "Explain recursion" in prompt
    assert "general knowledge" in prompt.lower()


def test_build_rag_prompt_contains_context_and_question():
    """RAG prompt should include both context and question."""
    engine = RAGEngine()
    doc = LCDocument(
        page_content="Recursion is a function calling itself.",
        metadata={"source": "cs_notes.pdf", "page": 7},
    )

    prompt, sources = engine._build_rag_prompt(
        user_message="Explain recursion",
        chat_history=[],
        search_results=[(doc, 0.3)],
    )

    assert "Explain recursion" in prompt
    assert "Recursion is a function calling itself" in prompt
    assert "cs_notes.pdf" in prompt
    assert len(sources) == 1
    assert sources[0].document == "cs_notes.pdf"
    assert sources[0].page == 7

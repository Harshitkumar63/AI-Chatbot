"""
Tests for Conversation Memory and Multi-Turn Entity Resolution.

Tests cover:
- Conversation creation and retrieval
- Message persistence and chronological ordering
- Memory window size limits
- Multi-turn pronoun resolution (Course pronouns: 'it', 'the instructor', 'price')
- Technical concept follow-up resolution ('in C++', 'example of it')
- Auto-generation of conversation titles
- Source citation deserialization in message history
"""

import pytest
from app.core.memory_manager import memory_manager
from app.db.init_db import init_database
from app.db.session import async_session_factory
from app.models.enums import MessageRole
from app.models.schemas import SourceInfo


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    await init_database()


@pytest.mark.anyio
async def test_get_or_create_conversation():
    """Verify creating new conversation and fetching existing one."""
    async with async_session_factory() as session:
        conv1 = await memory_manager.get_or_create_conversation(session)
        assert conv1.id is not None

        conv2 = await memory_manager.get_or_create_conversation(session, conv1.id)
        assert conv2.id == conv1.id


@pytest.mark.anyio
async def test_save_and_load_chat_history_order():
    """Messages must be returned in chronological order (oldest first)."""
    async with async_session_factory() as session:
        conv = await memory_manager.get_or_create_conversation(session)

        await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, "Hello 1")
        await memory_manager.save_message(session, conv.id, MessageRole.AI, "Response 1")
        await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, "Hello 2")

        history = await memory_manager.get_chat_history(session, conv.id)

        assert len(history) == 3
        assert history[0]["content"] == "Hello 1"
        assert history[1]["content"] == "Response 1"
        assert history[2]["content"] == "Hello 2"


@pytest.mark.anyio
async def test_memory_window_size():
    """Chat history should respect window size limit."""
    async with async_session_factory() as session:
        conv = await memory_manager.get_or_create_conversation(session)

        for i in range(15):
            await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, f"Msg {i}")

        # Default window is 10
        history = await memory_manager.get_chat_history(session, conv.id, window_size=5)
        assert len(history) == 5
        assert history[0]["content"] == "Msg 10"
        assert history[-1]["content"] == "Msg 14"


@pytest.mark.anyio
async def test_resolve_contextual_query_course_pronouns():
    """Resolves 'Who teaches it?' when previous turn discussed Python Development."""
    history = [
        {"role": "human", "content": "What is Python Development Masterclass?"},
        {"role": "ai", "content": "Python Development Masterclass is an intensive bootcamp."},
    ]
    resolved = memory_manager.resolve_contextual_query(history, "Who teaches it?")
    assert "Python Development Masterclass" in resolved


@pytest.mark.anyio
async def test_resolve_contextual_query_concept_followup():
    """Resolves 'Give an example in C++' when previous turn was 'Explain recursion'."""
    history = [
        {"role": "human", "content": "Explain recursion"},
        {"role": "ai", "content": "Recursion is a programming technique..."},
    ]
    resolved = memory_manager.resolve_contextual_query(history, "Give an example in C++")
    assert "recursion" in resolved.lower()


@pytest.mark.anyio
async def test_conversation_title_auto_generated():
    """Conversation title should automatically be set to the first user message."""
    async with async_session_factory() as session:
        conv = await memory_manager.get_or_create_conversation(session)
        await memory_manager.save_message(session, conv.id, MessageRole.HUMAN, "What is Machine Learning?")

        full_conv = await memory_manager.get_conversation_messages(session, conv.id)
        assert full_conv is not None
        assert "What is Machine Learning?" in full_conv["title"]


@pytest.mark.anyio
async def test_save_and_retrieve_message_with_sources():
    """AI messages with SourceInfo citations should persist and deserialize correctly."""
    async with async_session_factory() as session:
        conv = await memory_manager.get_or_create_conversation(session)
        sources = [
            SourceInfo(
                document="Eduzyra Course Catalog",
                page=None,
                section=None,
                confidence_score=1.0,
                source_type="course_catalog",
            )
        ]
        await memory_manager.save_message(session, conv.id, MessageRole.AI, "Course details here", sources=sources)

        full_conv = await memory_manager.get_conversation_messages(session, conv.id)
        assert full_conv is not None
        assert len(full_conv["messages"]) == 1
        saved_sources = full_conv["messages"][0]["sources"]
        assert saved_sources is not None
        assert saved_sources[0]["document"] == "Eduzyra Course Catalog"

"""
Memory Manager for EduBot.

=== WHAT IS CONVERSATION MEMORY? ===
By default, every API call to an LLM is independent — the LLM has NO memory
of previous messages. Each request is a blank slate.

To make the chatbot remember context, we manually:
1. Store every message in the database (SQLite)
2. Before each new request, load the last N messages
3. Include those messages in the prompt sent to the LLM

This gives the ILLUSION of memory, even though the LLM itself is stateless.

=== WHY A WINDOW? ===
We don't load ALL messages — just the last N (default: 10).
Why?
- LLMs have a limited context window (max tokens they can process)
- Old messages may be irrelevant
- Performance: fewer messages = faster processing

=== FUTURE ENHANCEMENT ===
More sophisticated memory strategies exist:
- Summary memory: Summarize old messages instead of discarding them
- Entity memory: Track key entities mentioned in the conversation
- Vector memory: Use embeddings to find relevant past messages
But for now, a simple window works great.
"""

import json
import re
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import Conversation, Message
from app.models.enums import MessageRole
from app.models.schemas import SourceInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """
    Manages conversation history and message persistence.

    Provides methods to:
    - Create new conversations
    - Save messages (human + AI)
    - Load recent chat history for context
    - Retrieve full conversation details
    """

    def __init__(self) -> None:
        """Initialize the memory manager."""
        self._settings = get_settings()

    async def get_or_create_conversation(
        self,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
    ) -> Conversation:
        """
        Get an existing conversation or create a new one.

        Parameters
        ----------
        session : AsyncSession
            Database session
        conversation_id : str, optional
            If provided, loads the existing conversation.
            If None, creates a new conversation.

        Returns
        -------
        Conversation
            The conversation object
        """
        if conversation_id:
            # Try to find existing conversation
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()

            if conversation:
                logger.debug(f"Loaded existing conversation: {conversation_id}")
                return conversation
            else:
                logger.warning(
                    f"Conversation {conversation_id} not found. Creating new one."
                )

        # Create a new conversation
        conversation = Conversation()
        session.add(conversation)
        await session.flush()  # Get the generated ID

        logger.info(f"Created new conversation: {conversation.id}")
        return conversation

    async def save_message(
        self,
        session: AsyncSession,
        conversation_id: str,
        role: MessageRole,
        content: str,
        sources: Optional[List[SourceInfo]] = None,
        answer_mode: Optional[str] = None,
    ) -> Message:
        """
        Save a message to the database.

        Parameters
        ----------
        session : AsyncSession
            Database session
        conversation_id : str
            Which conversation this message belongs to
        role : MessageRole
            Who sent it (HUMAN, AI, or SYSTEM)
        content : str
            The message text
        sources : List[SourceInfo], optional
            Source citations (for AI messages)
        answer_mode : str, optional
            Answer mode (course_data, rag, direct, hybrid)

        Returns
        -------
        Message
            The saved message object
        """
        # Serialize sources to JSON string for storage
        sources_json = None
        if sources:
            sources_json = json.dumps([s.model_dump() for s in sources])

        message = Message(
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            sources=sources_json,
            answer_mode=answer_mode,
        )

        session.add(message)
        await session.flush()

        # Update conversation title if this is the first human message
        if role == MessageRole.HUMAN:
            await self._maybe_update_title(session, conversation_id, content)

        logger.debug(
            f"Saved {role.value} message to conversation {conversation_id}: "
            f"{content[:50]}..."
        )

        return message

    async def get_chat_history(
        self,
        session: AsyncSession,
        conversation_id: str,
        window_size: Optional[int] = None,
    ) -> List[dict]:
        """
        Load recent chat history for a conversation with balanced human/ai pairing.

        Parameters
        ----------
        session : AsyncSession
            Database session
        conversation_id : str
            The conversation to load history for
        window_size : int, optional
            How many messages to load. Defaults to config value.

        Returns
        -------
        List[dict]
            Recent messages in chronological order
        """
        if window_size is None:
            window_size = self._settings.MEMORY_WINDOW_SIZE

        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(window_size)
        )

        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order (oldest first)

        # Convert to simple dicts for the LLM
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        logger.debug(
            f"Loaded {len(history)} messages from conversation {conversation_id}."
        )
        return history

    def resolve_contextual_query(
        self,
        chat_history: List[dict],
        current_message: str,
    ) -> str:
        """
        Resolve pronoun references in the current message using chat history.

        Examples:
        - History: "What is Python Development Masterclass?"
          Current: "Who teaches it?"
          Resolved: "Who teaches Python Development Masterclass?"

        - History: "Explain recursion"
          Current: "Give an example in C++"
          Resolved: "Give an example of recursion in C++"
        """
        if not chat_history:
            return current_message

        text = current_message.strip()
        lower_text = text.lower()

        # Check if message contains pronouns or continuation phrases
        pronoun_triggers = [
            " it", " it?", " this", " that", "its ", "the instructor", "the teacher",
            "the price", "the fee", "the duration", "the syllabus", "the deadline",
            "example in ", "code in ", "in c++", "in python", "in java"
        ]
        has_pronoun = any(p in lower_text for p in pronoun_triggers) or lower_text.startswith(("who teaches", "how much is", "how long is", "give an example"))

        if not has_pronoun:
            return current_message

        # Scan previous messages for subject entity
        last_user_query = ""
        last_ai_response = ""
        for msg in reversed(chat_history):
            if msg["role"] in ("human", "user") and not last_user_query:
                last_user_query = msg["content"]
            elif msg["role"] == "ai" and not last_ai_response:
                last_ai_response = msg["content"]

        # Check for course mentions in recent history
        course_names = [
            "Python Development Masterclass",
            "Machine Learning Foundations & Practice",
            "Full-Stack Web Development Bootcamp",
            "Data Structures & Algorithms in C++ & Java",
            "Generative AI & LLM Application Engineering",
            "Cloud Computing & DevOps with AWS & Docker",
            "Data Analytics & Business Intelligence",
            "Cybersecurity Essentials & Ethical Hacking",
        ]
        for c_name in course_names:
            if c_name.lower() in (last_user_query + " " + last_ai_response).lower():
                # Replace pronouns or append entity
                resolved = text
                if " it" in resolved.lower():
                    resolved = re.sub(r"\b(it|this|that)\b", c_name, resolved, flags=re.IGNORECASE)
                elif not any(w.lower() in resolved.lower() for w in c_name.split()[:2]):
                    resolved = f"{resolved} (referring to {c_name})"
                return resolved

        # Check for technical concepts (e.g. recursion, binary search, photosynthesis)
        concept_match = re.search(r"\b(explain|what is|how does)\s+([a-zA-Z0-9\s]+?)(?:\.|\?|$)", last_user_query, re.IGNORECASE)
        if concept_match:
            concept = concept_match.group(2).strip()
            if concept and len(concept) > 2 and concept.lower() not in ("it", "this", "that"):
                if "example in" in lower_text or "in c++" in lower_text or "in python" in lower_text:
                    return f"{text} of {concept}"
                if " it" in lower_text:
                    return re.sub(r"\b(it|this|that)\b", concept, text, flags=re.IGNORECASE)

        return current_message

    async def get_conversations(
        self,
        session: AsyncSession,
    ) -> List[dict]:
        """
        Get all conversations with message counts.

        Returns a list of conversation summaries for the sidebar.
        """
        result = await session.execute(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        conversations = list(result.scalars().all())

        summaries = []
        for conv in conversations:
            # Count messages for this conversation
            count_result = await session.execute(
                select(func.count(Message.id))
                .where(Message.conversation_id == conv.id)
            )
            message_count = count_result.scalar() or 0

            summaries.append({
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "message_count": message_count,
            })

        return summaries

    async def get_conversation_messages(
        self,
        session: AsyncSession,
        conversation_id: str,
    ) -> Optional[dict]:
        """
        Get a full conversation with all its messages.

        Returns None if the conversation doesn't exist.
        """
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            return None

        # Load all messages
        msg_result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = list(msg_result.scalars().all())

        # Parse source JSON strings back into SourceInfo objects
        message_dicts = []
        for msg in messages:
            sources = None
            if msg.sources:
                try:
                    sources = json.loads(msg.sources)
                except json.JSONDecodeError:
                    sources = None

            message_dicts.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "sources": sources,
                "answer_mode": msg.answer_mode,
                "created_at": msg.created_at,
            })

        return {
            "id": conversation.id,
            "title": conversation.title,
            "messages": message_dicts,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
        }

    async def _maybe_update_title(
        self,
        session: AsyncSession,
        conversation_id: str,
        first_message: str,
    ) -> None:
        """
        Set the conversation title from the first human message.

        Takes the first 50 characters of the message as the title.
        Only sets it if the conversation doesn't already have a title.
        """
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation and not conversation.title:
            # Truncate to 50 characters and add ellipsis if needed
            title = first_message[:50]
            if len(first_message) > 50:
                title += "..."
            conversation.title = title
            logger.debug(f"Set conversation title: '{title}'")


# ============================================
# SINGLETON INSTANCE
# ============================================
memory_manager = MemoryManager()

"""
Chat Service for EduBot — Hybrid Mode Orchestrator.

=== WHAT IS THE CHAT SERVICE? ===
This is the ORCHESTRATOR — the conductor of the orchestra.
It coordinates all components to handle a chat message:

1. Memory Manager → Load conversation history
2. RAG Engine → Intelligent routing (RAG vs Direct LLM)
3. LLM Service → Generate a response (streaming)
4. Memory Manager → Save the response

=== HYBRID MODE ===
The chat service now supports two answer modes:
- RAG Mode: Answer from knowledge base documents (with citations)
- Direct Mode: Answer from LLM's general knowledge

The RAG Engine's intelligent router decides which mode to use
based on semantic similarity scores. The chat service streams
the response and includes the answer_mode in the events so
the frontend knows how to display the answer.
"""

import json
from typing import AsyncGenerator, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.memory_manager import memory_manager
from app.core.rag_engine import rag_engine
from app.models.enums import AnswerMode, MessageRole
from app.models.schemas import SourceInfo, StreamEvent
from app.services.llm_service import llm_service
from app.utils.exceptions import ChatServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ChatService:
    """
    Orchestrates the complete chat flow with hybrid mode support.

    Coordinates Memory, RAG (with intelligent routing), and LLM
    to process user messages and generate streaming responses.
    """

    async def handle_message_stream(
        self,
        user_message: str,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Handle a user message and return a streaming SSE response.

        The flow includes intelligent routing:
        1. Get or create conversation
        2. Save user message
        3. Send 'start' event
        4. Load chat history
        5. RAG Engine decides: RAG mode or Direct mode
        6. Send 'mode' event (answer_mode)
        7. Stream LLM response tokens
        8. Save AI response
        9. Send source citations
        10. Send 'end' event

        Yields
        ------
        str
            SSE-formatted event strings
        """
        try:
            # Step 1: Get or create conversation
            conversation = await memory_manager.get_or_create_conversation(
                session=session,
                conversation_id=conversation_id,
            )
            conv_id = conversation.id

            # Step 2: Save the user's message
            await memory_manager.save_message(
                session=session,
                conversation_id=conv_id,
                role=MessageRole.HUMAN,
                content=user_message,
            )

            # Step 3: Send "start" event with conversation ID
            yield self._format_sse_event(
                StreamEvent(event="start", conversation_id=conv_id)
            )

            # Step 4: Load chat history (last N messages)
            chat_history = await memory_manager.get_chat_history(
                session=session,
                conversation_id=conv_id,
            )

            # Step 5: RAG Engine — Intelligent Routing
            # This is where the magic happens: the RAG engine decides
            # whether to use document context or general knowledge
            prompt, sources, answer_mode = await rag_engine.build_prompt(
                user_message=user_message,
                chat_history=chat_history,
            )

            logger.info(f"Answer mode: {answer_mode.value}")

            # Step 6: Send answer mode event immediately
            # This lets the frontend show the mode indicator during streaming
            yield self._format_sse_event(
                StreamEvent(event="mode", answer_mode=answer_mode.value)
            )

            # Step 7: Get system prompt
            system_prompt = rag_engine.get_system_prompt()

            # Step 8: Stream the LLM response
            full_response = ""
            async for token in llm_service.generate_stream(
                system_prompt=system_prompt,
                chat_history=chat_history,
                user_message=prompt,
            ):
                full_response += token
                yield self._format_sse_event(
                    StreamEvent(event="token", token=token)
                )

            # Step 9: Save the AI's complete response
            await memory_manager.save_message(
                session=session,
                conversation_id=conv_id,
                role=MessageRole.AI,
                content=full_response,
                sources=sources if sources else None,
            )

            # Step 10: Send source citations + answer mode
            if sources:
                yield self._format_sse_event(
                    StreamEvent(
                        event="sources",
                        sources=sources,
                        answer_mode=answer_mode.value,
                    )
                )
            else:
                # Even without sources, tell the frontend the answer mode
                yield self._format_sse_event(
                    StreamEvent(
                        event="sources",
                        sources=[],
                        answer_mode=answer_mode.value,
                    )
                )

            # Step 11: Send "end" event
            yield self._format_sse_event(StreamEvent(event="end"))

            logger.info(
                f"Chat completed. Conversation: {conv_id}, "
                f"Mode: {answer_mode.value}, "
                f"Response length: {len(full_response)} chars, "
                f"Sources: {len(sources)}"
            )

        except Exception as e:
            logger.error(f"Chat service error: {e}", exc_info=True)
            yield self._format_sse_event(
                StreamEvent(event="error", error=str(e))
            )
            yield self._format_sse_event(StreamEvent(event="end"))

    def _format_sse_event(self, event: StreamEvent) -> str:
        """Format a StreamEvent as an SSE JSON string."""
        return json.dumps(event.model_dump(exclude_none=True))


# ============================================
# SINGLETON INSTANCE
# ============================================
chat_service = ChatService()

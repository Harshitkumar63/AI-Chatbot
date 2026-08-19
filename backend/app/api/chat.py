"""
Chat API Endpoint.

=== WHAT DOES THIS ENDPOINT DO? ===
This is the MAIN endpoint of the application — it handles chat messages.

When a user sends a message:
1. The frontend sends a POST request to /api/chat
2. This endpoint receives it, processes it through the chat pipeline
3. It streams the response back using Server-Sent Events (SSE)

=== WHAT IS SSE? ===
Server-Sent Events is a protocol where the server pushes data to the client
in real-time. Unlike WebSockets (which are bidirectional), SSE is one-way:
server → client. Perfect for streaming LLM responses.

The client opens a connection, and the server sends events like:
  data: {"event": "start", "conversation_id": "abc-123"}
  data: {"event": "token", "token": "Machine"}
  data: {"event": "token", "token": " learning"}
  data: {"event": "end"}

=== WHY SSE OVER WEBSOCKETS? ===
- Simpler to implement
- Works over standard HTTP (no special server setup)
- Auto-reconnects if connection drops
- Perfect for our use case (one-way streaming)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.chat_service import chat_service
from app.db.session import get_session
from app.models.schemas import ChatRequest
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Create a router for chat-related endpoints
router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    summary="Send a chat message",
    description="Send a message and receive a streaming AI response via SSE.",
)
async def send_message(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Handle a chat message and return a streaming response.

    === HOW THIS WORKS ===
    1. FastAPI automatically validates the request body using ChatRequest schema
    2. The Depends(get_session) creates a database session
    3. We pass everything to chat_service which handles the logic
    4. EventSourceResponse streams the results back as SSE events

    Parameters
    ----------
    request : ChatRequest
        The user's message and optional conversation_id
        Automatically validated by FastAPI using Pydantic
    session : AsyncSession
        Database session (injected by FastAPI's dependency system)

    Returns
    -------
    EventSourceResponse
        A streaming SSE response with tokens, sources, and events
    """
    logger.info(
        f"Chat request received. Message: '{request.message[:50]}...', "
        f"Conversation: {request.conversation_id or 'new'}"
    )

    # Create the SSE event stream
    # EventSourceResponse takes an async generator and streams its output
    return EventSourceResponse(
        content=chat_service.handle_message_stream(
            user_message=request.message,
            session=session,
            conversation_id=request.conversation_id,
        ),
        media_type="text/event-stream",
    )

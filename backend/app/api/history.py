"""
Chat History API Endpoints.

Handles retrieving conversation lists and individual conversation details.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.memory_manager import memory_manager
from app.db.session import get_session
from app.models.schemas import ConversationDetailResponse, ConversationResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get(
    "",
    response_model=List[ConversationResponse],
    summary="List all conversations",
    description="Get a list of all conversations with message counts.",
)
async def list_conversations(
    session: AsyncSession = Depends(get_session),
) -> List[ConversationResponse]:
    """
    Get all conversations, ordered by most recent first.

    This is used to populate the conversation sidebar in the UI.
    """
    conversations = await memory_manager.get_conversations(session)

    return [
        ConversationResponse(**conv)
        for conv in conversations
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation details",
    description="Get a specific conversation with all its messages.",
)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> ConversationDetailResponse:
    """
    Get a full conversation with all messages.

    This is used when the user clicks on a conversation
    in the sidebar to load its chat history.
    """
    conversation = await memory_manager.get_conversation_messages(
        session=session,
        conversation_id=conversation_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    return ConversationDetailResponse(**conversation)

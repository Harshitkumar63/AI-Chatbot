"""
LLM Service for EduBot.

=== WHAT DOES THIS SERVICE DO? ===
This service manages the active LLM provider (e.g. Groq, OpenAI, Local).
It provides streaming and non-streaming response generation.

=== MODULAR PROVIDER ARCHITECTURE ===
The service delegates to a pluggable BaseLLMProvider (default: GroqLLMProvider).
This guarantees that changing or adding LLM backends requires zero changes
to chat_service or other application components.
"""

from typing import AsyncGenerator, List, Optional

from app.services.llm_provider import BaseLLMProvider, get_llm_provider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Service coordinating LLM text generation via pluggable providers.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None) -> None:
        """Initialize the LLM service."""
        self._provider: BaseLLMProvider = provider or get_llm_provider()

    @property
    def is_initialized(self) -> bool:
        """Check if the LLM provider is initialized."""
        return self._provider.is_initialized

    async def initialize(self) -> None:
        """Initialize the underlying LLM provider."""
        await self._provider.initialize()

    async def generate(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> str:
        """Generate a complete response (non-streaming)."""
        return await self._provider.generate(
            system_prompt=system_prompt,
            chat_history=chat_history,
            user_message=user_message,
        )

    async def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response (token by token)."""
        async for token in self._provider.generate_stream(
            system_prompt=system_prompt,
            chat_history=chat_history,
            user_message=user_message,
        ):
            yield token


# ============================================
# SINGLETON INSTANCE
# ============================================
llm_service = LLMService()

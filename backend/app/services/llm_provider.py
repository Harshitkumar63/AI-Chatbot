"""
Modular LLM Provider Architecture for Eduzyra.

=== MODULAR PROVIDER PATTERN ===
Defines an abstract base interface (BaseLLMProvider) allowing the chatbot
to seamlessly switch LLM backends (Groq, OpenAI, Anthropic, or Local Ollama/vLLM)
without rewriting core application logic.

Architecture:
    BaseLLMProvider (ABC)
          ▲
          ├── GroqLLMProvider (Active, fast inference)
          ├── OpenAILLMProvider (Future / Fallback)
          └── LocalLLMProvider (Future / Self-hosted)
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional
from pydantic import SecretStr
from langchain_groq import ChatGroq
from langchain_core.messages import (
    AIMessage,
    BaseMessage as LCMessage,
    HumanMessage,
    SystemMessage,
)

from app.config import get_settings
from app.utils.exceptions import LLMServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connections/clients."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if provider is ready."""
        pass

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> str:
        """Generate a complete non-streaming response."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously."""
        pass


class GroqLLMProvider(BaseLLMProvider):
    """
    Groq LPU LLM Provider offering high-throughput inference for Llama 3 and GPT-OSS models.
    """

    def __init__(self) -> None:
        self._client: Optional[ChatGroq] = None
        self._streaming_client: Optional[ChatGroq] = None
        self._settings = get_settings()

    @property
    def is_initialized(self) -> bool:
        return self._client is not None

    async def initialize(self) -> None:
        if self._client is not None:
            return

        if not self._settings.GROQ_API_KEY:
            raise LLMServiceError(
                "GROQ_API_KEY is not set. Please obtain a free key at https://console.groq.com"
            )

        try:
            logger.info(f"Initializing Groq LLM Provider with model: {self._settings.LLM_MODEL_NAME}")

            self._client = ChatGroq(
                api_key=SecretStr(self._settings.GROQ_API_KEY),
                model=self._settings.LLM_MODEL_NAME,
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.LLM_MAX_TOKENS,
                streaming=False,
            )

            self._streaming_client = ChatGroq(
                api_key=SecretStr(self._settings.GROQ_API_KEY),
                model=self._settings.LLM_MODEL_NAME,
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.LLM_MAX_TOKENS,
                streaming=True,
            )

            logger.info("Groq LLM Provider initialized successfully.")

        except Exception as e:
            logger.error(f"Failed to initialize Groq LLM Provider: {e}")
            raise LLMServiceError(f"Failed to initialize Groq LLM: {e}") from e

    def _build_messages(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> List[LCMessage]:
        messages: List[LCMessage] = [SystemMessage(content=system_prompt)]

        for msg in chat_history:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))
        return messages

    async def generate(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> str:
        if self._client is None:
            raise LLMServiceError("Groq LLM Provider not initialized.")

        try:
            messages = self._build_messages(system_prompt, chat_history, user_message)
            response = await self._client.ainvoke(messages)
            if isinstance(response.content, str):
                return response.content
            return str(response.content)
        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            raise LLMServiceError(f"Groq generation failed: {e}") from e

    async def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        if self._streaming_client is None:
            raise LLMServiceError("Groq LLM Provider not initialized.")

        try:
            messages = self._build_messages(system_prompt, chat_history, user_message)
            async for chunk in self._streaming_client.astream(messages):
                if chunk.content:
                    if isinstance(chunk.content, str):
                        yield chunk.content
                    else:
                        yield str(chunk.content)
        except Exception as e:
            logger.error(f"Groq streaming failed: {e}")
            raise LLMServiceError(f"Groq streaming failed: {e}") from e


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider instance.
    """
    return GroqLLMProvider()

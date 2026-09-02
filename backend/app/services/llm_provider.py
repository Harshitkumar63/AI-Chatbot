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
    def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously."""
        pass


# Fallback models on Groq with active API support
DEFAULT_FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound-mini",
]


class GroqLLMProvider(BaseLLMProvider):
    """
    Groq LPU LLM Provider offering high-throughput inference for Llama 3.3, Qwen 3.8 27B, and fallback models.
    Includes automatic rate-limit and quota fallback across high-capacity models.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ChatGroq] = {}
        self._streaming_clients: dict[str, ChatGroq] = {}
        self._settings = get_settings()

    @property
    def is_initialized(self) -> bool:
        return bool(self._clients)

    def _get_client(self, model: str, streaming: bool = False) -> ChatGroq:
        """Get or create a ChatGroq client for the specified model."""
        cache = self._streaming_clients if streaming else self._clients
        if model not in cache:
            cache[model] = ChatGroq(
                api_key=SecretStr(self._settings.GROQ_API_KEY),
                model=model,
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.LLM_MAX_TOKENS,
                streaming=streaming,
            )
        return cache[model]

    def _get_model_candidates(self) -> List[str]:
        """Return the list of models to try in priority order."""
        primary = self._settings.LLM_MODEL_NAME
        candidates = [primary]
        for fallback in DEFAULT_FALLBACK_MODELS:
            if fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Check if an exception is due to rate limits, quotas, or model unavailability."""
        err_msg = str(exc).lower()
        keywords = [
            "rate_limit",
            "rate limit",
            "429",
            "maximum limits",
            "tokens per minute",
            "requests per minute",
            "tpm",
            "rpm",
            "quota",
            "resource_exhausted",
            "decommissioned",
            "model_not_found",
        ]
        return any(kw in err_msg for kw in keywords)

    async def initialize(self) -> None:
        if self.is_initialized:
            return

        if not self._settings.GROQ_API_KEY:
            raise LLMServiceError(
                "GROQ_API_KEY is not set. Please obtain a free key at https://console.groq.com"
            )

        try:
            logger.info(f"Initializing Groq LLM Provider with model: {self._settings.LLM_MODEL_NAME}")
            self._get_client(self._settings.LLM_MODEL_NAME, streaming=False)
            self._get_client(self._settings.LLM_MODEL_NAME, streaming=True)
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
        if not self.is_initialized:
            raise LLMServiceError("Groq LLM Provider not initialized.")

        models_to_try = self._get_model_candidates()
        last_error: Optional[Exception] = None

        for model in models_to_try:
            try:
                client = self._get_client(model, streaming=False)
                messages = self._build_messages(system_prompt, chat_history, user_message)
                response = await client.ainvoke(messages)
                if isinstance(response.content, str):
                    return response.content
                return str(response.content)
            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e) and model != models_to_try[-1]:
                    logger.warning(
                        f"Groq model '{model}' encountered rate/quota limit. Falling back to next available model..."
                    )
                    continue
                logger.error(f"Groq generation failed on model '{model}': {e}")
                break

        raise LLMServiceError(f"Groq generation failed across models: {last_error}") from last_error

    async def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        if not self.is_initialized:
            raise LLMServiceError("Groq LLM Provider not initialized.")

        models_to_try = self._get_model_candidates()
        last_error: Optional[Exception] = None
        messages = self._build_messages(system_prompt, chat_history, user_message)

        for model in models_to_try:
            tokens_yielded = 0
            try:
                client = self._get_client(model, streaming=True)
                async for chunk in client.astream(messages):
                    if chunk.content:
                        token = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        tokens_yielded += 1
                        yield token
                # Completed successfully
                return
            except Exception as e:
                last_error = e
                # If failed before yielding any tokens, fall back to next model
                if tokens_yielded == 0 and self._is_rate_limit_error(e) and model != models_to_try[-1]:
                    logger.warning(
                        f"Groq model '{model}' rate-limited before response started. Falling back to next model..."
                    )
                    continue
                logger.error(f"Groq streaming failed on model '{model}': {e}")
                raise LLMServiceError(f"Groq streaming failed: {e}") from e

        if last_error:
            raise LLMServiceError(f"Groq streaming failed across all available models: {last_error}") from last_error


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider instance.
    """
    return GroqLLMProvider()

"""
LLM Service for EduBot.

=== WHAT DOES THIS SERVICE DO? ===
This service communicates with the Groq API to generate AI responses.
It sends prompts and receives generated text, with streaming support.

=== WHAT IS GROQ? ===
Groq is a company that provides ultra-fast LLM inference.
They have custom hardware (LPU — Language Processing Unit) that runs
open-source models like Llama 3.1 at incredible speeds.

Key facts:
- Free tier: ~30 requests/minute, 6,000 tokens/minute
- Speed: 10-100x faster than running models locally
- Models: Llama 3.1 (8B, 70B), Mixtral 8x7B
- API: Compatible with OpenAI's API format

=== WHY A WRAPPER CLASS? ===
Same reasons as the embedding service:
1. Abstraction: Switch LLM providers without changing other code
2. Error handling: Translate API errors into our exception types
3. Streaming: Encapsulate the complex streaming logic
4. Configuration: Centralize all LLM settings

=== WHAT IS STREAMING? ===
Without streaming:
  → Wait 5 seconds → Get entire response at once
  User experience: "Is it frozen? Is it working?"

With streaming:
  → Get tokens one by one as they're generated
  → Words appear like someone is typing
  User experience: "It's thinking and responding!"

Technically, streaming uses an "async generator" — a function that
yields values one at a time instead of returning all at once.
"""

from typing import AsyncGenerator, List, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage as LCMessage

from app.config import get_settings
from app.utils.exceptions import LLMServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Service for interacting with the Groq LLM API.

    Provides both streaming and non-streaming response generation.
    """

    def __init__(self) -> None:
        """Initialize the LLM service (client not yet created)."""
        self._client: Optional[ChatGroq] = None
        self._streaming_client: Optional[ChatGroq] = None
        self._settings = get_settings()

    @property
    def is_initialized(self) -> bool:
        """Check if the LLM client is ready."""
        return self._client is not None

    async def initialize(self) -> None:
        """
        Initialize the Groq LLM client.

        Creates two clients:
        1. Regular client — for non-streaming responses
        2. Streaming client — for token-by-token streaming

        Why two clients? LangChain's ChatGroq needs streaming=True
        set at creation time, not per-request. So we create both.
        """
        if self._client is not None:
            logger.debug("LLM service already initialized.")
            return

        if not self._settings.GROQ_API_KEY:
            raise LLMServiceError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
            )

        try:
            logger.info(f"Initializing LLM service with model: {self._settings.LLM_MODEL_NAME}")

            # Regular client (returns complete responses)
            self._client = ChatGroq(
                api_key=self._settings.GROQ_API_KEY,
                model_name=self._settings.LLM_MODEL_NAME,
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.LLM_MAX_TOKENS,
                streaming=False,
            )

            # Streaming client (returns tokens one by one)
            self._streaming_client = ChatGroq(
                api_key=self._settings.GROQ_API_KEY,
                model_name=self._settings.LLM_MODEL_NAME,
                temperature=self._settings.LLM_TEMPERATURE,
                max_tokens=self._settings.LLM_MAX_TOKENS,
                streaming=True,
            )

            logger.info("LLM service initialized successfully.")

        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            raise LLMServiceError(f"Failed to initialize LLM: {e}") from e

    def _build_messages(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> List[LCMessage]:
        """
        Build the message list for the LLM.

        The LLM expects messages in this format:
        [
            SystemMessage("You are a helpful assistant..."),
            HumanMessage("What is ML?"),          # from history
            AIMessage("ML is..."),                 # from history
            HumanMessage("Tell me more"),          # current question
        ]

        Parameters
        ----------
        system_prompt : str
            The system prompt (AI's personality + context)
        chat_history : List[dict]
            Previous messages as [{"role": "human", "content": "..."}, ...]
        user_message : str
            The current user question

        Returns
        -------
        List[LCMessage]
            LangChain message objects ready for the LLM
        """
        messages: List[LCMessage] = [SystemMessage(content=system_prompt)]

        # Add conversation history
        for msg in chat_history:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        # Add the current user message
        messages.append(HumanMessage(content=user_message))

        return messages

    async def generate(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> str:
        """
        Generate a complete response (non-streaming).

        Use this when you don't need token-by-token output.
        Returns the full response as a single string.
        """
        if self._client is None:
            raise LLMServiceError("LLM service not initialized.")

        try:
            messages = self._build_messages(system_prompt, chat_history, user_message)
            response = await self._client.ainvoke(messages)
            return response.content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise LLMServiceError(f"Failed to generate response: {e}") from e

    async def generate_stream(
        self,
        system_prompt: str,
        chat_history: List[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response (token by token).

        This is an async generator — it yields tokens one at a time.

        === WHAT IS AN ASYNC GENERATOR? ===
        A normal function returns one value:
            def get_answer(): return "ML is a branch of AI"

        A generator yields multiple values:
            def get_tokens():
                yield "ML"
                yield " is"
                yield " a"
                yield " branch"

        An ASYNC generator yields values that come from async operations:
            async def stream_tokens():
                async for chunk in llm.astream(messages):
                    yield chunk.content

        Usage:
            async for token in llm_service.generate_stream(...):
                print(token, end="")  # Prints: ML is a branch of AI

        Parameters
        ----------
        system_prompt : str
            The system prompt with context
        chat_history : List[dict]
            Previous conversation messages
        user_message : str
            Current user question

        Yields
        ------
        str
            Individual tokens (words/pieces) of the response
        """
        if self._streaming_client is None:
            raise LLMServiceError("LLM service not initialized.")

        try:
            messages = self._build_messages(system_prompt, chat_history, user_message)

            # astream() returns an async iterator of chunks
            # Each chunk contains a piece of the response
            async for chunk in self._streaming_client.astream(messages):
                # chunk.content may be empty for some events
                if chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise LLMServiceError(f"Streaming failed: {e}") from e


# ============================================
# SINGLETON INSTANCE
# ============================================
llm_service = LLMService()

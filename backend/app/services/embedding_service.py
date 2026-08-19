"""
Embedding Service for EduBot.

=== WHAT DOES THIS SERVICE DO? ===
This service converts text into numerical vectors (embeddings).
These vectors capture the MEANING of the text, allowing us to
find similar content using math (cosine similarity).

=== HOW EMBEDDINGS WORK (SIMPLIFIED) ===

1. Input: "Machine learning is a type of AI"
2. The model (all-MiniLM-L6-v2) processes this text
3. Output: [0.023, -0.145, 0.892, ...] (384 numbers)

These 384 numbers represent the TEXT's position in a
384-dimensional "meaning space". Texts with similar meaning
have similar numbers (they're "close" in this space).

=== WHY A WRAPPER CLASS? ===
We wrap the embedding model in our own class for:
1. Abstraction: The rest of the app doesn't know/care about Sentence-Transformers
2. Swappability: We could switch to OpenAI embeddings by changing only this file
3. Error handling: We catch and translate errors into our own exception types
4. Lazy loading: The model is loaded only when first needed (saves startup time)

=== THE MODEL: all-MiniLM-L6-v2 ===
- Created by: Microsoft
- Size: ~80MB (small enough to run on any laptop)
- Dimensions: 384 (good balance of quality vs. speed)
- Speed: ~14,000 sentences/second on CPU
- Quality: Excellent for semantic similarity tasks
- License: Apache 2.0 (free for commercial use)
"""

from typing import List, Optional

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings
from app.utils.exceptions import VectorStoreError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using a local model.

    This class follows the Singleton pattern — only ONE instance exists.
    The model is loaded once and reused for all embedding requests.

    Usage:
        service = EmbeddingService()
        await service.initialize()
        vector = await service.embed_text("What is machine learning?")
    """

    def __init__(self) -> None:
        """Initialize the service (model is NOT loaded yet)."""
        self._model: Optional[HuggingFaceEmbeddings] = None
        self._settings = get_settings()

    @property
    def is_initialized(self) -> bool:
        """Check if the embedding model is loaded."""
        return self._model is not None

    async def initialize(self) -> None:
        """
        Load the embedding model.

        This downloads the model (~80MB) on first run.
        Subsequent runs use the cached version.

        We do this as a separate method (not in __init__) because:
        1. Model loading is slow (~2-5 seconds)
        2. We want to control WHEN it happens (during app startup)
        3. We can show progress/errors to the user
        """
        if self._model is not None:
            logger.debug("Embedding model already initialized.")
            return

        try:
            logger.info(
                f"Loading embedding model: {self._settings.EMBEDDING_MODEL_NAME}"
            )

            # HuggingFaceEmbeddings is LangChain's wrapper around sentence-transformers
            # model_kwargs: passed to the underlying SentenceTransformer model
            # encode_kwargs: passed to model.encode() when generating embeddings
            self._model = HuggingFaceEmbeddings(
                model_name=self._settings.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},  # Use CPU (works everywhere)
                encode_kwargs={"normalize_embeddings": True},  # Normalize for cosine similarity
            )

            logger.info("Embedding model loaded successfully.")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise VectorStoreError(f"Failed to initialize embedding model: {e}") from e

    def get_embeddings_model(self) -> HuggingFaceEmbeddings:
        """
        Get the underlying LangChain embeddings model.

        This is used by FAISS and LangChain components that need
        the embeddings model directly.

        Raises VectorStoreError if the model hasn't been initialized.
        """
        if self._model is None:
            raise VectorStoreError("Embedding model not initialized. Call initialize() first.")
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        """
        Convert a single text string into an embedding vector.

        Parameters
        ----------
        text : str
            The text to embed (e.g., a user's question)

        Returns
        -------
        List[float]
            A list of 384 floating-point numbers representing the text's meaning.

        Example
        -------
            vector = await service.embed_text("What is Python?")
            len(vector)  # 384
        """
        if self._model is None:
            raise VectorStoreError("Embedding model not initialized.")

        try:
            # embed_query is for a single text (vs. embed_documents for batches)
            vector = self._model.embed_query(text)
            return vector

        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise VectorStoreError(f"Embedding failed: {e}") from e

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Convert multiple texts into embedding vectors (batch operation).

        This is more efficient than calling embed_text() in a loop
        because the model processes all texts together.

        Parameters
        ----------
        texts : List[str]
            A list of texts to embed (e.g., document chunks)

        Returns
        -------
        List[List[float]]
            A list of embedding vectors, one per text.
        """
        if self._model is None:
            raise VectorStoreError("Embedding model not initialized.")

        try:
            logger.debug(f"Embedding {len(texts)} texts...")
            vectors = self._model.embed_documents(texts)
            logger.debug(f"Successfully embedded {len(vectors)} texts.")
            return vectors

        except Exception as e:
            logger.error(f"Failed to embed texts: {e}")
            raise VectorStoreError(f"Batch embedding failed: {e}") from e


# ============================================
# SINGLETON INSTANCE
# ============================================
# We create a single global instance that the entire app shares.
# This ensures the model is loaded only ONCE.
embedding_service = EmbeddingService()

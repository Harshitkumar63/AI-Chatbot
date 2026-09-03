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

=== DEPLOYMENT MODES ===
This service supports TWO embedding backends:

1. LOCAL MODE (default, for development):
   - Uses sentence-transformers + PyTorch (~2.5 GB disk)
   - No API key needed, runs entirely offline
   - Set USE_CLOUD_EMBEDDINGS=false (or omit)

2. CLOUD MODE (for Render / production):
   - Uses Hugging Face Inference API (~0 GB extra disk)
   - Requires a free HUGGINGFACE_API_KEY
   - Set USE_CLOUD_EMBEDDINGS=true
   - Same model (all-MiniLM-L6-v2), identical quality

=== THE MODEL: all-MiniLM-L6-v2 ===
- Created by: Microsoft
- Size: ~80MB (small enough to run on any laptop)
- Dimensions: 384 (good balance of quality vs. speed)
- Speed: ~14,000 sentences/second on CPU
- Quality: Excellent for semantic similarity tasks
- License: Apache 2.0 (free for commercial use)
"""

from typing import List, Optional

from langchain_core.embeddings import Embeddings

from app.config import get_settings
from app.utils.exceptions import VectorStoreError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using local or cloud models.

    This class follows the Singleton pattern — only ONE instance exists.
    The model is loaded once and reused for all embedding requests.

    The backend is chosen automatically based on config:
    - USE_CLOUD_EMBEDDINGS=true  → HF Inference API (lightweight, for production)
    - USE_CLOUD_EMBEDDINGS=false → Local sentence-transformers (for development)

    Usage:
        service = EmbeddingService()
        await service.initialize()
        vector = await service.embed_text("What is machine learning?")
    """

    def __init__(self) -> None:
        """Initialize the service (model is NOT loaded yet)."""
        self._model: Optional[Embeddings] = None
        self._settings = get_settings()
        self._is_cloud: bool = False

    @property
    def is_initialized(self) -> bool:
        """Check if the embedding model is loaded."""
        return self._model is not None

    async def initialize(self) -> None:
        """
        Load the embedding model (local or cloud).

        In LOCAL mode: Downloads the model (~80MB) on first run.
        Subsequent runs use the cached version.

        In CLOUD mode: Validates the API key and creates the API client.
        No model download required — saves ~2.5 GB of disk space.

        We do this as a separate method (not in __init__) because:
        1. Model loading is slow (~2-5 seconds locally)
        2. We want to control WHEN it happens (during app startup)
        3. We can show progress/errors to the user
        """
        if self._model is not None:
            logger.debug("Embedding model already initialized.")
            return

        # Decide which backend to use based on config
        use_cloud = (
            self._settings.USE_CLOUD_EMBEDDINGS
            and self._settings.HUGGINGFACE_API_KEY
        )

        try:
            if use_cloud:
                self._initialize_cloud()
            else:
                self._initialize_local()

            logger.info("Embedding model loaded successfully.")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise VectorStoreError(f"Failed to initialize embedding model: {e}") from e

    def _initialize_cloud(self) -> None:
        """
        Initialize cloud-based embeddings via Hugging Face Inference API.

        This avoids installing PyTorch and sentence-transformers entirely,
        reducing the Docker image from ~2.5 GB to ~180 MB.
        """
        from langchain_huggingface import HuggingFaceEndpointEmbeddings

        model_id = f"sentence-transformers/{self._settings.EMBEDDING_MODEL_NAME}"
        logger.info(
            f"Initializing CLOUD embeddings via HF Inference API: {model_id}"
        )

        self._model = HuggingFaceEndpointEmbeddings(
            model=model_id,
            huggingfacehub_api_token=self._settings.HUGGINGFACE_API_KEY,
        )
        self._is_cloud = True

    def _initialize_local(self) -> None:
        """
        Initialize local embeddings using sentence-transformers + PyTorch.

        This requires ~2.5 GB of disk space but runs entirely offline.
        Best for local development.
        """
        from langchain_huggingface import HuggingFaceEmbeddings

        logger.info(
            f"Loading LOCAL embedding model: {self._settings.EMBEDDING_MODEL_NAME}"
        )

        # HuggingFaceEmbeddings is LangChain's wrapper around sentence-transformers
        # Try loading from local cache first for instant startup without network timeouts
        try:
            self._model = HuggingFaceEmbeddings(
                model_name=self._settings.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu", "local_files_only": True},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception:
            self._model = HuggingFaceEmbeddings(
                model_name=self._settings.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        self._is_cloud = False

    def get_embeddings_model(self) -> Embeddings:
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

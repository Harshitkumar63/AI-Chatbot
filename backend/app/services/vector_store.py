"""
Vector Store Service for EduBot.

=== WHAT DOES THIS SERVICE DO? ===
This service manages FAISS — our vector database.
It handles:
1. Creating new FAISS indexes
2. Adding document chunks (text + embeddings) to the index
3. Searching for similar chunks (given a user's question)
4. Saving/loading the index to/from disk

=== WHAT IS FAISS? ===
FAISS (Facebook AI Similarity Search) is a library by Meta AI that
efficiently searches through large collections of vectors.

Think of it as a specialized search engine:
- Google searches by keywords → "machine learning" matches pages with those words
- FAISS searches by meaning → "how do computers learn?" matches content about ML

=== HOW FAISS WORKS (SIMPLIFIED) ===
1. You add vectors (embeddings) to the index
2. FAISS organizes them for fast searching (using smart data structures)
3. When you search, FAISS finds the K nearest neighbors
4. "Nearest" = most similar meaning (using cosine/L2 distance)

=== WHY FAISS OVER OTHER OPTIONS? ===
- Free and open-source (by Meta/Facebook)
- Runs locally (no cloud service needed)
- Blazing fast (can search millions of vectors in milliseconds)
- Battle-tested (used in production at Meta)
- Simple API
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from app.config import get_settings
from app.services.embedding_service import embedding_service
from app.utils.exceptions import VectorStoreError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStoreService:
    """
    Service for managing the FAISS vector store.

    Provides methods to add documents, search for similar content,
    and persist the index to disk.
    """

    def __init__(self) -> None:
        """Initialize the service (FAISS index not yet loaded)."""
        self._store: Optional[FAISS] = None
        self._settings = get_settings()

    @property
    def is_ready(self) -> bool:
        """Check if the FAISS index is loaded and ready for queries."""
        return self._store is not None

    @property
    def document_count(self) -> int:
        """Get the number of documents in the index."""
        if self._store is None:
            return 0
        return len(self._store.docstore._dict)

    async def initialize(self) -> None:
        """
        Initialize the vector store.

        Tries to load an existing FAISS index from disk.
        If no index exists (first run), that's okay — it will be
        created when the first document is uploaded.
        """
        index_path = self._settings.vector_store_dir_path
        index_file = index_path / "index.faiss"

        if index_file.exists():
            try:
                logger.info(f"Loading existing FAISS index from: {index_path}")

                embeddings_model = embedding_service.get_embeddings_model()
                self._store = FAISS.load_local(
                    folder_path=str(index_path),
                    embeddings=embeddings_model,
                    allow_dangerous_deserialization=True,  # Required for loading pickled data
                )

                logger.info(
                    f"FAISS index loaded. Documents: {self.document_count}"
                )

            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}. Starting fresh.")
                self._store = None
        else:
            logger.info("No existing FAISS index found. Will create on first document upload.")

    async def add_documents(
        self,
        texts: List[str],
        metadatas: List[dict],
    ) -> int:
        """
        Add document chunks to the FAISS index.

        This is called after a PDF is processed:
        1. PDF → extracted text → split into chunks
        2. Each chunk is embedded (converted to a vector)
        3. The chunks + vectors are added to FAISS

        Parameters
        ----------
        texts : List[str]
            The text chunks to add
        metadatas : List[dict]
            Metadata for each chunk (document name, page number, etc.)
            Example: [{"source": "intro_ml.pdf", "page": 3, "chunk": 0}]

        Returns
        -------
        int
            Number of chunks successfully added
        """
        if not texts:
            logger.warning("No texts to add to vector store.")
            return 0

        try:
            embeddings_model = embedding_service.get_embeddings_model()

            # Create LangChain Document objects (text + metadata)
            documents = [
                LCDocument(page_content=text, metadata=meta)
                for text, meta in zip(texts, metadatas)
            ]

            if self._store is None:
                # First time — create a new FAISS index from these documents
                logger.info(f"Creating new FAISS index with {len(documents)} chunks.")
                self._store = FAISS.from_documents(
                    documents=documents,
                    embedding=embeddings_model,
                )
            else:
                # Add to existing index
                logger.info(f"Adding {len(documents)} chunks to existing FAISS index.")
                self._store.add_documents(documents)

            # Save to disk (persist the index)
            await self._save_index()

            logger.info(f"Vector store now has {self.document_count} total chunks.")
            return len(documents)

        except Exception as e:
            logger.error(f"Failed to add documents to vector store: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[LCDocument, float]]:
        """
        Search the vector store for chunks similar to the query.

        How search works:
        1. The query text is converted to an embedding vector
        2. FAISS finds the K closest vectors in its index
        3. It returns the corresponding text chunks + similarity scores

        Parameters
        ----------
        query : str
            The user's question (e.g., "What is machine learning?")
        top_k : int, optional
            Number of results to return. Defaults to config value.

        Returns
        -------
        List[Tuple[LCDocument, float]]
            List of (document_chunk, similarity_score) tuples.
            Higher score = more similar.

        Example
        -------
            results = await vector_store.search("What is ML?")
            for doc, score in results:
                print(f"Score: {score:.3f}")
                print(f"Text: {doc.page_content[:100]}...")
                print(f"Source: {doc.metadata['source']}")
        """
        if self._store is None:
            logger.debug("Vector store is empty — no documents indexed yet.")
            return []

        if top_k is None:
            top_k = self._settings.RETRIEVAL_TOP_K

        try:
            # similarity_search_with_score returns both the document and its score
            results = self._store.similarity_search_with_score(
                query=query,
                k=top_k,
            )

            logger.debug(
                f"Search for '{query[:50]}...' returned {len(results)} results."
            )

            return results

        except Exception as e:
            logger.error(f"Vector store search failed: {e}")
            raise VectorStoreError(f"Search failed: {e}") from e

    async def _save_index(self) -> None:
        """
        Save the FAISS index to disk.

        Why save to disk?
        - FAISS is an in-memory index (lives in RAM)
        - If the server restarts, the index would be lost
        - Saving to disk lets us reload it on startup
        - The saved files are: index.faiss (vectors) + index.pkl (metadata)
        """
        if self._store is None:
            return

        try:
            index_path = self._settings.vector_store_dir_path
            index_path.mkdir(parents=True, exist_ok=True)

            self._store.save_local(folder_path=str(index_path))
            logger.debug(f"FAISS index saved to: {index_path}")

        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise VectorStoreError(f"Failed to save index: {e}") from e

    async def delete_all(self) -> None:
        """
        Delete the entire FAISS index (reset).

        Use this when you want to re-index all documents from scratch.
        """
        self._store = None
        index_path = self._settings.vector_store_dir_path

        # Remove index files from disk
        for file in ["index.faiss", "index.pkl"]:
            filepath = index_path / file
            if filepath.exists():
                os.remove(filepath)
                logger.info(f"Deleted: {filepath}")

        logger.info("Vector store cleared.")


# ============================================
# SINGLETON INSTANCE
# ============================================
vector_store_service = VectorStoreService()

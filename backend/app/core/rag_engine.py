"""
RAG Engine for EduBot — with Intelligent Routing.

=== WHAT IS INTELLIGENT ROUTING? ===
Not every question needs RAG. When a student asks "What is Python?",
the LLM already knows the answer — no document search needed.

But when they ask "What is PW's refund policy?", we MUST search
the knowledge base because that information is organization-specific.

The intelligent router automatically decides:
1. Search FAISS for relevant document chunks
2. Check the similarity scores of the results
3. If scores are HIGH → Use RAG (answer from documents)
4. If scores are LOW → Skip RAG (answer from general knowledge)
5. If vector store is EMPTY → Always use direct LLM

=== HOW SIMILARITY SCORES WORK ===
FAISS returns a distance score for each result. We convert it to
a similarity score (0.0 to 1.0):
- 1.0 = perfect match (identical meaning)
- 0.5 = moderate match
- 0.0 = no match at all

We compare the BEST score against a threshold (default: 0.35).
If the best score is below the threshold, documents aren't relevant enough.

=== ANSWER MODES ===
- RAG: "Based on your uploaded notes, Newton's Second Law states..."
- DIRECT: "Newton's Second Law states F = ma..."  (from LLM knowledge)
"""

from typing import List, Optional, Tuple

from app.config import get_settings
from app.models.enums import AnswerMode
from app.models.schemas import SourceInfo
from app.services.vector_store import vector_store_service
from app.utils.logger import get_logger
from app.utils.prompts import (
    DIRECT_LLM_PROMPT_TEMPLATE,
    NO_CONTEXT_PROMPT_TEMPLATE,
    RAG_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class RAGEngine:
    """
    Retrieval-Augmented Generation engine with intelligent routing.

    Automatically decides whether to use RAG or direct LLM
    based on semantic similarity scores from the vector store.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def build_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
    ) -> Tuple[str, List[SourceInfo], AnswerMode]:
        """
        Build the complete prompt for the LLM with intelligent routing.

        Returns
        -------
        Tuple[str, List[SourceInfo], AnswerMode]
            - The complete prompt string for the LLM
            - List of source citations (empty for direct mode)
            - The answer mode (RAG, DIRECT, or HYBRID)
        """
        # Step 1: Check if vector store has any documents
        if not vector_store_service.is_ready or vector_store_service.document_count == 0:
            logger.info("Vector store empty → Using DIRECT mode (no documents indexed).")
            prompt = self._build_no_context_prompt(user_message, chat_history)
            return prompt, [], AnswerMode.DIRECT

        # Step 2: Search FAISS for relevant chunks
        search_results = await vector_store_service.search(user_message)

        if not search_results:
            logger.info("No search results → Using DIRECT mode.")
            prompt = self._build_direct_prompt(user_message, chat_history)
            return prompt, [], AnswerMode.DIRECT

        # Step 3: INTELLIGENT ROUTING — Check similarity scores
        # FAISS returns L2 distance (lower = more similar)
        # We convert to a similarity score: similarity = 1 / (1 + distance)
        best_score = self._get_best_similarity_score(search_results)
        threshold = self._settings.RAG_SIMILARITY_THRESHOLD

        logger.info(
            f"Routing decision: best_similarity={best_score:.3f}, "
            f"threshold={threshold:.3f}"
        )

        if best_score < threshold:
            # Low confidence — documents aren't relevant to this question
            logger.info(
                f"Score {best_score:.3f} < threshold {threshold:.3f} "
                f"→ Using DIRECT mode (documents not relevant)."
            )
            prompt = self._build_direct_prompt(user_message, chat_history)
            return prompt, [], AnswerMode.DIRECT
        else:
            # High confidence — documents are relevant, use RAG
            logger.info(
                f"Score {best_score:.3f} >= threshold {threshold:.3f} "
                f"→ Using RAG mode (relevant documents found)."
            )
            prompt, sources = self._build_rag_prompt(
                user_message, chat_history, search_results
            )
            return prompt, sources, AnswerMode.RAG

    def _get_best_similarity_score(self, search_results: list) -> float:
        """
        Get the highest similarity score from search results.

        FAISS returns L2 (Euclidean) distance by default:
        - 0.0 = identical vectors
        - Higher = more different

        We convert to similarity (0.0 - 1.0):
        - similarity = 1 / (1 + distance)
        - 1.0 = identical
        - 0.0 = completely different

        Note: When using normalized embeddings (which we do),
        L2 distance ranges from 0 to 2, so similarity ranges
        from 0.33 to 1.0 in practice.
        """
        if not search_results:
            return 0.0

        # search_results is List[Tuple[Document, float]]
        # The float is the L2 distance (lower = better)
        distances = [score for _, score in search_results]
        min_distance = min(distances)

        # Convert L2 distance to similarity score
        similarity = 1.0 / (1.0 + min_distance)
        return similarity

    def _build_rag_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
        search_results: list,
    ) -> Tuple[str, List[SourceInfo]]:
        """Build a RAG prompt with retrieved document context."""
        context_parts: List[str] = []
        sources: List[SourceInfo] = []
        seen_sources: set = set()

        for doc, distance in search_results:
            source_name = doc.metadata.get("source", "Unknown")
            page_num = doc.metadata.get("page", None)
            similarity = 1.0 / (1.0 + distance)

            context_parts.append(
                f"--- From: {source_name} (Page {page_num}) "
                f"[Relevance: {similarity:.0%}] ---\n"
                f"{doc.page_content}\n"
            )

            source_key = f"{source_name}_p{page_num}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append(
                    SourceInfo(
                        document=source_name,
                        page=page_num,
                        chunk_preview=doc.page_content[:150] + "...",
                        confidence_score=round(similarity, 3),
                    )
                )

        context_str = "\n".join(context_parts)
        history_str = self._format_chat_history(chat_history)

        prompt = RAG_PROMPT_TEMPLATE.format(
            context=context_str,
            chat_history=history_str,
            question=user_message,
        )

        logger.debug(
            f"Built RAG prompt with {len(search_results)} chunks, "
            f"{len(sources)} unique sources."
        )

        return prompt, sources

    def _build_direct_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
    ) -> str:
        """Build a direct LLM prompt (no document context)."""
        history_str = self._format_chat_history(chat_history)

        prompt = DIRECT_LLM_PROMPT_TEMPLATE.format(
            chat_history=history_str,
            question=user_message,
        )

        logger.debug("Built DIRECT prompt (no relevant documents).")
        return prompt

    def _build_no_context_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
    ) -> str:
        """Build a no-context prompt (vector store is empty)."""
        history_str = self._format_chat_history(chat_history)

        prompt = NO_CONTEXT_PROMPT_TEMPLATE.format(
            chat_history=history_str,
            question=user_message,
        )

        logger.debug("Built NO-CONTEXT prompt (empty vector store).")
        return prompt

    def _format_chat_history(self, chat_history: List[dict]) -> str:
        """Format chat history into a readable string for the LLM."""
        if not chat_history:
            return "No previous conversation."

        formatted_parts: List[str] = []
        for msg in chat_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            formatted_parts.append(f"{role}: {content}")

        return "\n".join(formatted_parts)

    def get_system_prompt(self) -> str:
        """Get the system prompt for the LLM."""
        return SYSTEM_PROMPT


# ============================================
# SINGLETON INSTANCE
# ============================================
rag_engine = RAGEngine()

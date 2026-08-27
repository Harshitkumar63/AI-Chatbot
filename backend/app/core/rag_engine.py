"""
RAG Engine & Prompt Builder for Eduzyra — 3-Way Hybrid AI Assistant.

=== 3-WAY HYBRID ENGINE ===
Coordinates the AIRouter, CourseService, and VectorStore to construct
grounded, hallucination-resistant prompts with precise citations:

1. COURSE_DATA: Live database facts formatted into prompt + Course Catalog citation
2. RAG: FAISS document chunks formatted into prompt + Document/Page citations
3. DIRECT: Pure educational LLM prompt with general knowledge attribution
"""

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.router import ai_router
from app.db.session import async_session_factory
from app.models.enums import AnswerMode
from app.models.schemas import SourceInfo
from app.services.course_service import course_service
from app.services.vector_store import vector_store_service
from app.utils.logger import get_logger
from app.utils.prompts import (
    COURSE_DATA_PROMPT_TEMPLATE,
    DIRECT_LLM_PROMPT_TEMPLATE,
    NO_CONTEXT_PROMPT_TEMPLATE,
    RAG_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class RAGEngine:
    """
    Orchestrates prompt construction for 3-way hybrid AI modes.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_best_similarity_score(self, search_results: list) -> float:
        """Calculate highest similarity score from search results."""
        if not search_results:
            return 0.0
        distances = [score for _, score in search_results]
        min_distance = min(distances)
        return 1.0 / (1.0 + min_distance)

    async def build_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
        session: Optional[AsyncSession] = None,
    ) -> Tuple[str, List[SourceInfo], AnswerMode]:
        """
        Build the complete prompt and citations for the LLM using 3-way hybrid routing.

        Parameters
        ----------
        user_message : str
            Current user query
        chat_history : List[dict]
            Recent conversation history
        session : Optional[AsyncSession]
            Active database session

        Returns
        -------
        Tuple[str, List[SourceInfo], AnswerMode]
            - Complete formatted prompt for LLM
            - List of SourceInfo citations
            - Selected AnswerMode
        """
        # Step 1: Route query via AIRouter
        if session is not None:
            mode, metadata = await ai_router.route_query(
                user_message=user_message,
                chat_history=chat_history,
                session=session,
            )
        else:
            async with async_session_factory() as temp_session:
                mode, metadata = await ai_router.route_query(
                    user_message=user_message,
                    chat_history=chat_history,
                    session=temp_session,
                )

        history_str = self._format_chat_history(chat_history)

        # Step 2: Handle COURSE_DATA Mode
        if mode == AnswerMode.COURSE_DATA:
            courses = metadata.get("matched_courses", [])
            if not courses and session:
                # If router didn't pre-populate courses, search now
                courses = await course_service.search_courses_by_query(
                    session=session,
                    query_text=user_message,
                    limit=5,
                )

            course_context = course_service.format_courses_for_context(courses)
            prompt = COURSE_DATA_PROMPT_TEMPLATE.format(
                course_context=course_context,
                chat_history=history_str,
                question=user_message,
            )

            # Build source citation for course catalog
            course_titles = ", ".join([c.title for c in courses[:3]]) if courses else "Eduzyra Course Catalog"
            sources = [
                SourceInfo(
                    document="Eduzyra Course Catalog",
                    page=None,
                    chunk_preview=f"Authoritative course database data for: {course_titles}",
                    confidence_score=1.0,
                    source_type="course_catalog",
                )
            ]
            logger.info(f"Built COURSE_DATA prompt with {len(courses)} courses.")
            return prompt, sources, AnswerMode.COURSE_DATA

        # Step 3: Handle RAG Mode
        if mode == AnswerMode.RAG:
            search_results = metadata.get("vector_search_results", [])
            if not search_results and vector_store_service.is_ready:
                search_results = await vector_store_service.search(user_message)

            if search_results:
                prompt, sources = self._build_rag_prompt(
                    user_message=user_message,
                    chat_history=chat_history,
                    search_results=search_results,
                )
                logger.info(f"Built RAG prompt with {len(search_results)} chunks.")
                return prompt, sources, AnswerMode.RAG
            else:
                # No document chunks available for an org/doc question
                prompt = RAG_PROMPT_TEMPLATE.format(
                    context="NO RELEVANT DOCUMENTS FOUND IN KNOWLEDGE BASE FOR THIS QUERY.",
                    chat_history=history_str,
                    question=user_message,
                )
                logger.info("Built RAG safety prompt (no documents found for policy query).")
                return prompt, [], AnswerMode.RAG

        # Step 4: Handle DIRECT LLM Mode
        prompt = DIRECT_LLM_PROMPT_TEMPLATE.format(
            chat_history=history_str,
            question=user_message,
        )
        logger.info("Built DIRECT LLM prompt.")
        return prompt, [], AnswerMode.DIRECT

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
            source_name = doc.metadata.get("source", "Knowledge Base Document")
            page_num = doc.metadata.get("page", None)
            section = doc.metadata.get("section", None)
            document_id = doc.metadata.get("document_id", None)
            similarity = 1.0 / (1.0 + distance)

            section_str = f" | Section: {section}" if section else ""
            page_str = f"Page {page_num}" if page_num else "Document"
            context_parts.append(
                f"--- From: {source_name} ({page_str}{section_str}) "
                f"[Relevance: {similarity:.0%}] ---\n"
                f"{doc.page_content}\n"
            )

            source_key = f"{source_name}_p{page_num}_s{section}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append(
                    SourceInfo(
                        document=source_name,
                        page=page_num,
                        section=section,
                        document_id=document_id,
                        chunk_preview=doc.page_content[:150] + "...",
                        confidence_score=round(similarity, 3),
                        source_type="document",
                    )
                )

        context_str = "\n".join(context_parts)
        history_str = self._format_chat_history(chat_history)

        prompt = RAG_PROMPT_TEMPLATE.format(
            context=context_str,
            chat_history=history_str,
            question=user_message,
        )

        return prompt, sources

    def _build_direct_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
    ) -> str:
        """Build a direct LLM prompt (no document context)."""
        history_str = self._format_chat_history(chat_history)
        return DIRECT_LLM_PROMPT_TEMPLATE.format(
            chat_history=history_str,
            question=user_message,
        )

    def _build_no_context_prompt(
        self,
        user_message: str,
        chat_history: List[dict],
    ) -> str:
        """Build a no-context prompt."""
        history_str = self._format_chat_history(chat_history)
        return NO_CONTEXT_PROMPT_TEMPLATE.format(
            chat_history=history_str,
            question=user_message,
        )

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

"""
Intelligent Hybrid AI Router for Eduzyra.

=== 3-WAY HYBRID ROUTING ARCHITECTURE ===
This router analyzes the user's query and conversation context to route to:

            ┌─────────────────┐
            │  USER QUESTION  │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │    AI ROUTER    │
            └────────┬────────┘
                     │
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
COURSE DATA         RAG         GENERAL LLM
(Live Database)  (FAISS + Docs)  (Pure LLM)
     │               │               │
     └───────────────┼───────────────┘
                     ▼
               FINAL ANSWER

Priority Rules:
1. Course Data has priority for live structured course facts (price, instructor, duration, syllabus).
2. RAG has priority for organization/document-specific questions (policies, uploaded PDFs).
3. General LLM answers general educational/technical questions (what is recursion, binary search code).
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AnswerMode
from app.services.course_service import course_service
from app.services.vector_store import vector_store_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Keywords & regex patterns indicating course catalog intent
COURSE_INTENT_PATTERNS = [
    # Course discovery / listing
    r"\b(which|what|show|list|any|all)\s+(courses|course|programs|classes|curriculum)\b",
    r"\b(courses\s+(available|offered|we\s+have|are\s+there))\b",
    r"\b(what\s+do\s+you\s+teach)\b",
    r"\b(catalog|catalogues?|offerings)\b",
    # Pricing / Cost
    r"\b(price|fee|fees|cost|charge|charges|how\s+much|discount|offer|pricing)\b",
    # Instructor / Faculty
    r"\b(who\s+teaches|who\s+is\s+the\s+teacher|instructor|faculty|trainer|professor|mentor)\b",
    # Duration & Lessons
    r"\b(how\s+long|duration|weeks|hours|how\s+many\s+lessons|lessons\s+count|modules)\b",
    # Syllabus & Learning Outcomes
    r"\b(syllabus|curriculum|what\s+will\s+i\s+learn|topics\s+covered|course\s+content)\b",
    # Rating & Enrollment
    r"\b(rating|reviews?|how\s+many\s+students|enrolled|enrollment)\b",
    # Comparison & Recommendations
    r"\b(compare|versus|vs\.?|which\s+(one\s+)?is\s+better|which\s+course\s+should\s+i\s+take)\b",
    r"\b(recommend\s+(a\s+)?course|suggest\s+(a\s+)?course|suitable\s+for\s+(a\s+)?beginner)\b",
    r"\b(i\s+want\s+to\s+learn\s+(python|machine\s+learning|ai|web|dsa|cloud|cyber|data))\b",
    # Course Details / Information
    r"\b(details?\s+(of|about)\s+(the\s+)?[a-z0-9\s-]+course)\b",
    r"\b(tell\s+me\s+about\s+(the\s+)?[a-z0-9\s-]+course)\b",
    r"\b(about\s+the\s+[a-z0-9\s-]+course)\b",
    r"\b(information\s+about\s+(the\s+)?[a-z0-9\s-]+course)\b",
    # Platform / Website / Project Discovery
    r"\b(about\s+(eduzyra|althexus|this\s+platform|this\s+website|this\s+project))\b",
    r"\b(what\s+is\s+(eduzyra|althexus|this\s+platform|this\s+website|this\s+project))\b",
    r"\b(tell\s+me\s+about\s+(eduzyra|althexus|this\s+platform|this\s+website|this\s+project))\b",
    r"\b(details?\s+(of|about)\s+(the\s+)?(project|platform|website|learning\s+paths?))\b",
    r"\b(cost\s+of\s+courses?|course\s+prices?|course\s+fees?|how\s+much\s+do\s+courses\s+cost)\b",
    # Specific course codes or keywords
    r"\b(edu-104|py-dev|ml-found|fs-web|dsa-pro|ai-gen|cloud-devops|data-analytics|cyber-sec)\b",
]

# Keywords indicating institutional / organization / document / policy queries
ORG_POLICY_PATTERNS = [
    r"\b(refund\s+policy|return\s+policy|cancellation\s+policy)\b",
    r"\b(scholarship|financial\s+aid|discount\s+policy)\b",
    r"\b(admission\s+process|admission\s+criteria|eligibility\s+criteria)\b",
    r"\b(certificate|certification\s+policy|grading\s+system|passing\s+marks)\b",
    r"\b(in\s+the\s+document|according\s+to\s+(the|our)\s+(pdf|notes?|doc|material|handbook))\b",
    r"\b(terms\s+and\s+conditions|privacy\s+policy|contact\s+support|eduzyra\s+policy)\b",
]

# Keywords indicating pronoun follow-ups that require context resolution
PRONOUN_FOLLOW_UPS = [
    r"\b(who\s+teaches\s+(it|this|that))\b",
    r"\b(what\s+is\s+(its|the)\s+(price|cost|fee|duration|rating|syllabus))\b",
    r"\b(how\s+long\s+is\s+(it|this|that))\b",
    r"\b(how\s+many\s+lessons\s+in\s+(it|this|that))\b",
    r"\b(what\s+will\s+i\s+learn\s+in\s+(it|this|that))\b",
    r"\b(is\s+(it|this)\s+for\s+beginners?)\b",
    r"\b(how\s+much\s+(is\s+it|does\s+it\s+cost))\b",
]


class AIRouter:
    """
    Intelligent router that determines the appropriate information source
    for a user's prompt: COURSE_DATA, RAG, or DIRECT LLM.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def route_query(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
        session: AsyncSession,
    ) -> Tuple[AnswerMode, Dict[str, Any]]:
        """
        Analyze intent and return the selected AnswerMode along with routing metadata.

        Parameters
        ----------
        user_message : str
            Current user query
        chat_history : List[Dict[str, str]]
            Recent conversation history
        session : AsyncSession
            Database session for course checks

        Returns
        -------
        Tuple[AnswerMode, Dict[str, Any]]
            Selected AnswerMode and metadata (e.g. matched courses, vector results, scores)
        """
        clean_text = user_message.lower().strip()
        metadata: Dict[str, Any] = {
            "query": user_message,
            "resolved_entity": None,
            "matched_courses": [],
            "vector_search_results": [],
            "best_similarity": 0.0,
            "reason": "",
        }

        # Step 1: Check multi-turn context for pronoun follow-up
        recent_course_entity = self._extract_course_from_history(chat_history)
        is_pronoun_followup = any(re.search(p, clean_text) for p in PRONOUN_FOLLOW_UPS)

        if is_pronoun_followup and recent_course_entity:
            logger.info(f"Router: Pronoun follow-up detected for course '{recent_course_entity}'.")
            course = await course_service.get_course_by_id_or_code(session, recent_course_entity)
            if course:
                metadata["resolved_entity"] = course.title
                metadata["matched_courses"] = [course]
                metadata["reason"] = f"Multi-turn pronoun follow-up on '{course.title}'"
                return AnswerMode.COURSE_DATA, metadata

        # Step 2: Identify Organizational / Document / Policy Intent
        is_org_policy = any(re.search(p, clean_text) for p in ORG_POLICY_PATTERNS)

        # Step 3: Check Course Intent Patterns (only if NOT an organizational policy question)
        is_course_intent = any(re.search(p, clean_text) for p in COURSE_INTENT_PATTERNS) and not is_org_policy

        # Check for explicit course code, full title, or distinctive multi-word course phrases
        all_courses = await course_service.get_all_courses(session, is_available=True)
        has_course_code = any(re.search(rf"\b{re.escape(c.code.lower())}\b", clean_text) for c in all_courses)
        has_full_title = any(c.title.lower() in clean_text for c in all_courses)

        course_name_phrases = [
            "react for products",
            "react for product",
            "edu-104",
            "edu 104",
            "python development",
            "python course",
            "machine learning foundations",
            "machine learning course",
            "full-stack web",
            "web development",
            "web dev",
            "data structures",
            "generative ai",
            "cloud computing",
            "devops",
            "data analytics",
            "cybersecurity essentials",
            "cyber security",
            "ethical hacking",
            "learning paths",
        ]
        has_course_phrase = any(phrase in clean_text for phrase in course_name_phrases) and not is_org_policy

        is_explicit_course_mention = has_course_code or has_full_title or has_course_phrase

        # If it's a pure general definition question (e.g. "what is python?"), ensure it's not hijacked by course data
        is_pure_concept_question = bool(re.match(r"^what\s+is\s+(python|machine\s+learning|ai|html|css|javascript|recursion)\??$", clean_text))

        if (is_course_intent or is_explicit_course_mention) and not is_pure_concept_question and not is_org_policy:
            logger.info("Router: Course-related intent identified.")

            # Search database for relevant courses
            matched_courses = await course_service.search_courses_by_query(
                session=session,
                query_text=user_message,
                limit=5,
            )

            # If user asks about comparison
            if "compare" in clean_text or "vs" in clean_text:
                comp_data = await course_service.compare_courses_by_query(session, user_message)
                if comp_data.courses:
                    codes = [c.code for c in comp_data.courses]
                    matched = [c for c in all_courses if c.code in codes]
                    matched_courses = matched or matched_courses

            metadata["matched_courses"] = matched_courses
            metadata["reason"] = "Course catalog query or course details requested"
            return AnswerMode.COURSE_DATA, metadata

        # Step 4: Perform Vector Store Search (if indexed docs exist)
        search_results = []
        best_similarity = 0.0

        if vector_store_service.is_ready and vector_store_service.document_count > 0:
            search_results = await vector_store_service.search(
                query=user_message,
                top_k=self._settings.RETRIEVAL_TOP_K,
            )
            if search_results:
                min_dist = min(score for _, score in search_results)
                best_similarity = 1.0 / (1.0 + min_dist)

        metadata["vector_search_results"] = search_results
        metadata["best_similarity"] = best_similarity

        # Step 5: Evaluate RAG vs Direct LLM
        threshold = self._settings.RAG_SIMILARITY_THRESHOLD

        if is_org_policy:
            # If asking about policies/handbook, RAG is required
            if best_similarity >= threshold and search_results:
                logger.info(f"Router: Org policy query matched documents with score {best_similarity:.3f}.")
                metadata["reason"] = f"Organization/policy query grounded in documents ({best_similarity:.1%})"
                return AnswerMode.RAG, metadata
            else:
                logger.info("Router: Org policy query with no matching documents in knowledge base.")
                metadata["reason"] = "Organization query but no matching policy doc found"
                # Route to RAG with empty/low results so RAG prompt explicitly handles the policy safety message
                return AnswerMode.RAG, metadata

        if best_similarity >= threshold and search_results:
            logger.info(f"Router: High vector similarity {best_similarity:.3f} >= {threshold:.3f} -> RAG Mode.")
            metadata["reason"] = f"Relevant document chunks found ({best_similarity:.1%})"
            return AnswerMode.RAG, metadata

        # Step 6: Default to General LLM for educational / general conceptual questions
        logger.info("Router: Direct General LLM Mode selected.")
        metadata["reason"] = "General educational or conceptual question"
        return AnswerMode.DIRECT, metadata

    def _extract_course_from_history(self, chat_history: List[Dict[str, str]]) -> Optional[str]:
        """
        Scan recent messages in chat history to identify the last referenced course title or code.
        """
        if not chat_history:
            return None

        # Look in the last 4 messages (reverse order)
        for msg in reversed(chat_history[-4:]):
            content = msg.get("content", "")
            # Check for known course codes
            codes = ["PY-DEV", "ML-FOUND", "FS-WEB", "DSA-PRO", "AI-GEN", "CLOUD-DEVOPS", "DATA-ANALYTICS", "CYBER-SEC"]
            for code in codes:
                if code.lower() in content.lower():
                    return code

            # Check for titles
            titles = [
                "Python Development",
                "Machine Learning",
                "Web Development",
                "Data Structures",
                "Generative AI",
                "Cloud Computing",
                "Data Analytics",
                "Cybersecurity",
            ]
            for title in titles:
                if title.lower() in content.lower():
                    return title

        return None


# ============================================
# SINGLETON INSTANCE
# ============================================
ai_router = AIRouter()

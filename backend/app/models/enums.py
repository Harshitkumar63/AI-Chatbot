"""
Enumerations for EduBot.

=== WHAT ARE ENUMS? ===
An enum (enumeration) is a set of named constants.
Instead of using raw strings like "human", "ai", "system" throughout the code,
we define them as an enum. This prevents typos and gives IDE autocomplete.

=== EXAMPLE ===
Without enums (error-prone):
    message.role = "humam"  # Typo! No error raised, but breaks logic.

With enums (safe):
    message.role = MessageRole.HUMAN  # Autocomplete! Typo = immediate error.

=== WHY str AND Enum? ===
By inheriting from both `str` and `Enum`, our enum values work as strings:
    MessageRole.HUMAN == "human"  # True
    json.dumps(MessageRole.HUMAN)  # '"human"' — serializes cleanly
"""

from enum import Enum


class MessageRole(str, Enum):
    """
    Roles for chat messages.

    In every conversation, messages come from one of three sources:
    - HUMAN: The user who typed the message
    - AI: The chatbot's response
    - SYSTEM: System-generated messages (e.g., "PDF uploaded successfully")
    """

    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


class DocumentStatus(str, Enum):
    """
    Processing status for uploaded documents.

    When a user uploads a PDF, it goes through these stages:
    1. PENDING: File received, not yet processed
    2. PROCESSING: Currently extracting text, chunking, embedding
    3. COMPLETED: Successfully indexed in FAISS, ready for queries
    4. FAILED: Processing failed (corrupt PDF, etc.)
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnswerMode(str, Enum):
    """
    How the chatbot generated its answer.

    This enables intelligent routing:
    - RAG: Answer came from retrieved documents (knowledge base)
    - DIRECT: Answer came from the LLM's general knowledge
    - HYBRID: Answer combined both sources

    The frontend uses this to show appropriate source attribution:
    - RAG → "📄 Source: intro_ml.pdf, Page 3"
    - DIRECT → "💡 Answered from general knowledge"
    """

    RAG = "rag"
    DIRECT = "direct"
    HYBRID = "hybrid"


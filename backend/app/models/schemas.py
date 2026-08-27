"""
Pydantic Schemas for EduBot API.

=== WHAT ARE PYDANTIC SCHEMAS? ===
Pydantic schemas define the SHAPE of data that flows through the API.
They are like "contracts" that specify:
- What data the API expects (request)
- What data the API returns (response)

=== WHY DO WE NEED BOTH SQLAlchemy MODELS AND PYDANTIC SCHEMAS? ===
They serve different purposes:

SQLAlchemy models (database.py):
  → Define how data is STORED in the database
  → Used by the ORM to create tables and query data

Pydantic schemas (this file):
  → Define how data is TRANSFERRED over the API
  → Used by FastAPI to validate requests and format responses

Example:
  Database model has: id, conversation_id, role, content, sources, created_at
  API response might only show: role, content, sources, created_at
  (We hide internal IDs from the user — they don't need to see conversation_id)

=== NAMING CONVENTION ===
  - *Request: Data the client SENDS to us (e.g., ChatRequest)
  - *Response: Data we SEND back to the client (e.g., ChatResponse)
  - *Base: Shared fields between request and response
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================
# CHAT SCHEMAS
# ============================================

class ChatRequest(BaseModel):
    """
    Data the client sends when sending a chat message.

    Example JSON:
    {
        "message": "What is machine learning?",
        "conversation_id": "abc-123"  // null for new conversation
    }
    """

    # The user's message text
    message: str = Field(
        ...,  # ... means "required"
        min_length=1,
        max_length=4096,
        description="The user's message text",
        examples=["What is machine learning?"],
    )

    # Optional: continue an existing conversation
    # If null/missing, a new conversation is created
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID of an existing conversation to continue. Omit for new conversation.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )


class SourceInfo(BaseModel):
    """
    Information about a source document cited in a response.

    This is how we show the user WHERE the answer came from.
    """

    document: str = Field(
        ...,
        description="The document filename",
        examples=["intro_to_ml.pdf"],
    )

    page: Optional[int] = Field(
        default=None,
        description="Page number in the document (if available)",
    )

    chunk_preview: Optional[str] = Field(
        default=None,
        description="A short preview of the relevant text chunk",
    )

    confidence_score: Optional[float] = Field(
        default=None,
        description="Similarity score from FAISS (0.0 - 1.0)",
    )

    section: Optional[str] = Field(
        default=None,
        description="Section or heading name in the document",
    )

    document_id: Optional[int] = Field(
        default=None,
        description="Database document ID",
    )

    source_type: Optional[str] = Field(
        default="document",
        description="Source type: document, course_catalog, general_knowledge",
    )


class ChatResponse(BaseModel):
    """
    Data returned after a chat message is fully processed.

    This is used for non-streaming responses.
    For streaming, we use Server-Sent Events (SSE) instead.
    """

    conversation_id: str = Field(
        ...,
        description="The conversation ID (new or existing)",
    )

    message: str = Field(
        ...,
        description="The AI's complete response",
    )

    sources: List[SourceInfo] = Field(
        default_factory=list,
        description="List of source documents cited",
    )

    answer_mode: Optional[str] = Field(
        default=None,
        description="How the answer was generated: rag, direct, or hybrid",
    )


class StreamEvent(BaseModel):
    """
    A single event in the SSE stream.

    During streaming, we send a series of these events:
    1. {"event": "start", "conversation_id": "abc-123"}
    2. {"event": "mode", "answer_mode": "rag" | "direct"}
    3. {"event": "token", "token": "Machine"}
    4. {"event": "token", "token": " learning"}
    5. {"event": "token", "token": " is"}
    6. {"event": "sources", "sources": [...], "answer_mode": "rag"}
    7. {"event": "end"}
    """

    event: str = Field(
        ...,
        description="Event type: start, token, sources, error, end",
    )

    token: Optional[str] = Field(
        default=None,
        description="A single token (word/piece) of the response",
    )

    conversation_id: Optional[str] = Field(
        default=None,
        description="Sent with the 'start' event",
    )

    sources: Optional[List[SourceInfo]] = Field(
        default=None,
        description="Sent with the 'sources' event",
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message (sent with 'error' event)",
    )

    answer_mode: Optional[str] = Field(
        default=None,
        description="How the answer was generated: rag, direct, or hybrid",
    )


# ============================================
# MESSAGE SCHEMAS
# ============================================

class MessageResponse(BaseModel):
    """
    A single message in a conversation.

    Used when returning chat history.
    """

    id: int = Field(..., description="Message ID")
    role: str = Field(..., description="Who sent this: human, ai, or system")
    content: str = Field(..., description="The message text")
    sources: Optional[List[SourceInfo]] = Field(
        default=None,
        description="Source citations (for AI messages)",
    )
    answer_mode: Optional[str] = Field(
        default=None,
        description="Answer mode: course_data, rag, direct, hybrid",
    )
    created_at: datetime = Field(..., description="When the message was sent")

    model_config = {"from_attributes": True}


# ============================================
# CONVERSATION SCHEMAS
# ============================================

class ConversationResponse(BaseModel):
    """
    Summary of a conversation (for the conversation list).
    """

    id: str = Field(..., description="Conversation UUID")
    title: Optional[str] = Field(None, description="Conversation title")
    created_at: datetime = Field(..., description="When the conversation started")
    updated_at: datetime = Field(..., description="When the last message was sent")
    message_count: int = Field(0, description="Total messages in this conversation")

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    """
    Full conversation with all messages (for loading a specific chat).
    """

    id: str = Field(..., description="Conversation UUID")
    title: Optional[str] = Field(None, description="Conversation title")
    messages: List[MessageResponse] = Field(
        default_factory=list,
        description="All messages in chronological order",
    )
    created_at: datetime = Field(..., description="When the conversation started")
    updated_at: datetime = Field(..., description="When the last message was sent")

    model_config = {"from_attributes": True}


# ============================================
# DOCUMENT SCHEMAS
# ============================================

class DocumentUploadResponse(BaseModel):
    """
    Response after uploading a document.
    """

    id: int = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    chunk_count: int = Field(0, description="Number of chunks created")
    file_size: int = Field(0, description="File size in bytes")
    message: str = Field(..., description="Status message")

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """
    Document information (for listing all documents).
    """

    id: int = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    chunk_count: int = Field(0, description="Number of chunks")
    file_size: int = Field(0, description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")
    error_message: Optional[str] = Field(None, description="Error details if failed")

    model_config = {"from_attributes": True}


# ============================================
# HEALTH CHECK SCHEMA
# ============================================

class HealthResponse(BaseModel):
    """
    Health check response — used by monitoring tools to verify the app is running.
    """

    status: str = Field("healthy", description="Application status")
    app_name: str = Field(..., description="Application name")
    version: str = Field("1.0.0", description="Application version")
    vector_store_ready: bool = Field(
        False,
        description="Whether the FAISS vector store is loaded",
    )
    document_count: int = Field(
        0,
        description="Number of indexed documents",
    )


# ============================================
# COURSE SCHEMAS (SINGLE SOURCE OF TRUTH)
# ============================================

class CourseBase(BaseModel):
    """Base fields for a course."""
    code: str = Field(..., description="Unique course code (e.g. PY-DEV)")
    title: str = Field(..., description="Full course title")
    description: str = Field(..., description="Detailed description")
    category: str = Field(..., description="Category (Programming, AI, Web Dev, etc.)")
    level: str = Field(..., description="Difficulty level (Beginner, Intermediate, Advanced)")
    instructor: str = Field(..., description="Instructor name")
    instructor_bio: Optional[str] = Field(None, description="Instructor biography")
    duration: str = Field(..., description="Duration e.g. 8 weeks (40 hours)")
    lessons_count: int = Field(0, description="Total lessons/modules count")
    rating: float = Field(5.0, description="Average rating (0.0-5.0)")
    reviews_count: int = Field(0, description="Total number of reviews")
    enrolled_students: int = Field(0, description="Number of enrolled students")
    current_price: float = Field(..., description="Current active price")
    original_price: float = Field(..., description="Original price")
    currency: str = Field("₹", description="Currency symbol")
    discount_percent: int = Field(0, description="Discount percentage")
    syllabus: List[str] = Field(default_factory=list, description="List of syllabus topics/modules")
    learning_outcomes: List[str] = Field(default_factory=list, description="List of learning outcomes")
    prerequisites: List[str] = Field(default_factory=list, description="List of prerequisites")
    is_available: bool = Field(True, description="Whether course is open for enrollment")


class CourseResponse(BaseModel):
    """Summary response for course lists."""
    id: str = Field(..., description="Course UUID")
    code: str = Field(..., description="Course code")
    title: str = Field(..., description="Course title")
    description: str = Field(..., description="Description preview")
    category: str = Field(..., description="Category")
    level: str = Field(..., description="Level")
    instructor: str = Field(..., description="Instructor name")
    duration: str = Field(..., description="Duration")
    lessons_count: int = Field(..., description="Lessons count")
    rating: float = Field(..., description="Rating")
    enrolled_students: int = Field(..., description="Enrolled students")
    current_price: float = Field(..., description="Current price")
    original_price: float = Field(..., description="Original price")
    currency: str = Field("₹", description="Currency symbol")
    discount_percent: int = Field(..., description="Discount percent")
    is_available: bool = Field(..., description="Availability status")

    model_config = {"from_attributes": True}


class CourseDetailResponse(CourseResponse):
    """Full course details including syllabus, prerequisites, and outcomes."""
    instructor_bio: Optional[str] = None
    reviews_count: int = 0
    syllabus: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    model_config = {"from_attributes": True}


class CourseListResponse(BaseModel):
    """Response containing a list of courses and metadata."""
    total: int = Field(..., description="Total courses matching criteria")
    courses: List[CourseResponse] = Field(default_factory=list, description="List of courses")


class CourseComparisonItem(BaseModel):
    """Comparison item for comparing two or more courses."""
    code: str
    title: str
    category: str
    level: str
    instructor: str
    duration: str
    lessons_count: int
    rating: float
    current_price: float
    original_price: float
    currency: str = "₹"
    discount_percent: int
    syllabus_preview: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)


class CourseComparisonResponse(BaseModel):
    """Response containing course comparison data."""
    courses: List[CourseComparisonItem]
    comparison_notes: Optional[str] = None


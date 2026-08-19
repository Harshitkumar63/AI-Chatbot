"""
SQLAlchemy Database Models for EduBot.

=== WHAT IS AN ORM (Object-Relational Mapping)? ===
An ORM lets you interact with a database using Python classes instead of SQL.

Without ORM (raw SQL):
    cursor.execute("INSERT INTO messages (content, role) VALUES (?, ?)", ("Hello", "human"))

With ORM (SQLAlchemy):
    message = Message(content="Hello", role=MessageRole.HUMAN)
    session.add(message)

The ORM translates your Python objects into SQL automatically.

=== WHAT IS SQLAlchemy? ===
SQLAlchemy is the most popular Python ORM. It supports:
- SQLite (our development DB)
- PostgreSQL (production)
- MySQL, Oracle, etc.

The KEY benefit: your code stays the SAME regardless of which database you use.
Switching from SQLite to PostgreSQL = changing ONE config line.

=== HOW THESE MODELS MAP TO DATABASE TABLES ===

Conversation table:
    ┌────────────┬──────────┬──────────────────┬──────────────────┐
    │ id (UUID)  │ title    │ created_at       │ updated_at       │
    ├────────────┼──────────┼──────────────────┼──────────────────┤
    │ abc-123    │ "ML Q&A" │ 2024-01-15 10:00 │ 2024-01-15 10:30 │
    └────────────┴──────────┴──────────────────┴──────────────────┘

Message table:
    ┌──────┬─────────────────┬─────────┬─────────────────┬──────────────────┐
    │ id   │ conversation_id │ role    │ content         │ created_at       │
    ├──────┼─────────────────┼─────────┼─────────────────┼──────────────────┤
    │ 1    │ abc-123         │ human   │ "What is ML?"   │ 2024-01-15 10:00 │
    │ 2    │ abc-123         │ ai      │ "ML is..."      │ 2024-01-15 10:01 │
    └──────┴─────────────────┴─────────┴─────────────────┴──────────────────┘

Document table:
    ┌──────┬──────────────┬──────────┬────────┬──────────┬──────────────────┐
    │ id   │ filename     │ status   │ chunks │ file_size│ created_at       │
    ├──────┼──────────────┼──────────┼────────┼──────────┼──────────────────┤
    │ 1    │ intro_ml.pdf │ completed│ 24     │ 1048576  │ 2024-01-15 09:00 │
    └──────┴──────────────┴──────────┴────────┴──────────┴──────────────────┘
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ============================================
# BASE CLASS
# ============================================
# All our models inherit from this base class.
# SQLAlchemy uses it to track all tables and create them.

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


def generate_uuid() -> str:
    """
    Generate a unique ID for database records.

    Why UUID instead of auto-increment integers?
    - UUIDs are globally unique (no collisions, even across servers)
    - They don't reveal how many records exist (security)
    - They work well with distributed systems

    Example: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    """
    return str(uuid.uuid4())


class Conversation(Base):
    """
    Represents a chat conversation (a "thread" of messages).

    One conversation contains many messages.
    Think of it like a WhatsApp chat — the conversation is the chat window,
    and messages are the individual bubbles inside.

    Relationship: Conversation (1) ──→ (Many) Messages
    """

    __tablename__ = "conversations"

    # Primary key — unique identifier for each conversation
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    # Optional title (auto-generated from the first message or user-defined)
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )

    # Timestamps — when was this conversation created/last updated?
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ---- Relationship ----
    # This creates a virtual connection to the Message table.
    # conversation.messages → returns all messages in this conversation
    # cascade="all, delete-orphan" → deleting a conversation deletes its messages
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title={self.title})>"


class Message(Base):
    """
    Represents a single message in a conversation.

    Each message has:
    - A role (who sent it: human, ai, or system)
    - Content (the actual text)
    - Optional sources (which documents were cited)
    - A link back to its parent conversation
    """

    __tablename__ = "messages"

    # Auto-incrementing integer ID
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Which conversation does this message belong to?
    # This is a "foreign key" — it references the conversations.id column
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who sent this message? (human, ai, or system)
    role: Mapped[str] = mapped_column(
        Enum("human", "ai", "system", name="message_role"),
        nullable=False,
    )

    # The actual message text
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Sources cited in this message (stored as JSON string)
    # Example: '[{"document": "intro_ml.pdf", "page": 3}]'
    sources: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # When was this message sent?
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # ---- Relationship ----
    # message.conversation → returns the parent Conversation object
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content={preview})>"


class Document(Base):
    """
    Represents an uploaded document (PDF).

    Tracks the document's lifecycle:
    1. User uploads a PDF → status = PENDING
    2. System processes it → status = PROCESSING
    3. Successfully indexed → status = COMPLETED (or FAILED)

    We store metadata here (filename, size, chunk count),
    but the actual embeddings are stored in FAISS.
    """

    __tablename__ = "documents"

    # Auto-incrementing integer ID
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Original filename (e.g., "intro_to_ml.pdf")
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Processing status (pending, processing, completed, failed)
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="document_status"),
        nullable=False,
        default="pending",
    )

    # How many chunks was this document split into?
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # File size in bytes
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Error message if processing failed
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # When was this document uploaded?
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"

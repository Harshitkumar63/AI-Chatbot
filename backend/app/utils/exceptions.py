"""
Custom Exception Classes for EduBot.

=== WHAT ARE CUSTOM EXCEPTIONS? ===
Python has built-in exceptions like ValueError, FileNotFoundError, etc.
But in a production app, we create our OWN exception classes because:

1. Specificity: "DocumentProcessingError" tells you EXACTLY what went wrong.
   A generic "Exception" tells you nothing.

2. Handling: We can catch specific exceptions and return appropriate HTTP codes:
   - DocumentNotFoundError → 404 Not Found
   - LLMServiceError → 503 Service Unavailable
   - DocumentProcessingError → 422 Unprocessable Entity

3. Information: Custom exceptions can carry extra data (document_id, model_name).

=== HOW PYTHON EXCEPTIONS WORK ===
Exceptions form a tree (inheritance hierarchy):

    BaseException
    └── Exception
        └── EduBotError (our base)
            ├── DocumentProcessingError
            ├── DocumentNotFoundError
            ├── LLMServiceError
            ├── VectorStoreError
            └── ChatServiceError

When you write `except EduBotError`, it catches ALL our custom exceptions.
When you write `except LLMServiceError`, it catches only LLM-related errors.

=== USAGE ===
    from app.utils.exceptions import LLMServiceError

    try:
        response = await llm.generate(prompt)
    except Exception as e:
        raise LLMServiceError(f"Groq API failed: {e}") from e
"""


class EduBotError(Exception):
    """
    Base exception for all EduBot errors.

    All custom exceptions inherit from this class.
    This allows catching ALL application errors with a single except clause:

        try:
            ...
        except EduBotError as e:
            logger.error(f"Application error: {e}")
    """

    def __init__(self, message: str = "An unexpected error occurred"):
        self.message = message
        super().__init__(self.message)


class DocumentProcessingError(EduBotError):
    """
    Raised when PDF processing fails.

    Examples:
    - PDF is corrupted and can't be read
    - PDF has no extractable text (it's a scanned image)
    - Chunking fails due to encoding issues

    HTTP Status: 422 Unprocessable Entity
    """

    def __init__(self, message: str = "Failed to process document", filename: str = ""):
        self.filename = filename
        super().__init__(f"{message}: {filename}" if filename else message)


class DocumentNotFoundError(EduBotError):
    """
    Raised when a requested document doesn't exist.

    HTTP Status: 404 Not Found
    """

    def __init__(self, document_id: str = ""):
        self.document_id = document_id
        message = f"Document not found: {document_id}" if document_id else "Document not found"
        super().__init__(message)


class LLMServiceError(EduBotError):
    """
    Raised when the LLM API (Groq) fails.

    Examples:
    - API key is invalid
    - Rate limit exceeded
    - Network timeout
    - Model not available

    HTTP Status: 503 Service Unavailable
    """

    def __init__(self, message: str = "LLM service is unavailable"):
        super().__init__(message)


class VectorStoreError(EduBotError):
    """
    Raised when FAISS operations fail.

    Examples:
    - Index file doesn't exist
    - Dimension mismatch when adding embeddings
    - Search fails on empty index

    HTTP Status: 500 Internal Server Error
    """

    def __init__(self, message: str = "Vector store operation failed"):
        super().__init__(message)


class ChatServiceError(EduBotError):
    """
    Raised when the chat orchestration fails.

    This is a higher-level error that wraps failures in
    the chat pipeline (memory, RAG, or LLM).

    HTTP Status: 500 Internal Server Error
    """

    def __init__(self, message: str = "Chat service error"):
        super().__init__(message)


class ConversationNotFoundError(EduBotError):
    """
    Raised when a conversation ID doesn't exist in the database.

    HTTP Status: 404 Not Found
    """

    def __init__(self, conversation_id: str = ""):
        self.conversation_id = conversation_id
        message = (
            f"Conversation not found: {conversation_id}"
            if conversation_id
            else "Conversation not found"
        )
        super().__init__(message)

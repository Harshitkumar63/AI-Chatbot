"""
Admin API Endpoints for EduBot Knowledge Base Management.

=== WHAT IS THIS? ===
These endpoints are for ADMINISTRATORS ONLY.
Students should never access these endpoints.

Admins use these to:
- Upload documents (PDF, DOCX, TXT) to build the knowledge base
- List all indexed documents
- Delete documents
- Rebuild the FAISS index
- Check indexing status

=== SECURITY ===
Protected with a simple API key (ADMIN_API_KEY in .env).
In production, replace with proper authentication (OAuth2, JWT).

=== HOW API KEY AUTH WORKS ===
The admin sends the API key in a header:
    X-Admin-Key: your-secret-key

The server checks this header against the configured key.
If it doesn't match → 403 Forbidden.
"""

from typing import List

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.document_processor import document_processor
from app.db.session import get_session
from app.models.schemas import DocumentResponse, DocumentUploadResponse
from app.services.vector_store import vector_store_service
from app.utils.exceptions import DocumentProcessingError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin - Knowledge Base"])


# ============================================
# AUTH DEPENDENCY
# ============================================

async def verify_admin_key(
    x_admin_key: str = Header(
        ...,
        description="Admin API key for authentication",
    ),
) -> str:
    """
    Verify the admin API key.

    This is a FastAPI dependency that runs BEFORE the endpoint.
    If the key is wrong, it raises a 403 error and the endpoint
    never executes.
    """
    settings = get_settings()
    if x_admin_key != settings.ADMIN_API_KEY:
        logger.warning("Invalid admin API key attempt.")
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key.",
        )
    return x_admin_key


# ============================================
# ENDPOINTS
# ============================================

@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload a document to knowledge base",
    description="Upload PDF, DOCX, or TXT files to index in the knowledge base. Admin only.",
    dependencies=[Depends(verify_admin_key)],
)
async def admin_upload_document(
    file: UploadFile = File(
        ...,
        description="Document file (PDF, DOCX, or TXT, max 10MB)",
    ),
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse:
    """
    Upload and process a document for the knowledge base.

    Supported formats: PDF, DOCX, TXT
    The document is automatically:
    1. Saved to disk
    2. Text extracted
    3. Split into chunks
    4. Embedded and indexed in FAISS
    """
    logger.info(f"Admin upload: {file.filename}")

    try:
        file_content = await file.read()

        document = await document_processor.process_upload(
            file_content=file_content,
            filename=file.filename or "unknown",
            session=session,
        )

        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            status=document.status,
            chunk_count=document.chunk_count,
            file_size=document.file_size,
            message=(
                f"Successfully processed '{document.filename}' "
                f"into {document.chunk_count} chunks."
            ),
        )

    except DocumentProcessingError as e:
        logger.error(f"Document processing failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the document.",
        )


@router.get(
    "/documents",
    response_model=List[DocumentResponse],
    summary="List all documents",
    description="Get all documents in the knowledge base with their processing status.",
    dependencies=[Depends(verify_admin_key)],
)
async def admin_list_documents(
    session: AsyncSession = Depends(get_session),
) -> List[DocumentResponse]:
    """List all documents in the knowledge base."""
    documents = await document_processor.get_all_documents(session)

    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            chunk_count=doc.chunk_count,
            file_size=doc.file_size,
            created_at=doc.created_at,
            error_message=doc.error_message,
        )
        for doc in documents
    ]


@router.delete(
    "/documents/{document_id}",
    summary="Delete a document",
    description="Delete a document from the knowledge base. Requires index rebuild.",
    dependencies=[Depends(verify_admin_key)],
)
async def admin_delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Delete a document from the knowledge base.

    Note: After deletion, call POST /admin/rebuild-index to
    update the FAISS index without the deleted document.
    """
    deleted = await document_processor.delete_document(document_id, session)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found.",
        )

    return {
        "status": "deleted",
        "document_id": document_id,
        "message": (
            "Document deleted. Run POST /api/admin/rebuild-index "
            "to update the search index."
        ),
    }


@router.post(
    "/rebuild-index",
    summary="Rebuild FAISS index",
    description="Rebuild the vector search index from all completed documents.",
    dependencies=[Depends(verify_admin_key)],
)
async def admin_rebuild_index(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Rebuild the FAISS index from scratch.

    Use this after:
    - Deleting documents
    - If the index becomes corrupted
    - To optimize the index
    """
    logger.info("Admin triggered index rebuild.")

    total_chunks = await document_processor.rebuild_index(session)

    return {
        "status": "completed",
        "total_chunks": total_chunks,
        "document_count": vector_store_service.document_count,
        "message": f"Index rebuilt with {total_chunks} chunks.",
    }


@router.get(
    "/status",
    summary="Knowledge base status",
    description="Get the current status of the knowledge base.",
    dependencies=[Depends(verify_admin_key)],
)
async def admin_kb_status(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get knowledge base statistics."""
    documents = await document_processor.get_all_documents(session)

    completed = sum(1 for d in documents if d.status == "completed")
    failed = sum(1 for d in documents if d.status == "failed")
    processing = sum(1 for d in documents if d.status == "processing")

    return {
        "vector_store_ready": vector_store_service.is_ready,
        "total_documents": len(documents),
        "completed_documents": completed,
        "failed_documents": failed,
        "processing_documents": processing,
        "total_chunks_indexed": vector_store_service.document_count,
    }

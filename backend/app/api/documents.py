"""
Document Info API Endpoint (Student-Facing, Read-Only).

Students can see what documents are in the knowledge base,
but they CANNOT upload, delete, or manage documents.
Document management is admin-only (see admin.py).
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.document_processor import document_processor
from app.db.session import get_session
from app.models.schemas import DocumentResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List available documents",
    description="Get a list of all documents in the knowledge base (read-only).",
)
async def list_documents(
    session: AsyncSession = Depends(get_session),
) -> List[DocumentResponse]:
    """
    List all documents in the knowledge base.

    This is a read-only endpoint available to all users.
    Students can see what documents are indexed but cannot
    upload, modify, or delete them.
    """
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

"""
Main API Router.

Combines all routers under the /api prefix:

Student-facing endpoints:
- POST /api/chat           → Send a chat message (streaming)
- GET  /api/documents      → List indexed documents (read-only)
- GET  /api/conversations   → List conversations
- GET  /api/conversations/{id} → Get conversation messages
- GET  /api/health         → Health check

Admin-only endpoints (require X-Admin-Key header):
- POST   /api/admin/documents/upload     → Upload PDF/DOCX/TXT
- GET    /api/admin/documents            → List all documents
- DELETE /api/admin/documents/{id}       → Delete a document
- POST   /api/admin/rebuild-index        → Rebuild FAISS index
- GET    /api/admin/status               → Knowledge base status
"""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.history import router as history_router

# Create the main API router with /api prefix
api_router = APIRouter(prefix="/api")

# Student-facing routes
api_router.include_router(chat_router)
api_router.include_router(documents_router)
api_router.include_router(history_router)
api_router.include_router(health_router)

# Admin-only routes
api_router.include_router(admin_router)

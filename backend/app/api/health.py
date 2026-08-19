"""
Health Check API Endpoint.

=== WHAT IS A HEALTH CHECK? ===
A health check is a simple endpoint that tells you:
"Is the application running and are its dependencies working?"

It's used by:
- Deployment platforms (Render, Railway) to know if your app is alive
- Monitoring tools to alert you if the app goes down
- Load balancers to route traffic only to healthy instances

=== WHY IS IT IMPORTANT? ===
Without it, your deployment platform might think a crashed app is
still running, or a starting app is ready before it actually is.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.services.vector_store import vector_store_service

# Create a router — this is a "sub-app" that handles health-related routes
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=dict,
    summary="Health Check",
    description="Check if the application is running and its dependencies are ready.",
)
async def health_check() -> dict:
    """
    Return application health status.

    Returns basic information about the application state:
    - Is the app running?
    - Is the vector store loaded?
    - How many documents are indexed?
    """
    settings = get_settings()

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "vector_store_ready": vector_store_service.is_ready,
        "document_count": vector_store_service.document_count,
    }

"""
FastAPI Application Entry Point for EduBot.

=== WHAT IS THIS FILE? ===
This is the MAIN file — the starting point of the entire backend.
When you run `uvicorn app.main:app`, Python loads THIS file.

=== WHAT HAPPENS AT STARTUP? ===
1. FastAPI app is created with metadata (title, description, version)
2. CORS middleware is added (allows the frontend to talk to the backend)
3. All API routes are registered
4. On startup:
   a. Database tables are created
   b. Embedding model is loaded (~80MB, first run downloads it)
   c. LLM client is initialized (Groq API connection)
   d. FAISS index is loaded (if it exists)

=== WHAT IS CORS? ===
CORS (Cross-Origin Resource Sharing) is a security feature.
Browsers block requests from one domain to another by default.

Without CORS:
  Frontend (localhost:5173) → Backend (localhost:8000)  ❌ BLOCKED

With CORS configured:
  Frontend (localhost:5173) → Backend (localhost:8000)  ✅ ALLOWED

We tell the backend: "Allow requests from these specific origins."

=== WHAT IS MIDDLEWARE? ===
Middleware is code that runs BEFORE every request and AFTER every response.
Think of it as a security guard at the building entrance:
- Checks every visitor (request) coming in
- Stamps every visitor going out (adds headers to responses)

Our CORS middleware adds special headers to every response that tell
the browser "yes, this frontend is allowed to talk to me."
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.db.init_db import init_database
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service
from app.services.vector_store import vector_store_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    === WHAT IS THIS? ===
    This function runs code when the app STARTS and when it STOPS.
    - Code before `yield` runs at STARTUP
    - Code after `yield` runs at SHUTDOWN

    === WHY asynccontextmanager? ===
    FastAPI's newer way of handling startup/shutdown events.
    It replaces the old @app.on_event("startup") decorator.
    Benefits: cleaner, supports both startup AND shutdown in one function.

    === STARTUP SEQUENCE ===
    The order matters! We initialize dependencies in the right order:
    1. Database → other components need it
    2. Embeddings → vector store needs it
    3. Vector Store → needs embedding model to load
    4. LLM → independent, can load last
    """
    logger.info("=" * 60)
    logger.info("🚀 EduBot is starting up...")
    logger.info("=" * 60)

    settings = get_settings()

    # Step 1: Initialize the database (create tables)
    await init_database()
    logger.info("✅ Database initialized")

    # Step 2: Load the embedding model
    await embedding_service.initialize()
    logger.info("✅ Embedding model loaded")

    # Step 3: Load the FAISS vector store (if index exists)
    await vector_store_service.initialize()
    logger.info("✅ Vector store initialized")

    # Step 4: Initialize the LLM client
    await llm_service.initialize()
    logger.info("✅ LLM service initialized")

    logger.info("=" * 60)
    logger.info(f"🤖 {settings.APP_NAME} is ready!")
    logger.info(f"📝 API docs: http://localhost:8000/docs")
    logger.info(f"🔗 Health: http://localhost:8000/api/health")
    logger.info("=" * 60)

    # ---- App is running ----
    yield
    # ---- App is shutting down ----

    logger.info("👋 EduBot is shutting down...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    === FACTORY PATTERN ===
    We use a "factory function" instead of creating the app at module level.
    Why?
    1. Testability: In tests, we can create apps with different configs
    2. Clarity: All app setup is in one place
    3. Flexibility: Easy to create multiple app instances if needed
    """
    settings = get_settings()

    # Create the FastAPI app with metadata
    # These settings appear in the auto-generated API docs at /docs
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "🤖 An intelligent educational chatbot powered by RAG "
            "(Retrieval-Augmented Generation). Upload PDFs and ask questions "
            "about their content."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ---- CORS Middleware ----
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,  # Which domains can access
        allow_credentials=True,                     # Allow cookies/auth headers
        allow_methods=["*"],                        # Allow all HTTP methods
        allow_headers=["*"],                        # Allow all request headers
    )

    # ---- Register API Routes ----
    application.include_router(api_router)

    # ---- Serve Frontend (Single Local Server) ----
    import os
    from fastapi.staticfiles import StaticFiles

    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    )
    if os.path.exists(frontend_dist):
        application.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )

    return application


# Create the application instance
# This is what uvicorn looks for: `uvicorn app.main:app`
app = create_app()

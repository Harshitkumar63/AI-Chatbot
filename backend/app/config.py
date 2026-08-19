"""
Configuration Management for EduBot.

=== WHAT IS THIS FILE? ===
This file is the "control panel" for the entire application.
Instead of hardcoding values like API keys, database URLs, or model names
throughout the codebase, we centralize ALL configuration here.

=== WHY? ===
1. Security: API keys are loaded from environment variables, never hardcoded.
2. Flexibility: Change behavior without touching code (just edit .env).
3. Validation: Pydantic validates all settings at startup — bad config = immediate error.
4. Documentation: Every setting is in one place with a description.

=== HOW IT WORKS ===
1. Pydantic's BaseSettings reads values from environment variables.
2. If a .env file exists, python-dotenv loads it automatically.
3. Default values are provided for non-sensitive settings.
4. The @lru_cache decorator ensures we only parse settings once (singleton pattern).

=== USAGE ===
    from app.config import get_settings
    settings = get_settings()
    print(settings.GROQ_API_KEY)
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================
# BASE DIRECTORY
# ============================================
# This resolves to: backend/
# We use this as the root for all relative paths (data, uploads, etc.)
BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic's BaseSettings automatically reads from:
    1. Environment variables (highest priority)
    2. .env file (loaded by python-dotenv)
    3. Default values defined here (lowest priority)

    This means: if you set GROQ_API_KEY in your terminal,
    it overrides the value in .env, which overrides the default.
    """

    # ---- Application Settings ----
    APP_NAME: str = "EduBot"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS origins — which frontend URLs can talk to this API
    # In development: React dev server at localhost:5173
    # In production: your actual domain
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ---- LLM Configuration ----
    # Groq API key — required, no default (forces you to set it)
    GROQ_API_KEY: str = ""

    # Which LLM model to use on Groq
    LLM_MODEL_NAME: str = "llama-3.1-8b-instant"

    # Max tokens per response (1 token ≈ 0.75 words)
    LLM_MAX_TOKENS: int = 1024

    # Temperature: 0.0 = focused/deterministic, 1.0 = creative/random
    LLM_TEMPERATURE: float = 0.7

    # ---- Embedding Model ----
    # Runs locally — no API key needed
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # ---- Vector Store ----
    VECTOR_STORE_PATH: str = "data/vector_store"

    # How many similar document chunks to retrieve per query
    RETRIEVAL_TOP_K: int = 4

    # ---- Intelligent Routing ----
    # Similarity threshold for RAG routing (0.0 - 1.0)
    # If the best retrieval score is BELOW this, skip RAG and use direct LLM
    # Lower = more permissive (use RAG even with weak matches)
    # Higher = more strict (only use RAG with strong matches)
    RAG_SIMILARITY_THRESHOLD: float = 0.35

    # ---- Database ----
    # SQLite for development, PostgreSQL URL for production
    DATABASE_URL: str = "sqlite:///data/chatbot.db"

    # ---- Document Processing ----
    MAX_UPLOAD_SIZE: int = 10_485_760  # 10 MB in bytes
    CHUNK_SIZE: int = 500  # Characters per chunk
    CHUNK_OVERLAP: int = 50  # Overlap between chunks
    UPLOAD_DIR: str = "data/uploads"

    # Supported file types for admin uploads
    SUPPORTED_FILE_TYPES: str = ".pdf,.docx,.txt"

    # ---- Admin ----
    # Simple API key for admin endpoints (set a strong value in production!)
    ADMIN_API_KEY: str = "edubot-admin-key-change-me"

    # ---- Memory ----
    # How many past messages to include as context for the LLM
    MEMORY_WINDOW_SIZE: int = 10

    # ---- Pydantic Settings Config ----
    # This tells Pydantic WHERE to find the .env file
    # and that environment variables are case-insensitive
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars that aren't defined here
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Parse CORS_ORIGINS string into a list.

        Why a property? Environment variables are strings. We store
        multiple origins as comma-separated values, but FastAPI's
        CORSMiddleware expects a list. This property does the conversion.

        Example: "http://localhost:5173,http://localhost:3000"
                 → ["http://localhost:5173", "http://localhost:3000"]
        """
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def upload_dir_path(self) -> Path:
        """Get the absolute path to the upload directory."""
        return BASE_DIR / self.UPLOAD_DIR

    @property
    def vector_store_dir_path(self) -> Path:
        """Get the absolute path to the vector store directory."""
        return BASE_DIR / self.VECTOR_STORE_PATH

    @property
    def database_url_resolved(self) -> str:
        """
        Resolve the database URL to an absolute path for SQLite.

        SQLite URLs are relative by default (sqlite:///data/chatbot.db).
        We resolve them to absolute paths so the DB file is always created
        in the correct location regardless of where you run the server from.

        PostgreSQL URLs are returned as-is.
        """
        if self.DATABASE_URL.startswith("sqlite"):
            # sqlite:///data/chatbot.db → sqlite:///C:/Users/.../backend/data/chatbot.db
            db_path = self.DATABASE_URL.replace("sqlite:///", "")
            absolute_path = BASE_DIR / db_path
            return f"sqlite+aiosqlite:///{absolute_path}"
        return self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings (singleton).

    === WHAT IS @lru_cache? ===
    It's a decorator that caches the function's return value.
    The first call creates a Settings object (reads .env, validates).
    Every subsequent call returns the SAME object without re-reading .env.

    This is the "Singleton Pattern" — ensuring only ONE Settings instance exists.

    === WHY? ===
    Parsing .env and validating settings is expensive.
    We only want to do it ONCE, not every time someone calls get_settings().

    === USAGE ===
        settings = get_settings()
        print(settings.APP_NAME)  # "EduBot"
    """
    return Settings()

"""
Database Initialization for EduBot.

=== WHAT DOES THIS FILE DO? ===
This file creates all the database tables when the application starts.

=== HOW TABLE CREATION WORKS ===
1. SQLAlchemy reads all model classes (Conversation, Message, Document)
2. It checks if the tables already exist in the database
3. If they don't exist, it creates them
4. If they already exist, it skips them (safe to run multiple times)

=== WHEN IS THIS CALLED? ===
This is called during application startup (in main.py):
    @app.on_event("startup")
    async def startup():
        await init_database()

This ensures tables exist BEFORE any request is processed.
"""

from app.db.session import engine
from app.models.database import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_database() -> None:
    """
    Create all database tables.

    Uses Base.metadata.create_all() which:
    1. Reads the metadata from all model classes that inherit from Base
    2. Generates CREATE TABLE SQL statements
    3. Executes them against the database
    4. Skips tables that already exist (checkfirst=True by default)

    This is safe to call multiple times — it won't drop existing data.
    """
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        # run_sync is needed because create_all is a synchronous operation
        # We wrap it in run_sync to use it within our async context
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully.")

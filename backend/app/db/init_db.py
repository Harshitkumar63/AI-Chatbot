"""
Database Initialization for Eduzyra.

=== WHAT DOES THIS FILE DO? ===
Creates all database tables, performs non-destructive schema migrations (e.g. adding columns),
and seeds authoritative course data on startup.
"""

from sqlalchemy import text
from app.db.seed_courses import seed_courses_if_empty
from app.db.session import async_session_factory, engine
from app.models.database import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_database() -> None:
    """
    Create all database tables, run SQLite column migrations, and seed initial course catalog.
    """
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Run non-destructive SQLite column migrations
        try:
            # Check if answer_mode column exists in messages table
            columns_res = await conn.execute(text("PRAGMA table_info(messages);"))
            columns = [row[1] for row in columns_res.fetchall()]
            if "answer_mode" not in columns and len(columns) > 0:
                logger.info("Migrating table 'messages': adding 'answer_mode' column...")
                await conn.execute(text("ALTER TABLE messages ADD COLUMN answer_mode VARCHAR(50);"))
        except Exception as e:
            logger.warning(f"Column migration check note: {e}")

    logger.info("Database tables initialized successfully.")

    # Seed authoritative course data if table is currently empty
    async with async_session_factory() as session:
        seeded_count = await seed_courses_if_empty(session)
        if seeded_count > 0:
            logger.info(f"Initialized database with {seeded_count} courses.")

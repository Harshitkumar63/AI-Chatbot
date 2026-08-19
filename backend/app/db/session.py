"""
Database Session Management for EduBot.

=== WHAT IS A DATABASE SESSION? ===
A session is a "workspace" for talking to the database.
Think of it like opening a document in Word:
1. You open the document (create a session)
2. You make changes (add/edit/delete records)
3. You save (commit) or discard (rollback)
4. You close the document (close the session)

=== WHAT IS AN ENGINE? ===
The engine is the connection to the database.
It knows WHERE the database is and HOW to talk to it.

=== WHAT IS async? ===
"async" means the code can do other things while waiting.
Example: While waiting for a database query to return,
the server can handle other user requests.
Without async, the server would freeze until the query completes.

=== WHY AsyncSession? ===
FastAPI is async-first. Using async sessions means:
- The server can handle 1000s of concurrent users
- Database queries don't block other requests
- Better performance under load

=== WHAT IS A CONTEXT MANAGER (async with)? ===
    async with get_session() as session:
        # session is active here
        session.add(message)
    # session is automatically closed here, even if an error occurred

This pattern guarantees the session is ALWAYS closed properly.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_engine():
    """
    Create the SQLAlchemy async engine.

    The engine manages the actual connection pool to the database.

    Parameters explained:
    - echo: If True, prints all SQL queries to the console (useful for debugging)
    - future: Use SQLAlchemy 2.0 style (modern API)
    """
    settings = get_settings()
    database_url = settings.database_url_resolved

    logger.info(f"Creating database engine for: {database_url.split('///')[0]}///***")

    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,  # Print SQL in debug mode
        future=True,
    )

    return engine


# Create the engine (module-level, created once when imported)
engine = create_engine()

# Create a session factory
# This is a "factory" — it creates new session objects when called
# expire_on_commit=False means we can access attributes after commit
# (otherwise SQLAlchemy would expire them and require a new query)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.

    === WHAT IS A DEPENDENCY? ===
    In FastAPI, a "dependency" is a function that provides something
    your endpoint needs. FastAPI calls it automatically and passes
    the result to your endpoint function.

    Usage in an endpoint:
        @router.post("/chat")
        async def chat(session: AsyncSession = Depends(get_session)):
            # 'session' is ready to use
            result = await session.execute(select(Message))

    The `yield` keyword makes this a generator:
    1. Code BEFORE yield runs first (creates the session)
    2. The session is given to the endpoint
    3. Code AFTER yield runs when the endpoint finishes (closes the session)
    4. If an error occurs, the session is still closed (finally)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

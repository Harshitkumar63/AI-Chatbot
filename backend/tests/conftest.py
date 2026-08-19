"""
Pytest configuration and global fixtures.
"""

import asyncio
import pytest
from app.db.init_db import init_database


@pytest.fixture(autouse=True, scope="session")
def initialize_db():
    """Ensure database tables exist before running any tests."""
    asyncio.run(init_database())

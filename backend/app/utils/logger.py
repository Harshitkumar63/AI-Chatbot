"""
Centralized Logging Configuration for EduBot.

=== WHAT IS LOGGING? ===
Logging is like a diary for your application. Instead of using print(),
which just dumps text to the console, logging gives you:
- Severity levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Timestamps (when did this happen?)
- Source info (which file, which function?)
- Formatted output (consistent, readable)
- Output control (log to file, console, or both)

=== WHY NOT JUST USE print()? ===
print() problems:
  - No severity levels → you can't filter what's important
  - No timestamps → you don't know WHEN something happened
  - Can't turn off → in production, prints slow things down
  - No file logging → if the app crashes, the output is gone

=== HOW TO USE ===
    from app.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("User sent a message")
    logger.error("Failed to connect to LLM", exc_info=True)
    logger.debug("Retrieved 4 chunks from FAISS")  # Only shown in DEBUG mode
"""

import logging
import sys
from typing import Optional

from app.config import get_settings


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Create and configure a logger instance.

    Parameters
    ----------
    name : str, optional
        The logger name. Convention is to use __name__ so the logger
        shows which module generated the log message.
        Example: "app.core.chat_service"

    Returns
    -------
    logging.Logger
        A configured logger instance ready to use.

    How Python Logging Works Internally
    ------------------------------------
    Python's logging module has a hierarchy:
    1. Logger — the object you call .info(), .error() on
    2. Handler — WHERE to send the log (console, file, etc.)
    3. Formatter — HOW to format the message (timestamp, level, etc.)

    We configure:
    - StreamHandler → sends to console (stdout)
    - Formatter → "[2024-01-15 10:30:45] [INFO] [chat_service] Message here"
    """
    settings = get_settings()

    # Create or get a logger with the given name
    logger = logging.getLogger(name or "edubot")

    # Only configure handlers if they haven't been added yet
    # (prevents duplicate log lines when get_logger is called multiple times)
    if not logger.handlers:
        # Set the minimum severity level
        # DEBUG → shows everything
        # INFO → shows INFO and above (no DEBUG)
        # WARNING → shows WARNING and above
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        logger.setLevel(log_level)

        # Create a handler that sends output to the console with UTF-8 support
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # Create a formatter that makes logs readable
        # Example output: [2024-01-15 10:30:45] [INFO    ] [chat_service] User sent message
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)

        # Attach the handler to the logger
        logger.addHandler(console_handler)

        # Prevent log messages from being passed to parent loggers
        # (avoids duplicate messages)
        logger.propagate = False

    return logger

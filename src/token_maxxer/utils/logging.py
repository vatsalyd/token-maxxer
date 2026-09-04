"""Structured logging utilities for token-maxxer.

Provides context-aware logging helpers that automatically include
guild, user, and project context in log messages.
"""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger for a module.

    Usage:
        log = get_logger(__name__)
        log.info("Something happened")

    Args:
        name: Module name, typically ``__name__``.

    Returns:
        A logger namespaced under ``token_maxxer``.
    """
    # Ensure all loggers are children of the root token_maxxer logger
    if not name.startswith("token_maxxer"):
        name = f"token_maxxer.{name}"
    return logging.getLogger(name)


def log_action(
    logger: logging.Logger,
    *,
    action: str,
    result: str = "success",
    guild_id: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Log a structured action with optional context fields.

    Produces log lines like:
        INFO  token_maxxer.services.guild  guild=123 user=456 action=create_role result=success

    Args:
        logger: The logger instance to use.
        action: Short description of the action (e.g. ``create_role``).
        result: Outcome of the action (e.g. ``success``, ``skipped``, ``failed``).
        guild_id: Discord guild ID, if applicable.
        user_id: Discord user ID, if applicable.
        project_id: Internal project ID, if applicable.
        level: Logging level (default: INFO).
        **extra: Additional key=value pairs to include in the log.
    """
    parts: list[str] = []

    if guild_id is not None:
        parts.append(f"guild={guild_id}")
    if user_id is not None:
        parts.append(f"user={user_id}")
    if project_id is not None:
        parts.append(f"project={project_id}")

    parts.append(f"action={action}")
    parts.append(f"result={result}")

    for key, value in extra.items():
        parts.append(f"{key}={value}")

    logger.log(level, "  ".join(parts))

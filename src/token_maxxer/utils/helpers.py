"""General helper utilities for token-maxxer.

Small, reusable functions that don't belong to a specific service layer.
"""

from __future__ import annotations

from datetime import UTC, datetime

import discord


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Used for database timestamps where consistency matters.
    """
    return datetime.now(UTC).isoformat()


def format_timestamp(dt: datetime | str, style: str = "R") -> str:
    """Format a datetime as a Discord dynamic timestamp.

    Args:
        dt: A datetime object or ISO 8601 string.
        style: Discord timestamp style (R=relative, F=full, f=short, etc.).

    Returns:
        A Discord timestamp markdown string like ``<t:1234567890:R>``.
    """
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return discord.utils.format_dt(dt, style=style)


def truncate(text: str, max_length: int = 1024, suffix: str = "…") -> str:
    """Truncate a string to a maximum length, adding a suffix if truncated.

    Useful for fitting text into Discord embed field limits.

    Args:
        text: The text to truncate.
        max_length: Maximum allowed length.
        suffix: String to append if truncated.

    Returns:
        The original or truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def make_embed(
    *,
    title: str | None = None,
    description: str | None = None,
    color: discord.Color | None = None,
    footer: str | None = None,
) -> discord.Embed:
    """Create a standardized Discord embed.

    Provides a consistent look-and-feel across all bot responses.

    Args:
        title: Embed title.
        description: Embed description/body text.
        color: Embed sidebar color (defaults to blurple).
        footer: Footer text.

    Returns:
        A configured Discord Embed.
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else discord.Color.blurple(),
        timestamp=datetime.now(UTC),
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def success_embed(title: str, description: str | None = None) -> discord.Embed:
    """Create a green success embed."""
    return make_embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
    )


def error_embed(title: str, description: str | None = None) -> discord.Embed:
    """Create a red error embed."""
    return make_embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
    )


def info_embed(title: str, description: str | None = None) -> discord.Embed:
    """Create a blue info embed."""
    return make_embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blurple(),
    )


def warning_embed(title: str, description: str | None = None) -> discord.Embed:
    """Create a yellow warning embed."""
    return make_embed(
        title=f"⚠️ {title}",
        description=description,
        color=discord.Color.yellow(),
    )

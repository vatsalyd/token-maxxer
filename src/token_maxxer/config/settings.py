"""Application settings loaded from environment variables.

Uses python-dotenv to load .env files in development.
All required configuration is validated at startup.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings.

    Attributes:
        discord_token: Bot authentication token from Discord Developer Portal.
        target_guild_id: The DSAI Club guild (server) ID for command registration.
        log_level: Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        database_path: Path to the SQLite database file.
    """

    discord_token: str
    target_guild_id: int
    log_level: str
    database_path: Path

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables.

        Loads .env file if present, then validates all required variables.

        Returns:
            A validated Settings instance.

        Raises:
            SystemExit: If required environment variables are missing or invalid.
        """
        load_dotenv()

        errors: list[str] = []

        # --- Required: DISCORD_TOKEN ---
        discord_token = os.getenv("DISCORD_TOKEN", "").strip()
        if not discord_token:
            errors.append("DISCORD_TOKEN is not set or is empty.")

        # --- Required: TARGET_GUILD_ID ---
        raw_guild_id = os.getenv("TARGET_GUILD_ID", "").strip()
        target_guild_id = 0
        if not raw_guild_id:
            errors.append("TARGET_GUILD_ID is not set or is empty.")
        else:
            try:
                target_guild_id = int(raw_guild_id)
            except ValueError:
                errors.append(
                    f"TARGET_GUILD_ID must be a valid integer, got: '{raw_guild_id}'"
                )

        # --- Optional: LOG_LEVEL (default: INFO) ---
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level not in valid_levels:
            errors.append(
                f"LOG_LEVEL must be one of {valid_levels}, got: '{log_level}'"
            )

        # --- Optional: DATABASE_PATH (default: data/token_maxxer.db) ---
        database_path = Path(
            os.getenv("DATABASE_PATH", "data/token_maxxer.db").strip()
        )

        # --- Report all errors at once ---
        if errors:
            print("❌ Configuration errors:", file=sys.stderr)
            for error in errors:
                print(f"  • {error}", file=sys.stderr)
            print(
                "\nSee .env.example for required configuration.",
                file=sys.stderr,
            )
            sys.exit(1)

        return cls(
            discord_token=discord_token,
            target_guild_id=target_guild_id,
            log_level=log_level,
            database_path=database_path,
        )


# Module-level singleton, loaded on first import.
settings = Settings.from_env()

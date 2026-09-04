"""token-maxxer bot entry point.

Initializes the Discord bot with required intents, sets up the command tree,
and connects to the Discord gateway. Run with:

    python -m token_maxxer.bot
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.config.settings import settings
from token_maxxer.utils.checks import NotAuthorizedError

log = logging.getLogger("token_maxxer")


class TokenMaxxer(commands.Bot):
    """Main bot client for the DSAI Club Discord server.

    Handles gateway connection, command tree setup, and cog loading.
    Commands are synced to the target guild only during development
    for fast slash-command registration.
    """

    def __init__(self) -> None:
        # Only enable the intents the bot actually needs.
        intents = discord.Intents.default()
        intents.members = True  # Required for member management
        intents.message_content = False  # Not needed — we use slash commands

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

        self.target_guild = discord.Object(id=settings.target_guild_id)
        self.start_time: datetime | None = None

    async def setup_hook(self) -> None:
        """Called after login, before the bot starts receiving events.

        Loads cog extensions and syncs the command tree to the target guild.
        Guild-scoped sync is used during development for instant command updates
        (global sync can take up to an hour).
        """
        # Load cogs — will be added as extensions are built
        cog_extensions: list[str] = [
            "token_maxxer.cogs.utility",
            "token_maxxer.cogs.setup",
            # "token_maxxer.cogs.projects",
            # "token_maxxer.cogs.teams",
            # "token_maxxer.cogs.moderation",
        ]

        for ext in cog_extensions:
            try:
                await self.load_extension(ext)
                log.info("Loaded extension: %s", ext)
            except Exception:
                log.exception("Failed to load extension: %s", ext)

        # Sync commands to the target guild for fast registration
        self.tree.copy_global_to(guild=self.target_guild)
        await self.tree.sync(guild=self.target_guild)
        log.info(
            "Command tree synced to guild %s", settings.target_guild_id
        )

    async def on_ready(self) -> None:
        """Called when the bot has connected to Discord and is ready."""
        self.start_time = datetime.now(UTC)

        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.info("  token-maxxer is online!")
        log.info("  User    : %s (ID: %s)", self.user, self.user.id if self.user else "?")
        log.info("  Guild   : %s", settings.target_guild_id)
        log.info("  Latency : %.0fms", self.latency * 1000)
        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    async def on_error(self, event_method: str, /, *args, **kwargs) -> None:
        """Global error handler for non-command events."""
        log.exception("Unhandled exception in event: %s", event_method)


async def _setup_tree_error_handler(tree: app_commands.CommandTree) -> None:
    """Attach a global error handler to the command tree."""

    @tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Handle errors raised by slash commands."""
        if isinstance(error, NotAuthorizedError):
            msg = f"❌ {error}"
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You don't have permission to use this command."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.CheckFailure):
            msg = "❌ You are not authorized to use this command."
        else:
            msg = "❌ An unexpected error occurred. Please try again later."
            log.exception(
                "Unhandled command error in /%s (user=%s, guild=%s)",
                interaction.command.name if interaction.command else "unknown",
                interaction.user.id,
                interaction.guild_id,
                exc_info=error,
            )

        # Respond ephemerally so only the user sees the error
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            log.warning("Failed to send error response to user %s", interaction.user.id)


def _setup_logging() -> None:
    """Configure structured logging based on settings."""
    log_format = (
        "%(asctime)s │ %(levelname)-7s │ %(name)-25s │ %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Reduce noise from discord.py internals
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


def main() -> None:
    """Bot entry point."""
    _setup_logging()

    log.info("Starting token-maxxer...")
    log.info("Target guild: %s", settings.target_guild_id)

    client = TokenMaxxer()

    # Attach the global command error handler
    asyncio.get_event_loop().run_until_complete(
        _setup_tree_error_handler(client.tree)
    )

    client.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()

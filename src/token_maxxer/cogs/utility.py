"""Utility cog — basic bot health and information commands.

Commands:
    /ping   — Check bot latency.
    /botinfo — Display bot version, uptime, and server information.
"""

from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer import __version__
from token_maxxer.utils.helpers import info_embed
from token_maxxer.utils.logging import get_logger

log = get_logger(__name__)


class Utility(commands.Cog):
    """Basic utility commands for health checks and bot information."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Respond with the bot's current websocket latency."""
        latency_ms = round(self.bot.latency * 1000)

        # Choose emoji based on latency quality
        if latency_ms < 100:
            emoji = "🟢"
        elif latency_ms < 200:
            emoji = "🟡"
        else:
            emoji = "🔴"

        embed = info_embed(
            title="Pong!",
            description=f"{emoji} Latency: **{latency_ms}ms**",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        log.info(
            "guild=%s user=%s action=ping latency=%dms",
            interaction.guild_id,
            interaction.user.id,
            latency_ms,
        )

    @app_commands.command(name="botinfo", description="Display bot information")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        """Show bot version, uptime, guild count, and system information."""
        # Calculate uptime
        uptime_str = "Unknown"
        bot_client = self.bot
        if hasattr(bot_client, "start_time") and bot_client.start_time:
            delta = datetime.now(timezone.utc) - bot_client.start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)

            parts: list[str] = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m {seconds}s")
            uptime_str = " ".join(parts)

        # Build info embed
        embed = info_embed(title="token-maxxer")
        embed.add_field(name="Version", value=f"`{__version__}`", inline=True)
        embed.add_field(
            name="Latency",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True,
        )
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(
            name="Guilds",
            value=f"`{len(self.bot.guilds)}`",
            inline=True,
        )
        embed.add_field(
            name="Python",
            value=f"`discord.py {discord.__version__}`",
            inline=True,
        )

        embed.set_footer(text="DSAI Club • Internal Bot")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        log.info(
            "guild=%s user=%s action=botinfo",
            interaction.guild_id,
            interaction.user.id,
        )


async def setup(bot: commands.Bot) -> None:
    """Load the Utility cog into the bot."""
    await bot.add_cog(Utility(bot))

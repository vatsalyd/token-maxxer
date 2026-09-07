"""Guide cog — private Core Team bot manual and documentation commands.

Commands:
    /guide publish — Purge and publish the complete manual in #🤖・bot-guide.
    /guide view    — Inspect a specific manual section ephemerally.
"""

from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.services.guide_service import GuideService
from token_maxxer.utils.checks import is_core_or_higher
from token_maxxer.utils.helpers import error_embed, success_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)

SectionLiteral = Literal[
    "overview",
    "governance",
    "onboarding",
    "projects",
    "teams",
    "developer",
    "troubleshooting",
]


class Guide(
    commands.GroupCog,
    group_name="guide",
    group_description="Core Team documentation and bot manual management",
):
    """Cog providing private Core Team bot documentation and publishing tools."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guide_service = GuideService(bot)

    @app_commands.command(
        name="publish",
        description="Publish or refresh the complete Core Team manual in #🤖・bot-guide.",
    )
    @is_core_or_higher()
    async def publish(self, interaction: discord.Interaction) -> None:
        """Publish or update all 7 guide sections in #🤖・bot-guide."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        success, msg = await self.guide_service.publish_bot_guide(interaction.guild)

        if success:
            embed = success_embed(
                title="Bot Guide Published",
                description=(
                    f"✅ {msg}\n\n"
                    "The guide is visible only to members with `🔧 Core Member` and above."
                ),
            )
        else:
            embed = error_embed(
                title="Guide Publishing Failed",
                description=f"❌ {msg}",
            )

        await interaction.followup.send(embed=embed, ephemeral=True)
        log_action(
            log,
            action="publish_guide",
            result="success" if success else "failed",
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

    @app_commands.command(
        name="view",
        description="Read a specific section of the Core Team manual ephemerally.",
    )
    @app_commands.describe(section="The guide chapter to display")
    @app_commands.choices(
        section=[
            app_commands.Choice(name="1. Overview & Architecture", value="overview"),
            app_commands.Choice(name="2. Server Governance (/setup)", value="governance"),
            app_commands.Choice(name="3. Community Onboarding (/onboard)", value="onboarding"),
            app_commands.Choice(name="4. Project Lifecycle (/project)", value="projects"),
            app_commands.Choice(name="5. Teams & Permissions (/team)", value="teams"),
            app_commands.Choice(name="6. Developer Guide (Extending Bot)", value="developer"),
            app_commands.Choice(name="7. Troubleshooting & Gotchas", value="troubleshooting"),
        ]
    )
    @is_core_or_higher()
    async def view(
        self,
        interaction: discord.Interaction,
        section: app_commands.Choice[str],
    ) -> None:
        """Display a single guide section privately to the calling Core member."""
        try:
            embed = self.guide_service.get_section_embed(section.value)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except KeyError:
            err = error_embed(
                title="Invalid Section",
                description=f"Section `{section.value}` was not recognized.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Guide cog into the bot."""
    await bot.add_cog(Guide(bot))

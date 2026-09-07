"""Onboarding cog — slash commands and automated greeting workflows.

Commands:
    /onboard setup        — Populate or refresh content in all START HERE channels.
    /onboard test-welcome — Preview the newcomer greeting card in #👋・welcome.

Events:
    on_member_join        — Auto-assigns Member role and greets newcomer in #👋・welcome.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.config.settings import settings
from token_maxxer.services.onboarding_service import OnboardingService
from token_maxxer.utils.checks import is_coordinator_or_admin
from token_maxxer.utils.constants import ROLE_MEMBER
from token_maxxer.utils.helpers import error_embed, success_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)


class Onboarding(
    commands.GroupCog,
    group_name="onboard",
    group_description="Onboarding and START HERE channel management",
):
    """Cog handling newcomer welcoming, automated role assignment, and START HERE channels."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.onboarding_service = OnboardingService(bot)

    # ─── Event Listeners ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handle new members joining the server.

        1. Automatically assigns the base Member role.
        2. Sends a formatted welcome greeting embed into #👋・welcome.
        """
        # Ensure the event is for the configured target guild
        if member.guild.id != settings.target_guild_id:
            return

        guild = member.guild

        # 1. Auto-assign the Member role
        member_role = discord.utils.get(guild.roles, name=ROLE_MEMBER)
        if member_role is not None and member_role not in member.roles:
            try:
                await member.add_roles(
                    member_role,
                    reason="token-maxxer auto-onboarding: default member role",
                )
                log_action(
                    log,
                    action="auto_assign_member_role",
                    result="success",
                    guild_id=guild.id,
                    user_id=member.id,
                )
            except discord.Forbidden:
                log_action(
                    log,
                    action="auto_assign_member_role",
                    result="forbidden",
                    guild_id=guild.id,
                    user_id=member.id,
                )

        # 2. Send greeting embed to #👋・welcome
        welcome_channel = discord.utils.get(guild.text_channels, name="👋・welcome")
        if welcome_channel is not None:
            try:
                greeting = self.onboarding_service.build_welcome_greeting_embed(member)
                await welcome_channel.send(content=member.mention, embed=greeting)
                log_action(
                    log,
                    action="send_welcome_greeting",
                    result="success",
                    guild_id=guild.id,
                    user_id=member.id,
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("Failed to send welcome greeting for member %s: %s", member.id, exc)

    # ─── Slash Commands ────────────────────────────────────────────────────────

    @app_commands.command(
        name="setup",
        description="Populate or refresh official embeds and role selectors in all START HERE channels.",
    )
    @is_coordinator_or_admin()
    async def setup_onboarding(self, interaction: discord.Interaction) -> None:
        """Populate the 4 START HERE channels with rules, guide, and interactive role picker."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        count, errors = await self.onboarding_service.populate_start_here_channels(guild)

        if errors:
            err_text = "\n".join(f"• {e}" for e in errors)
            embed = error_embed(
                title="Onboarding Setup Partially Completed",
                description=(
                    f"Populated **{count}/4** START HERE channels.\n\n"
                    f"**Issues encountered:**\n{err_text}"
                ),
            )
        else:
            embed = success_embed(
                title="Onboarding Setup Complete",
                description=(
                    f"✅ Successfully populated all **{count}** START HERE channels with authoritative content!\n\n"
                    "• `📜・rules`: Code of Conduct & Guidelines published.\n"
                    "• `👋・welcome`: Welcome & Mission Statement published.\n"
                    "• `🧭・server-guide`: Server Roadmap & Command Directory published.\n"
                    "• `🎭・roles`: Interactive Role Picker & Member claim buttons published.\n\n"
                    "Newcomers can now self-assign interest roles and get started immediately."
                ),
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

        log_action(
            log,
            action="onboard_setup",
            result="complete",
            guild_id=guild.id,
            user_id=interaction.user.id,
            populated=count,
            errors=len(errors),
        )

    @app_commands.command(
        name="test-welcome",
        description="Simulate a new member join and preview the greeting message in #👋・welcome.",
    )
    @is_coordinator_or_admin()
    async def test_welcome(self, interaction: discord.Interaction) -> None:
        """Preview the new member greeting card in #👋・welcome."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        welcome_channel = discord.utils.get(interaction.guild.text_channels, name="👋・welcome")
        if welcome_channel is None:
            err = error_embed(
                title="Channel Not Found",
                description="Channel `👋・welcome` does not exist. Run `/setup` first.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)
            return

        greeting = self.onboarding_service.build_welcome_greeting_embed(interaction.user)
        try:
            await welcome_channel.send(content=interaction.user.mention, embed=greeting)
            await interaction.response.send_message(
                f"✅ Sent test welcome greeting to {welcome_channel.mention}!",
                ephemeral=True,
            )
        except discord.Forbidden:
            err = error_embed(
                title="Permission Denied",
                description=f"Bot lacks permissions to send messages to {welcome_channel.mention}.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Onboarding cog into the bot."""
    await bot.add_cog(Onboarding(bot))

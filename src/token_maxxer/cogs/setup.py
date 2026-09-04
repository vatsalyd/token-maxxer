"""Setup cog — server structure provisioning and reconciliation.

Provides the ``/setup`` slash command for club coordinators and admins to
idempotently bootstrap or repair server roles, categories, channels,
and permissions.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.services.guild_service import GuildService
from token_maxxer.services.permission_service import PermissionService
from token_maxxer.utils.checks import is_coordinator_or_admin
from token_maxxer.utils.helpers import warning_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)


class Setup(commands.Cog):
    """Server provisioning and reconciliation command cog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_service = GuildService(bot)
        self.permission_service = PermissionService(bot)

    @app_commands.command(
        name="setup",
        description="Provision or repair the DSAI Club server structure and permissions.",
    )
    @app_commands.describe(
        verify_only="If True, only audits server structure without creating or modifying resources",
    )
    @is_coordinator_or_admin()
    async def setup_command(
        self,
        interaction: discord.Interaction,
        verify_only: bool = False,
    ) -> None:
        """Run idempotent server setup or verification.

        Args:
            interaction: The Discord interaction.
            verify_only: Whether to perform a dry-run verification audit only.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be executed within a Discord server.",
                ephemeral=True,
            )
            return

        # Defer immediately because reconciliation may take several seconds
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild

        if verify_only:
            log_action(
                log,
                action="setup_verify",
                result="start",
                guild_id=guild.id,
                user_id=interaction.user.id,
            )
            v_report = self.guild_service.verify_server_structure(guild)
            embed = v_report.to_embed()
            await interaction.followup.send(embed=embed, ephemeral=True)
            log_action(
                log,
                action="setup_verify",
                result="complete",
                guild_id=guild.id,
                user_id=interaction.user.id,
                is_complete=v_report.is_complete,
            )
            return

        # Full reconciliation
        log_action(
            log,
            action="setup_reconcile",
            result="start",
            guild_id=guild.id,
            user_id=interaction.user.id,
        )

        try:
            # 1. Roles, categories, channels
            report = await self.guild_service.reconcile_server_structure(guild)

            # 2. Permission overwrites
            perm_count, perm_errors = await self.permission_service.reconcile_guild_permissions(
                guild
            )
            report.errors.extend(perm_errors)

            # 3. Build response embed
            embed = report.to_embed()
            embed.add_field(
                name="Permissions",
                value=f"✅ {perm_count} categories & channels reconciled",
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            log_action(
                log,
                action="setup_reconcile",
                result="complete",
                guild_id=guild.id,
                user_id=interaction.user.id,
                roles=report.total_roles,
                categories=report.total_categories,
                channels=report.total_channels,
                permissions=perm_count,
                errors=len(report.errors),
            )

        except Exception as exc:
            log.exception(
                "Unexpected error during /setup (guild=%s, user=%s)",
                guild.id,
                interaction.user.id,
            )
            err_embed = warning_embed(
                title="Setup encountered an unexpected error",
                description=(
                    f"An error occurred during server reconciliation: `{exc}`\n"
                    "Please verify bot permissions and try running `/setup` again."
                ),
            )
            await interaction.followup.send(embed=err_embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Setup cog into the bot."""
    await bot.add_cog(Setup(bot))

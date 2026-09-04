"""Teams cog — slash commands for project team management.

Commands:
    /team add           — Add a member to a project team with write access.
    /team remove        — Remove a member from a project team.
    /team list          — Display current team members and lead.
    /team transfer-lead — Transfer project leadership to another team member.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.cogs.projects import project_autocomplete
from token_maxxer.services.team_service import (
    TeamAuthorizationError,
    TeamService,
    TeamValidationError,
)
from token_maxxer.utils.helpers import error_embed
from token_maxxer.utils.logging import get_logger, log_action
from token_maxxer.views.team_views import (
    build_lead_transferred_embed,
    build_member_added_embed,
    build_member_removed_embed,
    build_team_list_embed,
)

log = get_logger(__name__)


class Teams(
    commands.GroupCog,
    group_name="team",
    group_description="Project team management commands",
):
    """Slash command group for managing project teams."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.team_service = TeamService(bot)

    async def _resolve_project(
        self,
        interaction: discord.Interaction,
        project_input: str,
    ) -> int | None:
        """Resolve project ID from autocomplete or text input."""
        if interaction.guild_id is None:
            return None

        clean = project_input.strip()
        if clean.isdigit():
            return int(clean)

        found = await self.team_service.db.get_project_by_name(interaction.guild_id, clean)
        if found is not None:
            return found.id

        return None

    # ─── /team add ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="add",
        description="Add a member to a project team, granting write access to workspace channels.",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
        member="The Discord member to add to the team",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def add_member(
        self,
        interaction: discord.Interaction,
        project: str,
        member: discord.Member,
    ) -> None:
        """Add a collaborator to a project."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        project_id = await self._resolve_project(interaction, project)
        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{project}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        proj = await self.team_service.db.get_project(project_id)
        if proj is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Project #{project_id} does not exist.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        try:
            self.team_service.verify_caller_authorization(interaction.user, proj)
            await self.team_service.add_member(interaction.guild, proj.id, member)

            embed = build_member_added_embed(proj, member)
            await interaction.followup.send(embed=embed)

            log_action(
                log,
                action="team_add_member",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                target_user=member.id,
                project_id=proj.id,
            )

        except (TeamAuthorizationError, TeamValidationError) as exc:
            err = error_embed(title="Team Operation Failed", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)

    # ─── /team remove ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="remove",
        description="Remove a member from a project team and revoke workspace write access.",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
        member="The Discord member to remove from the team",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def remove_member(
        self,
        interaction: discord.Interaction,
        project: str,
        member: discord.Member,
    ) -> None:
        """Remove a collaborator from a project."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        project_id = await self._resolve_project(interaction, project)
        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{project}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        proj = await self.team_service.db.get_project(project_id)
        if proj is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Project #{project_id} does not exist.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        try:
            self.team_service.verify_caller_authorization(interaction.user, proj)
            await self.team_service.remove_member(interaction.guild, proj.id, member)

            embed = build_member_removed_embed(proj, member)
            await interaction.followup.send(embed=embed)

            log_action(
                log,
                action="team_remove_member",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                target_user=member.id,
                project_id=proj.id,
            )

        except (TeamAuthorizationError, TeamValidationError) as exc:
            err = error_embed(title="Team Operation Failed", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)

    # ─── /team list ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="list",
        description="List all members collaborating on a project.",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def list_team(
        self,
        interaction: discord.Interaction,
        project: str,
    ) -> None:
        """View team roster for a project."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        project_id = await self._resolve_project(interaction, project)
        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{project}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        proj = await self.team_service.db.get_project(project_id)
        if proj is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Project #{project_id} does not exist.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        members = await self.team_service.list_members(proj.id)
        embed = build_team_list_embed(proj, members)
        await interaction.followup.send(embed=embed)

        log_action(
            log,
            action="view_team_list",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            project_id=proj.id,
            count=len(members),
        )

    # ─── /team transfer-lead ──────────────────────────────────────────────────

    @app_commands.command(
        name="transfer-lead",
        description="Transfer project leadership to another team member.",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
        new_lead="The Discord member who will become the new project lead",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def transfer_lead(
        self,
        interaction: discord.Interaction,
        project: str,
        new_lead: discord.Member,
    ) -> None:
        """Transfer leadership of a project."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        project_id = await self._resolve_project(interaction, project)
        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{project}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        proj = await self.team_service.db.get_project(project_id)
        if proj is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Project #{project_id} does not exist.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        # Only current lead, server owner, or Coordinator/Admin can transfer lead
        is_lead = interaction.user.id == proj.lead_id
        is_admin_or_coord = (
            interaction.user.id == interaction.guild.owner_id
            or interaction.user.guild_permissions.administrator
            or any(
                r.name in ("👑 Club Admin", "⚡ Coordinator")
                for r in interaction.user.roles
            )
        )

        if not (is_lead or is_admin_or_coord):
            err = error_embed(
                title="Unauthorized",
                description=(
                    f"Only the current lead (<@{proj.lead_id}>) or a Coordinator/Admin "
                    "can transfer project leadership."
                ),
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        try:
            updated_proj = await self.team_service.transfer_lead(
                interaction.guild, proj.id, new_lead
            )
            embed = build_lead_transferred_embed(updated_proj, new_lead)
            await interaction.followup.send(embed=embed)

            log_action(
                log,
                action="transfer_project_lead",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                project_id=proj.id,
                new_lead=new_lead.id,
            )

        except TeamValidationError as exc:
            err = error_embed(title="Transfer Failed", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Teams cog into the bot."""
    await bot.add_cog(Teams(bot))

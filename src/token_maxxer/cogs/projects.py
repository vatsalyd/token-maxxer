"""Projects cog — slash commands for project workspaces.

Commands:
    /project create — Open interactive modal to create a new project workspace.
    /project list   — List projects in the server with optional status filter.
    /project info   — View detailed project specifications, team, and progress.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.database import db
from token_maxxer.services.project_service import (
    ProjectNotFoundError,
    ProjectService,
)
from token_maxxer.utils.checks import can_create_projects
from token_maxxer.utils.constants import ProjectStatus
from token_maxxer.utils.helpers import error_embed
from token_maxxer.utils.logging import get_logger, log_action
from token_maxxer.views.project_views import (
    ProjectCreateModal,
    build_project_info_embed,
    build_project_list_embed,
)

log = get_logger(__name__)


async def project_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Provide autocomplete suggestions for project names and IDs."""
    if interaction.guild_id is None:
        return []

    projects = await db.list_projects(interaction.guild_id)
    choices: list[app_commands.Choice[str]] = []
    current_lower = current.strip().lower()

    for p in projects:
        if not current_lower or current_lower in p.name.lower() or str(p.id) == current_lower:
            label = f"#{p.id} — {p.name}"[:100]
            choices.append(app_commands.Choice(name=label, value=str(p.id)))
            if len(choices) >= 25:
                break

    return choices


class Projects(
    commands.GroupCog,
    group_name="project",
    group_description="Project workspace commands",
):
    """Command cog for project workspaces and discovery."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.project_service = ProjectService(bot)

    # ─── /project create ──────────────────────────────────────────────────────

    @app_commands.command(
        name="create",
        description="Launch a new project workspace (opens an interactive creation form).",
    )
    @can_create_projects()
    async def create(self, interaction: discord.Interaction) -> None:
        """Open the interactive project creation modal."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Projects can only be created inside a Discord server.",
                ephemeral=True,
            )
            return

        modal = ProjectCreateModal(project_service=self.project_service)
        await interaction.response.send_modal(modal)

        log_action(
            log,
            action="open_project_modal",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
        )

    # ─── /project list ────────────────────────────────────────────────────────

    @app_commands.command(
        name="list",
        description="List projects in the server with optional status filter.",
    )
    @app_commands.describe(
        status="Filter projects by lifecycle status (ACTIVE, IDEA, COMPLETED, ARCHIVED)",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="🟢 Active", value=ProjectStatus.ACTIVE.value),
            app_commands.Choice(name="💡 Ideas", value=ProjectStatus.IDEA.value),
            app_commands.Choice(name="✅ Completed", value=ProjectStatus.COMPLETED.value),
            app_commands.Choice(name="📦 Archived", value=ProjectStatus.ARCHIVED.value),
        ]
    )
    async def list_projects(
        self,
        interaction: discord.Interaction,
        status: str | None = None,
    ) -> None:
        """List projects matching the given status filter."""
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        projects = await self.project_service.list_projects(
            guild_id=interaction.guild_id,
            status=status,
        )

        embed = build_project_list_embed(projects, status_filter=status)
        await interaction.followup.send(embed=embed)

        log_action(
            log,
            action="list_projects",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            count=len(projects),
            filter=status,
        )

    # ─── /project info ────────────────────────────────────────────────────────

    @app_commands.command(
        name="info",
        description="View detailed information, team roster, and progress updates for a project.",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def info(
        self,
        interaction: discord.Interaction,
        project: str,
    ) -> None:
        """Display comprehensive details for a specific project."""
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "❌ This command must be run inside a Discord server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        clean_input = project.strip()
        project_id: int | None = None

        if clean_input.isdigit():
            project_id = int(clean_input)
        else:
            # Try to resolve by name
            found = await db.get_project_by_name(interaction.guild_id, clean_input)
            if found is not None:
                project_id = found.id

        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find a project matching `{clean_input}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        try:
            details = await self.project_service.get_project_details(project_id)
            embed = build_project_info_embed(details)
            await interaction.followup.send(embed=embed)

            log_action(
                log,
                action="view_project_info",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                project_id=project_id,
            )

        except ProjectNotFoundError:
            err = error_embed(
                title="Project Not Found",
                description=f"Project #{project_id} does not exist.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Projects cog into the bot."""
    await bot.add_cog(Projects(bot))

"""Projects cog — slash commands for project workspaces.

Commands:
    /project create   — Open interactive modal to create a new project workspace.
    /project list     — List projects in the server with optional status filter.
    /project info     — View detailed project specifications, team, and progress.
    /project update   — Post a structured milestone or progress update.
    /project status   — Transition project lifecycle status.
    /project archive  — Safely archive a project workspace to read-only.
    /project deadline — View or set target completion deadlines.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from token_maxxer.database import db
from token_maxxer.services.project_service import (
    ProjectError,
    ProjectNotFoundError,
    ProjectService,
)
from token_maxxer.utils.checks import can_create_projects
from token_maxxer.utils.constants import ProjectStatus
from token_maxxer.utils.helpers import error_embed, success_embed
from token_maxxer.utils.logging import get_logger, log_action
from token_maxxer.views.project_views import (
    ArchiveConfirmationView,
    ProjectCreateModal,
    ProjectUpdateModal,
    build_project_archived_embed,
    build_project_deadline_embed,
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

    # ─── /project update ──────────────────────────────────────────────────────

    @app_commands.command(
        name="update",
        description="Submit a progress update for a project (opens an update form).",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def update_project(
        self,
        interaction: discord.Interaction,
        project: str,
    ) -> None:
        """Open the project progress update modal."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Updates can only be submitted inside a Discord server.",
                ephemeral=True,
            )
            return

        clean_input = project.strip()
        project_id: int | None = None

        if clean_input.isdigit():
            project_id = int(clean_input)
        else:
            found = await self.project_service.db.get_project_by_name(
                interaction.guild_id, clean_input
            )
            if found is not None:
                project_id = found.id

        if project_id is None:
            await interaction.response.send_message(
                f"❌ Project `{clean_input}` not found.",
                ephemeral=True,
            )
            return

        can_update = await self.project_service.can_post_update(
            interaction.user, project_id
        )
        if not can_update:
            await interaction.response.send_message(
                "❌ You must be an active project member, lead, or core team to post updates.",
                ephemeral=True,
            )
            return

        proj = await self.project_service.get_project(project_id)
        modal = ProjectUpdateModal(project=proj, project_service=self.project_service)
        await interaction.response.send_modal(modal)

        log_action(
            log,
            action="open_project_update_modal",
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            project_id=project_id,
        )

    # ─── /project status ──────────────────────────────────────────────────────

    @app_commands.command(
        name="status",
        description="Change a project's lifecycle status (IDEA, ACTIVE, COMPLETED, ARCHIVED).",
    )
    @app_commands.describe(
        project="Select or enter the project name or ID",
        new_status="New lifecycle status for the project",
    )
    @app_commands.choices(
        new_status=[
            app_commands.Choice(name="🟢 Active", value=ProjectStatus.ACTIVE.value),
            app_commands.Choice(name="💡 Idea", value=ProjectStatus.IDEA.value),
            app_commands.Choice(name="✅ Completed", value=ProjectStatus.COMPLETED.value),
            app_commands.Choice(name="📦 Archived", value=ProjectStatus.ARCHIVED.value),
        ]
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def change_status(
        self,
        interaction: discord.Interaction,
        project: str,
        new_status: str,
    ) -> None:
        """Update the lifecycle status of a project."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
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
            found = await self.project_service.db.get_project_by_name(
                interaction.guild_id, clean_input
            )
            if found is not None:
                project_id = found.id

        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{clean_input}`.",
            )
            await interaction.followup.send(embed=err, ephemeral=True)
            return

        try:
            updated = await self.project_service.change_project_status(
                guild=interaction.guild,
                project_id=project_id,
                new_status=new_status,
                caller=interaction.user,
            )

            embed = success_embed(
                title="Project Status Updated",
                description=(
                    f"**{updated.name}** status changed to **{updated.status}**!\n\n"
                    f"• Status: **{updated.status}**\n"
                    f"• Changed by: {interaction.user.mention}"
                ),
            )
            await interaction.followup.send(embed=embed)

            log_action(
                log,
                action="change_project_status",
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                project_id=project_id,
                status=new_status,
            )

        except ProjectError as exc:
            err = error_embed(title="Status Change Failed", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)

    # ─── /project archive ─────────────────────────────────────────────────────

    @app_commands.command(
        name="archive",
        description="Archive a project workspace, locking channels to read-only mode.",
    )
    @app_commands.describe(
        project="The project name or numeric ID to archive.",
        force="Confirm and archive immediately without interactive confirmation prompt.",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def archive(
        self,
        interaction: discord.Interaction,
        project: str,
        force: bool = False,
    ) -> None:
        """Archive a project workspace."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Project archiving can only be performed inside a Discord server.",
                ephemeral=True,
            )
            return

        clean_input = project.strip()
        project_id: int | None = None

        if clean_input.isdigit():
            project_id = int(clean_input)
        else:
            found = await self.project_service.db.get_project_by_name(
                interaction.guild_id, clean_input
            )
            if found is not None:
                project_id = found.id

        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{clean_input}`.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)
            return

        try:
            proj = await self.project_service.get_project(project_id)
            if not await self.project_service.can_change_status(interaction.user, proj):
                await interaction.response.send_message(
                    "❌ Only the project lead, core members, coordinators, or admins "
                    "can archive this project.",
                    ephemeral=True,
                )
                return

            if proj.is_archived:
                await interaction.response.send_message(
                    f"ℹ️ Project **{proj.name}** is already archived.",
                    ephemeral=True,
                )
                return

            if force:
                await interaction.response.defer()
                archived = await self.project_service.archive_project(
                    project_id=proj.id,
                    guild=interaction.guild,
                    caller=interaction.user,
                )
                embed = build_project_archived_embed(archived, interaction.user)
                await interaction.followup.send(
                    content="✅ **Project workspace has been archived.**",
                    embed=embed,
                )
            else:
                prompt_embed = error_embed(
                    title=f"⚠️ Archive Project Workspace: {proj.name}?",
                    description=(
                        f"Are you sure you want to archive **{proj.name}**?\n\n"
                        f"• All project channels will be changed to **read-only**.\n"
                        f"• Write permissions will be revoked for all members.\n"
                        f"• History and previous conversations will remain preserved."
                    ),
                )
                view = ArchiveConfirmationView(
                    project=proj,
                    caller=interaction.user,
                    project_service=self.project_service,
                )
                await interaction.response.send_message(
                    embed=prompt_embed,
                    view=view,
                    ephemeral=True,
                )

        except ProjectError as exc:
            err = error_embed(title="Archive Failed", description=str(exc))
            if interaction.response.is_done():
                await interaction.followup.send(embed=err, ephemeral=True)
            else:
                await interaction.response.send_message(embed=err, ephemeral=True)

    # ─── /project deadline ────────────────────────────────────────────────────

    @app_commands.command(
        name="deadline",
        description="View or set the target completion deadline for a project.",
    )
    @app_commands.describe(
        project="The project name or numeric ID.",
        deadline="New deadline (e.g. '2026-12-31', 'End of Q4', or 'clear' to unset).",
    )
    @app_commands.autocomplete(project=project_autocomplete)
    async def deadline(
        self,
        interaction: discord.Interaction,
        project: str,
        deadline: str | None = None,
    ) -> None:
        """View or update a project's completion deadline."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Project commands can only be used inside a Discord server.",
                ephemeral=True,
            )
            return

        clean_input = project.strip()
        project_id: int | None = None

        if clean_input.isdigit():
            project_id = int(clean_input)
        else:
            found = await self.project_service.db.get_project_by_name(
                interaction.guild_id, clean_input
            )
            if found is not None:
                project_id = found.id

        if project_id is None:
            err = error_embed(
                title="Project Not Found",
                description=f"Could not find project `{clean_input}`.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)
            return

        try:
            proj = await self.project_service.get_project(project_id)

            # Query mode: view current deadline
            if deadline is None:
                embed = build_project_deadline_embed(proj)
                await interaction.response.send_message(embed=embed)
                return

            # Update mode: requires authorization
            if not await self.project_service.can_change_status(interaction.user, proj):
                await interaction.response.send_message(
                    "❌ Only the project lead, core members, coordinators, or admins "
                    "can update project deadlines.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            updated = await self.project_service.set_project_deadline(
                guild=interaction.guild,
                project_id=proj.id,
                deadline=deadline,
                caller=interaction.user,
            )

            embed = build_project_deadline_embed(updated, updated_by=interaction.user)
            await interaction.followup.send(
                content="✅ **Project deadline updated!**",
                embed=embed,
            )

        except ProjectError as exc:
            err = error_embed(title="Deadline Update Failed", description=str(exc))
            if interaction.response.is_done():
                await interaction.followup.send(embed=err, ephemeral=True)
            else:
                await interaction.response.send_message(embed=err, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Projects cog into the bot."""
    await bot.add_cog(Projects(bot))

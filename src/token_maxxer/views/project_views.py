"""Project UI components — Modals, Embeds, and Views for Discord interactions.

Provides:
- ProjectCreateModal: Discord modal for creating new project workspaces.
- Embed builders for project cards, info details, project hub summaries, and lists.
"""

from __future__ import annotations

import contextlib

import discord

from token_maxxer.database.models import Project
from token_maxxer.services.project_service import (
    ProjectCreationError,
    ProjectDetails,
    ProjectService,
    ProjectValidationError,
)
from token_maxxer.utils.constants import CHANNEL_PROJECT_HUB, ProjectStatus
from token_maxxer.utils.helpers import error_embed, format_timestamp, make_embed, success_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)

STATUS_EMOJIS: dict[str, str] = {
    ProjectStatus.IDEA.value: "💡",
    ProjectStatus.ACTIVE.value: "🟢",
    ProjectStatus.COMPLETED.value: "✅",
    ProjectStatus.ARCHIVED.value: "📦",
}

STATUS_COLORS: dict[str, discord.Color] = {
    ProjectStatus.IDEA.value: discord.Color.gold(),
    ProjectStatus.ACTIVE.value: discord.Color.green(),
    ProjectStatus.COMPLETED.value: discord.Color.blue(),
    ProjectStatus.ARCHIVED.value: discord.Color.dark_grey(),
}


# ─── Embed Builders ───────────────────────────────────────────────────────────


def build_project_card_embed(
    project: Project,
    channels: dict[str, int] | None = None,
    member_count: int = 1,
) -> discord.Embed:
    """Build a rich Discord embed representing a project card."""
    status_emoji = STATUS_EMOJIS.get(project.status, "📁")
    color = STATUS_COLORS.get(project.status, discord.Color.blurple())

    embed = make_embed(
        title=f"🚀 {project.name}",
        description=project.description,
        color=color,
    )

    embed.add_field(
        name="Status",
        value=f"{status_emoji} **{project.status}**",
        inline=True,
    )
    embed.add_field(
        name="Project Lead",
        value=f"<@{project.lead_id}>",
        inline=True,
    )
    embed.add_field(
        name="Team",
        value=f"👥 {member_count} member{'s' if member_count != 1 else ''}",
        inline=True,
    )

    if project.tech_stack:
        embed.add_field(
            name="Tech Stack",
            value=f"`{project.tech_stack}`",
            inline=False,
        )

    if channels:
        chan_links = [
            f"• **{ch_type.capitalize()}**: <#{ch_id}>"
            for ch_type, ch_id in channels.items()
        ]
        embed.add_field(
            name="Workspace Channels",
            value="\n".join(chan_links),
            inline=False,
        )

    if project.created_at:
        embed.add_field(
            name="Created",
            value=format_timestamp(project.created_at, style="D"),
            inline=True,
        )

    embed.set_footer(text=f"Project ID: {project.id} • DSAI Club")
    return embed


def build_project_info_embed(details: ProjectDetails) -> discord.Embed:
    """Build a detailed project embed including team roster and recent updates."""
    embed = build_project_card_embed(
        project=details.project,
        channels=details.channels,
        member_count=len(details.members),
    )

    # Team members list
    if details.members:
        member_mentions: list[str] = []
        for m in details.members:
            role_badge = "👑 Lead" if m.is_lead else "👤 Member"
            member_mentions.append(f"<@{m.user_id}> ({role_badge})")
        embed.add_field(
            name=f"Team Members ({len(details.members)})",
            value=", ".join(member_mentions),
            inline=False,
        )

    # Recent updates
    if details.updates:
        update_lines: list[str] = []
        for upd in details.updates[:3]:
            ts = format_timestamp(upd.created_at, style="R") if upd.created_at else "Recently"
            parts = [f"**Update by <@{upd.author_id}>** ({ts}):"]
            if upd.completed:
                parts.append(f"• **Done:** {upd.completed}")
            if upd.working_on:
                parts.append(f"• **Working on:** {upd.working_on}")
            if upd.blocked_by:
                parts.append(f"• **Blocked by:** {upd.blocked_by}")
            update_lines.append("\n".join(parts))

        embed.add_field(
            name="Recent Updates",
            value="\n\n".join(update_lines),
            inline=False,
        )

    return embed


def build_project_list_embed(
    projects: list[Project],
    status_filter: str | None = None,
) -> discord.Embed:
    """Build an embed listing projects in the server."""
    filter_label = f" ({status_filter})" if status_filter else ""
    title = f"🚀 DSAI Club Projects{filter_label}"

    if not projects:
        return make_embed(
            title=title,
            description="No projects found matching your query.",
            color=discord.Color.light_grey(),
        )

    embed = make_embed(
        title=title,
        description=f"Showing **{len(projects)}** project(s):",
        color=discord.Color.blurple(),
    )

    for p in projects[:15]:
        emoji = STATUS_EMOJIS.get(p.status, "📁")
        stack = f" • `{p.tech_stack}`" if p.tech_stack else ""
        desc_snippet = (
            f"_{p.description[:80]}…_" if len(p.description) > 80 else f"_{p.description}_"
        )
        embed.add_field(
            name=f"{emoji} #{p.id} — {p.name}",
            value=(
                f"Lead: <@{p.lead_id}> • Status: **{p.status}**{stack}\n"
                f"{desc_snippet}"
            ),
            inline=False,
        )

    if len(projects) > 15:
        embed.set_footer(text=f"Showing 15 of {len(projects)} projects")
    else:
        embed.set_footer(text=f"Total Projects: {len(projects)} • DSAI Club")

    return embed


def build_project_hub_embed(projects: list[Project]) -> discord.Embed:
    """Build the pinned overview embed for the #project-hub channel."""
    embed = make_embed(
        title="📌 DSAI Club — Project Hub",
        description=(
            "Welcome to the **DSAI Club Project Hub**!\n"
            "Browse active projects below or create your own with `/project create`.\n\n"
            "All club members have read access to all projects — check them out, "
            "learn from the work, or request to join a team!"
        ),
        color=discord.Color.gold(),
    )

    active_projects = [p for p in projects if p.status == ProjectStatus.ACTIVE.value]
    idea_projects = [p for p in projects if p.status == ProjectStatus.IDEA.value]
    completed_projects = [p for p in projects if p.status == ProjectStatus.COMPLETED.value]

    if active_projects:
        active_lines = [
            f"• **{p.name}** (<@{p.lead_id}>) — _{p.description[:60]}_"
            for p in active_projects[:10]
        ]
        embed.add_field(
            name=f"🟢 Active Projects ({len(active_projects)})",
            value="\n".join(active_lines),
            inline=False,
        )

    if idea_projects:
        idea_lines = [
            f"• **{p.name}** (<@{p.lead_id}>)"
            for p in idea_projects[:5]
        ]
        embed.add_field(
            name=f"💡 Project Ideas ({len(idea_projects)})",
            value="\n".join(idea_lines),
            inline=False,
        )

    if completed_projects:
        completed_lines = [
            f"• **{p.name}** (<@{p.lead_id}>)"
            for p in completed_projects[:5]
        ]
        embed.add_field(
            name=f"✅ Completed Showcase ({len(completed_projects)})",
            value="\n".join(completed_lines),
            inline=False,
        )

    if not projects:
        embed.add_field(
            name="No Projects Yet",
            value="Be the first to launch a project! Use `/project create`.",
            inline=False,
        )

    embed.set_footer(text="Updated automatically • DSAI Club")
    return embed


# ─── Project Creation Modal ───────────────────────────────────────────────────


class ProjectCreateModal(discord.ui.Modal, title="Create Project Workspace"):
    """Discord Modal for submitting a new project workspace proposal."""

    project_name = discord.ui.TextInput(
        label="Project Name",
        placeholder="e.g. AI News Agent",
        min_length=2,
        max_length=50,
        required=True,
    )

    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="What is the goal and scope of this project?",
        min_length=5,
        max_length=500,
        required=True,
    )

    tech_stack = discord.ui.TextInput(
        label="Tech Stack (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g. Python, PyTorch, LangChain",
        max_length=100,
        required=False,
    )

    def __init__(self, project_service: ProjectService | None = None) -> None:
        super().__init__()
        self.project_service = project_service or ProjectService()

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission by provisioning the workspace."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Projects can only be created inside a Discord server.",
                ephemeral=True,
            )
            return

        # Defer immediately while workspace is being created
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        name = self.project_name.value.strip()
        desc = self.description.value.strip()
        stack = self.tech_stack.value.strip() or None

        try:
            workspace = await self.project_service.create_project(
                guild=guild,
                name=name,
                description=desc,
                lead=interaction.user,
                tech_stack=stack,
            )

            # Build channel mapping for response
            chan_ids = {ch_type: ch.id for ch_type, ch in workspace.channels.items()}

            response_embed = success_embed(
                title=f"Project Workspace Created: {name}",
                description=(
                    f"Your workspace is set up under **{workspace.category.name}**!\n\n"
                    f"• Lead: {interaction.user.mention}\n"
                    f"• Team chat: <#{chan_ids.get('team-chat')}>\n"
                    f"• Announcements: <#{chan_ids.get('announcements')}>\n"
                    f"• Tasks: <#{chan_ids.get('tasks')}>\n"
                    f"• Work: <#{chan_ids.get('work')}>\n\n"
                    "Use `/team add` to invite collaborators to your project team."
                ),
            )

            await interaction.followup.send(embed=response_embed, ephemeral=True)

            # Post project card to announcements or project hub
            await self._notify_project_hub(guild, workspace.project, chan_ids)

        except ProjectValidationError as exc:
            err = error_embed(title="Validation Error", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)
        except ProjectCreationError as exc:
            err = error_embed(title="Workspace Creation Error", description=str(exc))
            await interaction.followup.send(embed=err, ephemeral=True)
        except Exception as exc:
            log.exception("Unexpected error during project creation submission")
            err = error_embed(
                title="Creation Failed",
                description=f"An unexpected error occurred: `{exc}`",
            )
            await interaction.followup.send(embed=err, ephemeral=True)

    async def _notify_project_hub(
        self,
        guild: discord.Guild,
        project: Project,
        channels: dict[str, int],
    ) -> None:
        """Publish the new project card to #project-hub if it exists."""
        hub_channel = discord.utils.get(guild.text_channels, name=CHANNEL_PROJECT_HUB)
        if hub_channel is not None:
            card = build_project_card_embed(project, channels=channels, member_count=1)
            with contextlib.suppress(discord.HTTPException):
                msg_content = (
                    f"🎉 **New Project Launched!** <@{project.lead_id}> created "
                    f"**{project.name}**"
                )
                await hub_channel.send(content=msg_content, embed=card)
                log_action(
                    log,
                    action="post_to_project_hub",
                    result="success",
                    guild_id=guild.id,
                    project_id=project.id,
                )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Fallback error handler for modal interaction failures."""
        log.exception("Unhandled error in ProjectCreateModal for user %s", interaction.user.id)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred processing your project proposal.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ An error occurred processing your project proposal.",
                ephemeral=True,
            )

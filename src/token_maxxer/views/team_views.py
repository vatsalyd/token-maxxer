"""Team views and embed builders for token-maxxer.

Provides UI components and embed formatters for project team rosters.
"""

from __future__ import annotations

import discord

from token_maxxer.database.models import Project, ProjectMember
from token_maxxer.utils.helpers import format_timestamp, make_embed, success_embed


def build_team_list_embed(
    project: Project,
    members: list[ProjectMember],
) -> discord.Embed:
    """Build a rich embed displaying the current team roster for a project."""
    embed = make_embed(
        title=f"👥 Team Roster — {project.name}",
        description=(
            f"Active collaborators with write access to the **{project.name}** workspace."
        ),
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="Project Lead",
        value=f"👑 <@{project.lead_id}>",
        inline=False,
    )

    regular_members = [m for m in members if not m.is_lead]
    if regular_members:
        member_lines: list[str] = []
        for m in regular_members:
            ts = format_timestamp(m.joined_at, style="R") if m.joined_at else ""
            member_lines.append(f"• <@{m.user_id}> {f'(joined {ts})' if ts else ''}")

        embed.add_field(
            name=f"Team Members ({len(regular_members)})",
            value="\n".join(member_lines),
            inline=False,
        )
    else:
        embed.add_field(
            name="Team Members",
            value="_No additional members yet. Add collaborators with `/team add`._",
            inline=False,
        )

    embed.set_footer(text=f"Total Team Size: {len(members)} • Project #{project.id}")
    return embed


def build_member_added_embed(
    project: Project,
    member: discord.Member,
) -> discord.Embed:
    """Build a confirmation embed when a member is added to a project."""
    return success_embed(
        title="Member Added to Project",
        description=(
            f"✅ {member.mention} has been added to **{project.name}**!\n\n"
            "They now have write access to all channels in the project workspace."
        ),
    )


def build_member_removed_embed(
    project: Project,
    member: discord.Member,
) -> discord.Embed:
    """Build a confirmation embed when a member is removed from a project."""
    return success_embed(
        title="Member Removed from Project",
        description=(
            f"👋 {member.mention} has been removed from **{project.name}**.\n\n"
            "Their write access to workspace channels has been revoked. "
            "They retain read-only visitor access as a club member."
        ),
    )


def build_lead_transferred_embed(
    project: Project,
    new_lead: discord.Member,
) -> discord.Embed:
    """Build a confirmation embed when project leadership is transferred."""
    return success_embed(
        title="Project Leadership Transferred",
        description=(
            f"👑 Leadership of **{project.name}** has been transferred to {new_lead.mention}!\n\n"
            "They now have lead management authority over the project workspace."
        ),
    )

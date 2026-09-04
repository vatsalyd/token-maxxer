"""Constants and server structure definitions for token-maxxer.

This module contains all the static configuration for the DSAI Club server:
- Server structure (categories and channels)
- Role hierarchy and definitions
- Project workspace template
- Discord permission presets

No Discord API calls are made here — this is pure configuration data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import discord

# ─── Project Status ───────────────────────────────────────────────────────────


class ProjectStatus(StrEnum):
    """Project lifecycle status values."""

    IDEA = "IDEA"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ProjectMemberRole(StrEnum):
    """Roles a user can have within a project."""

    LEAD = "lead"
    MEMBER = "member"


# ─── Role Definitions ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """Definition of a Discord role to be created by the bot.

    Attributes:
        name: Display name of the role.
        color: Role color in Discord.
        hoist: Whether to display the role separately in the member list.
        mentionable: Whether the role can be mentioned by anyone.
        permissions: Discord permissions granted by this role.
    """

    name: str
    color: discord.Color
    hoist: bool = False
    mentionable: bool = False
    permissions: discord.Permissions = field(
        default_factory=discord.Permissions.none
    )


# Administrative / operational roles (ordered by hierarchy, highest first)
ADMIN_ROLES: list[RoleDefinition] = [
    RoleDefinition(
        name="👑 Club Admin",
        color=discord.Color.gold(),
        hoist=True,
        mentionable=True,
        permissions=discord.Permissions(
            administrator=False,
            manage_guild=True,
            manage_roles=True,
            manage_channels=True,
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            view_audit_log=True,
            mention_everyone=True,
        ),
    ),
    RoleDefinition(
        name="⚡ Coordinator",
        color=discord.Color.orange(),
        hoist=True,
        mentionable=True,
        permissions=discord.Permissions(
            manage_roles=True,
            manage_channels=True,
            manage_messages=True,
            kick_members=True,
            view_audit_log=True,
            mention_everyone=True,
        ),
    ),
    RoleDefinition(
        name="🔧 Core Member",
        color=discord.Color.blue(),
        hoist=True,
        mentionable=True,
        permissions=discord.Permissions(
            manage_messages=True,
            mention_everyone=True,
        ),
    ),
    RoleDefinition(
        name="🚀 Project Lead",
        color=discord.Color.green(),
        hoist=False,
        mentionable=True,
        permissions=discord.Permissions.none(),
    ),
    RoleDefinition(
        name="👤 Member",
        color=discord.Color.light_grey(),
        hoist=False,
        mentionable=False,
        permissions=discord.Permissions.none(),
    ),
]

# Interest / self-selectable roles (no admin permissions)
INTEREST_ROLES: list[RoleDefinition] = [
    RoleDefinition(name="🐍 Python", color=discord.Color.from_str("#3776AB")),
    RoleDefinition(name="🤖 Machine Learning", color=discord.Color.from_str("#FF6F00")),
    RoleDefinition(name="🧠 Deep Learning", color=discord.Color.from_str("#9C27B0")),
    RoleDefinition(name="✨ LLMs", color=discord.Color.from_str("#00BCD4")),
    RoleDefinition(name="🔗 AI Agents", color=discord.Color.from_str("#4CAF50")),
    RoleDefinition(name="📊 Data Science", color=discord.Color.from_str("#2196F3")),
    RoleDefinition(name="💻 Software Engineering", color=discord.Color.from_str("#607D8B")),
    RoleDefinition(name="🎨 Design", color=discord.Color.from_str("#E91E63")),
]

# All roles in hierarchy order (admin first, then interest)
ALL_ROLES: list[RoleDefinition] = ADMIN_ROLES + INTEREST_ROLES

# Quick-lookup sets for role names
ADMIN_ROLE_NAMES: set[str] = {r.name for r in ADMIN_ROLES}
INTEREST_ROLE_NAMES: set[str] = {r.name for r in INTEREST_ROLES}


# ─── Server Structure ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    """Definition of a Discord category and its channels.

    Attributes:
        name: Display name of the category.
        emoji: Emoji prefix for the category name.
        channels: List of channel names (with emoji prefixes).
        is_private: If True, the category is restricted to specific roles.
    """

    name: str
    emoji: str
    channels: list[str] = field(default_factory=list)
    is_private: bool = False

    @property
    def display_name(self) -> str:
        """Full display name including emoji."""
        return f"{self.emoji} {self.name}"


# Complete server structure as defined in the scaffold
SERVER_STRUCTURE: list[CategoryDefinition] = [
    CategoryDefinition(
        name="START HERE",
        emoji="🏠",
        channels=[
            "📜・rules",
            "👋・welcome",
            "🧭・server-guide",
            "🎭・roles",
        ],
    ),
    CategoryDefinition(
        name="CLUB",
        emoji="📢",
        channels=[
            "📢・announcements",
            "📅・events",
            "📝・meeting-notes",
            "📚・resources",
        ],
    ),
    CategoryDefinition(
        name="PROJECTS",
        emoji="🚀",
        channels=[
            "📌・project-hub",
            "💡・project-ideas",
            "🧩・team-formation",
            "💬・project-discussion",
            "🏆・project-showcase",
        ],
    ),
    CategoryDefinition(
        name="LEARNING",
        emoji="🧠",
        channels=[
            "💬・technical-discussion",
            "❓・help-desk",
            "👀・code-review",
            "📚・learning-resources",
        ],
    ),
    CategoryDefinition(
        name="COMMUNITY",
        emoji="💬",
        channels=[
            "💬・general",
            "😂・memes",
            "🎮・off-topic",
        ],
    ),
    CategoryDefinition(
        name="CORE TEAM",
        emoji="🔐",
        channels=[
            "💭・internal",
            "📋・planning",
            "📊・project-tracking",
            "📝・tasks",
        ],
        is_private=True,
    ),
]


# ─── Project Workspace Template ──────────────────────────────────────────────


# Default channels created for each new project workspace
PROJECT_WORKSPACE_CHANNELS: list[str] = [
    "📢・announcements",
    "💬・team-chat",
    "📋・tasks",
    "🧪・work",
]

# Template for the project category name
PROJECT_CATEGORY_TEMPLATE = "🚀 PROJECT — {name}"


# ─── Permission Presets ──────────────────────────────────────────────────────

# Roles that can use /setup
SETUP_ALLOWED_ROLES: set[str] = {
    "👑 Club Admin",
    "⚡ Coordinator",
}

# Roles that can create projects
PROJECT_CREATE_ALLOWED_ROLES: set[str] = {
    "👑 Club Admin",
    "⚡ Coordinator",
    "🔧 Core Member",
}

# Roles that can archive projects (beyond the project lead)
PROJECT_ADMIN_ROLES: set[str] = {
    "👑 Club Admin",
    "⚡ Coordinator",
    "🔧 Core Member",
}

# Roles that can manage teams (beyond the project lead)
TEAM_ADMIN_ROLES: set[str] = {
    "👑 Club Admin",
    "⚡ Coordinator",
    "🔧 Core Member",
}

# Roles that can view the CORE TEAM category
CORE_TEAM_VISIBLE_ROLES: set[str] = {
    "👑 Club Admin",
    "⚡ Coordinator",
    "🔧 Core Member",
}

# ─── Channel Type Constants ──────────────────────────────────────────────────

# Used in the project_channels table
PROJECT_CHANNEL_TYPES: dict[str, str] = {
    "📢・announcements": "announcements",
    "💬・team-chat": "team-chat",
    "📋・tasks": "tasks",
    "🧪・work": "work",
}

# Special channel names referenced by the bot
CHANNEL_PROJECT_HUB = "📌・project-hub"
CHANNEL_PROJECT_IDEAS = "💡・project-ideas"
CHANNEL_PROJECT_SHOWCASE = "🏆・project-showcase"

# Channels where regular members can only view/read (cannot send messages)
READONLY_CHANNELS: set[str] = {
    "📜・rules",
    "👋・welcome",
    "🧭・server-guide",
    "🎭・roles",
    "📢・announcements",
    "📌・project-hub",
}

# Role name constants for easy reference
ROLE_ADMIN = "👑 Club Admin"
ROLE_COORDINATOR = "⚡ Coordinator"
ROLE_CORE_MEMBER = "🔧 Core Member"
ROLE_PROJECT_LEAD = "🚀 Project Lead"
ROLE_MEMBER = "👤 Member"


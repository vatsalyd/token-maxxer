"""Guide service for token-maxxer.

Provides structured, authoritative bot documentation and developer reference
embeds for the private #🤖・bot-guide channel inside the CORE TEAM category.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord

from token_maxxer import __version__
from token_maxxer.utils.constants import (
    CHANNEL_BOT_GUIDE,
    CHANNEL_PROJECT_DISCUSSIONS,
    CHANNEL_PROJECT_HUB,
    INTEREST_ROLES,
    ROLE_ADMIN,
    ROLE_ALUMNI,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
    ROLE_PROJECT_LEAD,
)
from token_maxxer.utils.helpers import make_embed
from token_maxxer.utils.logging import get_logger, log_action

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class GuideService:
    """Service generating and publishing the private Core Team bot guide."""

    def __init__(self, bot: discord.Client | None = None) -> None:
        self.bot = bot

    # ─── Embed Builders ───────────────────────────────────────────────────────

    def build_overview_embed(self) -> discord.Embed:
        """Section 1: Bot overview, architecture, and design philosophy."""
        embed = make_embed(
            title="📖 Core Team Manual — Bot Overview & Architecture",
            description=(
                f"**token-maxxer `v{__version__}`** is the internal workspace engine for the DSAI Club.\n\n"
                "This guide is **strictly private** to Core Members, Coordinators, and Club Admins. "
                "It documents how the bot operates, how permissions and project workspaces work, "
                "and how to extend the codebase as we build new club tools."
            ),
            color=discord.Color.from_str("#3F51B5"),
        )

        embed.add_field(
            name="1. 🏛️ Architectural Foundation",
            value=(
                "• **Framework**: `discord.py 2.x` using asynchronous gateway & application commands.\n"
                "• **Persistence**: `SQLite` with foreign-key cascades via `aiosqlite`.\n"
                "• **Layered Separation**:\n"
                "  - `cogs/`: Slash command interactions & autocomplete handlers.\n"
                "  - `services/`: Business logic, reconciliation, & validation rules.\n"
                "  - `database/`: Data models & async parameterized SQLite queries.\n"
                "  - `views/`: Discord UI modals, buttons, and persistent select menus."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 🔐 Core Security Principle: Least Privilege",
            value=(
                "The bot provisions roles and permissions following strict least-privilege:\n"
                "• **Public Discovery**: Regular members can read all channels and project workspaces.\n"
                "• **Restricted Writing**: Only designated project members can post in project channels.\n"
                "• **Private Leadership**: The `🔐 CORE TEAM` category is invisible to non-core members."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 1 of 7")
        return embed

    def build_governance_embed(self) -> discord.Embed:
        """Section 2: Server provisioning, hierarchy, and reconciliation."""
        embed = make_embed(
            title="🏗️ Server Provisioning & Governance (`/setup`)",
            description=(
                "The `/setup` command is an **idempotent infrastructure reconciler**. "
                "It inspects the entire server, verifies expected structures, and fixes any drifts."
            ),
            color=discord.Color.from_str("#009688"),
        )

        embed.add_field(
            name="1. 👑 Role Hierarchy Precedence",
            value=(
                f"1. `token-maxxer` *(Must be positioned above managed roles)*\n"
                f"2. `{ROLE_ADMIN}` *(Club Presidents & Lead Organizers)*\n"
                f"3. `{ROLE_COORDINATOR}` *(Operational Coordinators)*\n"
                f"4. `{ROLE_CORE_MEMBER}` *(Active Core Team Members)*\n"
                f"5. `{ROLE_PROJECT_LEAD}` *(Assigned dynamically to project leads)*\n"
                f"6. `{ROLE_ALUMNI}` *(Club alumni & graduate mentors)*\n"
                f"7. `{ROLE_MEMBER}` *(Standard club members)*\n"
                f"8. *Interest Roles* (8 domain focus roles)"
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 🔄 How Reconciliation Works",
            value=(
                "• **Verify-Only Mode**: `/setup verify_only:True` checks structure without writing changes.\n"
                "• **Role Reconciliation**: Creates missing roles with accurate color, hoist, and permissions.\n"
                "• **Category & Channel Sync**: Moves misplaced channels and creates missing ones.\n"
                "• **Permission Lockdown**: Re-applies read-only rules to `START HERE` and hides `CORE TEAM`."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 2 of 7")
        return embed

    def build_onboarding_guide_embed(self) -> discord.Embed:
        """Section 3: Onboarding system and member welcoming."""
        embed = make_embed(
            title="👋 Onboarding & Community Workflows (`/onboard`)",
            description=(
                "The onboarding system ensures every newcomer is welcomed and oriented immediately."
            ),
            color=discord.Color.from_str("#00BCD4"),
        )

        embed.add_field(
            name="1. ⚡ Automated Member Joins (`on_member_join`)",
            value=(
                f"When a new student joins the Discord server:\n"
                f"• The bot automatically grants `{ROLE_MEMBER}` so they have base access.\n"
                f"• Sends a personalized welcome embed into `#👋・welcome` tagging them and linking next steps."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 🎭 Interactive Role Picker (`#🎭・roles`)",
            value=(
                "• Uses a persistent `RoleSelectionView` (`timeout=None`) that stays live across reboots.\n"
                f"• Allows members to toggle any of the {len(INTEREST_ROLES)} tech-interest roles:\n"
                f"  {', '.join(r.name for r in INTEREST_ROLES)}.\n"
                "• Includes **Claim Member Role** and **Claim Alumni Role** self-service buttons.\n"
                "• Introduces the `#🎓・alumni-network` channel for student-graduate networking."
            ),
            inline=False,
        )

        embed.add_field(
            name="3. 📝 Updating Onboarding Content",
            value=(
                "To refresh rules or welcome text:\n"
                "1. Edit definitions in `services/onboarding_service.py`.\n"
                "2. Run `/onboard setup` in Discord — old bot embeds will be cleanly replaced without duplicates."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 3 of 7")
        return embed

    def build_projects_guide_embed(self) -> discord.Embed:
        """Section 4: Project workspace management and lifecycle."""
        embed = make_embed(
            title="🚀 Project Workspace Lifecycle (`/project`)",
            description=(
                "Project workspaces turn Discord into an active incubator for student research and engineering."
            ),
            color=discord.Color.from_str("#FF9800"),
        )

        embed.add_field(
            name="1. 🌟 Launching a Project (`/project create`)",
            value=(
                "• Restricted to Core Members, Coordinators, and Admins.\n"
                "• Opens an interactive creation modal (Name, Description, Tech Stack, Deadline).\n"
                "• Staged creation automatically creates:\n"
                "  - Category: `🚀 PROJECT: <NAME>`\n"
                "  - Channels: `📢・announcements`, `💬・team-chat`, `📋・tasks`, `🧪・work`\n"
                f"  - Broadcasts announcement card in `{CHANNEL_PROJECT_HUB}`.\n"
                "• SQLite stores channel IDs, lead user ID, and project metadata."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 📊 Lifecycle States & Milestones",
            value=(
                "• **`IDEA`** 💡: Conceptual phase in `#💡・project-ideas`.\n"
                "• **`ACTIVE`** 🟢: Workspace provisioned, active development in progress.\n"
                "• **`COMPLETED`** ✅: Deliverables finished, showcased in `#🏆・project-showcase`.\n"
                "• **`ARCHIVED`** 📦: `/project archive <name>` freezes channels to read-only for archival.\n"
                "• **Progress Updates**: `/project update <name>` broadcasts structured milestone reports."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 4 of 7")
        return embed

    def build_teams_guide_embed(self) -> discord.Embed:
        """Section 5: Team management and permission mechanics."""
        embed = make_embed(
            title="👥 Team Management & Permissions (`/team`)",
            description=(
                "How collaborators are onboarded to projects and how channel write access works."
            ),
            color=discord.Color.from_str("#E91E63"),
        )

        embed.add_field(
            name="1. 🔑 Dynamic Permission Overwrites",
            value=(
                "• Regular members have `view_channel=True` but `send_messages=False` on project channels.\n"
                "• Running `/team add <project> <@member>`:\n"
                "  1. Adds a record to the `project_members` SQLite table.\n"
                "  2. Applies an explicit channel overwrite granting `send_messages=True`, `attach_files=True`, "
                "and `create_public_threads=True`.\n"
                "• Running `/team remove <project> <@member>` deletes the overwrite, cleanly reverting access."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 👑 Lead Authority & Delegation",
            value=(
                "• The Project Lead has authority to add/remove members, post updates, and set deadlines.\n"
                "• Core Members, Coordinators, and Admins can manage any team as server moderators.\n"
                "• `/team transfer-lead <project> <@new_lead>` reassigns the project lead in Discord and DB."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 5 of 7")
        return embed

    def build_developer_embed(self) -> discord.Embed:
        """Section 6: Developer guide for extending the bot."""
        embed = make_embed(
            title="🛠️ Core Developer Guide — Adding New Features",
            description=(
                "Step-by-step instructions for Core Team engineers adding new capabilities to token-maxxer."
            ),
            color=discord.Color.from_str("#673AB7"),
        )

        embed.add_field(
            name="1. 📦 Adding a New Command / Cog",
            value=(
                "1. Create `src/token_maxxer/cogs/my_feature.py`.\n"
                "2. Define `class MyFeature(commands.Cog)` or `commands.GroupCog`.\n"
                "3. Decorate commands with authorization checks (e.g. `@is_core_or_higher()`).\n"
                "4. Add an `async def setup(bot: commands.Bot)` function.\n"
                "5. Register extension path in `bot.py`'s `cog_extensions` list."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. ⚙️ Adding a New Service",
            value=(
                "• Keep Discord callbacks thin by moving business logic into `services/`.\n"
                "• Export your service in `src/token_maxxer/services/__init__.py`.\n"
                "• Use structured logging via `log_action(log, action=..., result=...)`."
            ),
            inline=False,
        )

        embed.add_field(
            name="3. 🗄️ Database Changes",
            value=(
                "• Add tables/indexes to `src/token_maxxer/database/schema.sql`.\n"
                "• Define dataclass representations in `database/models.py`.\n"
                "• Add async queries in `database/db.py` using parameterized queries (`?`)."
            ),
            inline=False,
        )

        embed.add_field(
            name="4. 🧪 Unit Tests",
            value=(
                "• Every feature must have tests in `tests/`.\n"
                "• Run full test suite with: `pytest -v`.\n"
                "• Mocks for Discord Guild, Channels, and Members are available in `tests/conftest.py`."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 6 of 7")
        return embed

    def build_troubleshooting_embed(self) -> discord.Embed:
        """Section 7: Troubleshooting, incident response, and gotchas."""
        embed = make_embed(
            title="🚨 Troubleshooting & Incident Response",
            description="Common issues, gotchas, and how to resolve them quickly.",
            color=discord.Color.from_str("#F44336"),
        )

        embed.add_field(
            name="1. ⚠️ '403 Forbidden: Missing Permissions'",
            value=(
                "• **Role Hierarchy**: The `token-maxxer` bot role must be positioned above the roles it manages. "
                "Open Server Settings -> Roles and drag `token-maxxer` near the top.\n"
                "• **Channel Overwrites**: The bot cannot set permissions it lacks at the guild level."
            ),
            inline=False,
        )

        embed.add_field(
            name="2. 🔄 Recovery Commands",
            value=(
                "• **Repair All Channels & Roles**: `/setup` (re-syncs permissions without deleting data).\n"
                "• **Audit Discrepancies**: `/setup verify_only:True` (reports missing or misordered items).\n"
                "• **Refresh Onboarding Channels**: `/onboard setup` (re-posts rules, welcome, and role picker).\n"
                "• **Re-publish Bot Guide**: `/guide publish` (re-posts this guide in `#🤖・bot-guide`)."
            ),
            inline=False,
        )

        embed.add_field(
            name="3. 🖥️ Windows & Unicode Notes",
            value=(
                "Windows terminals default to `cp1252`. Always ensure `sys.stdout.reconfigure(encoding='utf-8')` "
                "is enabled when logging emojis in console scripts."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club Core Team • Section 7 of 7")
        return embed

    # ─── Multi-Section Retrieval ───────────────────────────────────────────────

    def get_section_embed(self, section_key: str) -> discord.Embed:
        """Retrieve a specific guide embed by key name."""
        mapping = {
            "overview": self.build_overview_embed,
            "governance": self.build_governance_embed,
            "onboarding": self.build_onboarding_guide_embed,
            "projects": self.build_projects_guide_embed,
            "teams": self.build_teams_guide_embed,
            "developer": self.build_developer_embed,
            "troubleshooting": self.build_troubleshooting_embed,
        }
        builder = mapping.get(section_key.lower())
        if builder is None:
            raise KeyError(f"Unknown section '{section_key}'. Valid sections: {list(mapping.keys())}")
        return builder()

    def get_all_sections(self) -> list[tuple[str, discord.Embed]]:
        """Return all guide sections in logical reading order."""
        return [
            ("overview", self.build_overview_embed()),
            ("governance", self.build_governance_embed()),
            ("onboarding", self.build_onboarding_guide_embed()),
            ("projects", self.build_projects_guide_embed()),
            ("teams", self.build_teams_guide_embed()),
            ("developer", self.build_developer_embed()),
            ("troubleshooting", self.build_troubleshooting_embed()),
        ]

    # ─── Channel Publishing ───────────────────────────────────────────────────

    async def publish_bot_guide(self, guild: discord.Guild) -> tuple[bool, str]:
        """Purge and publish the complete Core Team manual into #🤖・bot-guide.

        Returns:
            A tuple of ``(success, status_message)``.
        """
        guide_channel = discord.utils.get(guild.text_channels, name=CHANNEL_BOT_GUIDE)
        if guide_channel is None:
            return False, f"Channel `{CHANNEL_BOT_GUIDE}` not found. Run `/setup` first."

        try:
            # Clean up old bot messages
            async for msg in guide_channel.history(limit=50):
                if msg.author.id == (self.bot.user.id if self.bot and self.bot.user else None):
                    with contextlib.suppress(discord.HTTPException):
                        await msg.delete()

            # Publish all guide sections in order
            sections = self.get_all_sections()
            for _, embed in sections:
                await guide_channel.send(embed=embed)

            log_action(
                log,
                action="publish_bot_guide",
                result="success",
                guild_id=guild.id,
                channel=guide_channel.name,
                sections=len(sections),
            )
            return True, f"Successfully published {len(sections)} guide sections to {guide_channel.mention}!"

        except discord.Forbidden:
            log.warning("Permission denied publishing to %s", guide_channel.name)
            return False, f"Permission denied writing to {guide_channel.mention}."
        except discord.HTTPException as exc:
            log.warning("HTTP error publishing to %s: %s", guide_channel.name, exc)
            return False, f"HTTP error writing to {guide_channel.mention}: {exc}"

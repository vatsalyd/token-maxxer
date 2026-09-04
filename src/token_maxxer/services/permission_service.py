"""Permission service for token-maxxer.

Central permission management for the DSAI Club server:
- Public channel permissions (standard & read-only)
- Core Team private category permissions
- Project workspace permissions (members can write, all can read)
- Granting and revoking project team member access

Provides reusable permission overwrite maps to avoid duplicate permission
logic across cogs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from token_maxxer.utils.constants import (
    READONLY_CHANNELS,
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
    ROLE_PROJECT_LEAD,
)
from token_maxxer.utils.logging import get_logger, log_action

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class PermissionService:
    """Service for configuring Discord permission overwrites centrally.

    Ensures that permission rules strictly adhere to the least-privilege
    philosophy documented in the project scaffold:
    - Standard members can read all project workspaces but not write.
    - Project team members can send messages, attach files, and create threads.
    - Project leads can additionally manage threads.
    - Core Team category is strictly hidden from general members.
    """

    def __init__(self, bot: discord.Client | None = None) -> None:
        self.bot = bot

    def _get_role(self, guild: discord.Guild, name: str) -> discord.Role | None:
        """Find a role by exact name or normalized name."""
        norm_name = name.strip().lower()
        for role in guild.roles:
            if role.name == name or role.name.strip().lower() == norm_name:
                return role
        return None

    def _get_bot_member(self, guild: discord.Guild) -> discord.Member | None:
        """Return the bot's Member object in the guild."""
        return guild.me

    # ─── Overwrite Builders ───────────────────────────────────────────────────

    def get_bot_overwrite(self) -> discord.PermissionOverwrite:
        """Permissions granted to the bot itself on managed channels."""
        return discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            manage_messages=True,
            manage_channels=True,
        )

    def get_project_member_overwrite(self) -> discord.PermissionOverwrite:
        """Permissions granted to an active project team member."""
        return discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            create_public_threads=True,
            send_messages_in_threads=True,
            add_reactions=True,
        )

    def get_project_lead_overwrite(self) -> discord.PermissionOverwrite:
        """Permissions granted to a project lead."""
        return discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            create_public_threads=True,
            send_messages_in_threads=True,
            add_reactions=True,
            manage_threads=True,
        )

    def build_readonly_public_overwrites(
        self,
        guild: discord.Guild,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Build overwrites for public read-only channels (e.g. rules, announcements).

        Regular members can view, read history, and react, but cannot post messages.
        Core team and coordinators can post and manage messages.
        """
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

        # Bot overwrite
        bot_member = self._get_bot_member(guild)
        if bot_member:
            overwrites[bot_member] = self.get_bot_overwrite()

        # @everyone: view and read only
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,
            add_reactions=True,
        )

        # Member role: view and read only
        member_role = self._get_role(guild, ROLE_MEMBER)
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                create_public_threads=False,
                create_private_threads=False,
                send_messages_in_threads=False,
                add_reactions=True,
            )

        # Core Member: can post and manage
        core_role = self._get_role(guild, ROLE_CORE_MEMBER)
        if core_role:
            overwrites[core_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            )

        # Coordinator: can post and manage
        coord_role = self._get_role(guild, ROLE_COORDINATOR)
        if coord_role:
            overwrites[coord_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            )

        # Club Admin: can post and manage
        admin_role = self._get_role(guild, ROLE_ADMIN)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            )

        return overwrites

    def build_standard_public_overwrites(
        self,
        guild: discord.Guild,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Build overwrites for general public channels (e.g. community, discussion)."""
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

        bot_member = self._get_bot_member(guild)
        if bot_member:
            overwrites[bot_member] = self.get_bot_overwrite()

        # @everyone: normal participation
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            create_public_threads=True,
            send_messages_in_threads=True,
        )

        return overwrites

    def build_core_team_overwrites(
        self,
        guild: discord.Guild,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Build overwrites for the private CORE TEAM category and its channels.

        Hidden from @everyone, Member, and Project Lead roles.
        Only visible to Core Member, Coordinator, and Club Admin.
        """
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

        bot_member = self._get_bot_member(guild)
        if bot_member:
            overwrites[bot_member] = self.get_bot_overwrite()

        # @everyone: hidden
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=False,
        )

        # Member role: hidden
        member_role = self._get_role(guild, ROLE_MEMBER)
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=False,
            )

        # Project Lead role: hidden (unless they hold Core Member or above)
        lead_role = self._get_role(guild, ROLE_PROJECT_LEAD)
        if lead_role:
            overwrites[lead_role] = discord.PermissionOverwrite(
                view_channel=False,
            )

        # Core Member: full access
        core_role = self._get_role(guild, ROLE_CORE_MEMBER)
        if core_role:
            overwrites[core_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
                create_public_threads=True,
                create_private_threads=True,
                send_messages_in_threads=True,
            )

        # Coordinator: full access + channel management
        coord_role = self._get_role(guild, ROLE_COORDINATOR)
        if coord_role:
            overwrites[coord_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
                manage_channels=True,
                create_public_threads=True,
                create_private_threads=True,
                send_messages_in_threads=True,
            )

        # Club Admin: full access
        admin_role = self._get_role(guild, ROLE_ADMIN)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
                manage_channels=True,
                create_public_threads=True,
                create_private_threads=True,
                send_messages_in_threads=True,
            )

        return overwrites

    def build_project_workspace_overwrites(
        self,
        guild: discord.Guild,
        lead: discord.Member | None = None,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Build base overwrites for a dynamic project workspace category or channel.

        All members can view and read history, but only project members and leaders
        have write access.
        """
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}

        bot_member = self._get_bot_member(guild)
        if bot_member:
            overwrites[bot_member] = self.get_bot_overwrite()

        # @everyone: view and read only, no posting
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
            create_public_threads=False,
            create_private_threads=False,
            send_messages_in_threads=False,
            add_reactions=True,
        )

        # Member role: view and read only
        member_role = self._get_role(guild, ROLE_MEMBER)
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                create_public_threads=False,
                create_private_threads=False,
                send_messages_in_threads=False,
                add_reactions=True,
            )

        # Core Member: can post and assist
        core_role = self._get_role(guild, ROLE_CORE_MEMBER)
        if core_role:
            overwrites[core_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            )

        # Coordinator: can post and manage
        coord_role = self._get_role(guild, ROLE_COORDINATOR)
        if coord_role:
            overwrites[coord_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_channels=True,
            )

        # Club Admin: can post and manage
        admin_role = self._get_role(guild, ROLE_ADMIN)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_channels=True,
            )

        # Project lead overwrite if provided
        if lead is not None:
            overwrites[lead] = self.get_project_lead_overwrite()

        return overwrites

    # ─── Permission Application Methods ───────────────────────────────────────

    async def apply_public_permissions(
        self,
        channel: discord.abc.GuildChannel,
        readonly: bool = False,
    ) -> None:
        """Apply public permission overwrites to a channel or category.

        Args:
            channel: The channel or category to configure.
            readonly: If True, channel will be view-only for general members.
        """
        overwrites = (
            self.build_readonly_public_overwrites(channel.guild)
            if readonly
            else self.build_standard_public_overwrites(channel.guild)
        )
        await channel.edit(
            overwrites=overwrites,
            reason="token-maxxer apply public permissions",
        )
        log_action(
            log,
            action="apply_public_permissions",
            result="success",
            guild_id=channel.guild.id,
            channel=channel.name,
            readonly=readonly,
        )

    async def apply_core_permissions(
        self,
        channel: discord.abc.GuildChannel,
    ) -> None:
        """Apply private permissions to a Core Team channel or category.

        Args:
            channel: The channel or category to restrict.
        """
        overwrites = self.build_core_team_overwrites(channel.guild)
        await channel.edit(
            overwrites=overwrites,
            reason="token-maxxer apply core team permissions",
        )
        log_action(
            log,
            action="apply_core_permissions",
            result="success",
            guild_id=channel.guild.id,
            channel=channel.name,
        )

    async def apply_project_permissions(
        self,
        channel: discord.abc.GuildChannel,
        lead: discord.Member | None = None,
    ) -> None:
        """Apply base project workspace permissions.

        Args:
            channel: The project category or channel.
            lead: Optional project lead member to grant lead permissions.
        """
        overwrites = self.build_project_workspace_overwrites(channel.guild, lead=lead)
        await channel.edit(
            overwrites=overwrites,
            reason="token-maxxer apply project permissions",
        )
        log_action(
            log,
            action="apply_project_permissions",
            result="success",
            guild_id=channel.guild.id,
            channel=channel.name,
            lead_id=lead.id if lead else None,
        )

    async def grant_project_member_access(
        self,
        target: discord.abc.GuildChannel,
        member: discord.Member,
        is_lead: bool = False,
    ) -> None:
        """Grant a member write access to a project channel or category.

        Args:
            target: The project CategoryChannel or TextChannel.
            member: The Discord member to grant access to.
            is_lead: If True, grants lead permissions including thread management.
        """
        overwrite = (
            self.get_project_lead_overwrite() if is_lead else self.get_project_member_overwrite()
        )
        await target.set_permissions(
            member,
            overwrite=overwrite,
            reason=f"token-maxxer grant project access (lead={is_lead})",
        )
        log_action(
            log,
            action="grant_project_member_access",
            result="success",
            guild_id=target.guild.id,
            channel=target.name,
            user_id=member.id,
            is_lead=is_lead,
        )

    async def revoke_project_member_access(
        self,
        target: discord.abc.GuildChannel,
        member: discord.Member,
    ) -> None:
        """Revoke a member's explicit write permissions from a project channel or category.

        The member will revert to viewing/reading the channel via the Member role.

        Args:
            target: The project CategoryChannel or TextChannel.
            member: The Discord member to revoke write access from.
        """
        await target.set_permissions(
            member,
            overwrite=None,
            reason="token-maxxer revoke project access",
        )
        log_action(
            log,
            action="revoke_project_member_access",
            result="success",
            guild_id=target.guild.id,
            channel=target.name,
            user_id=member.id,
        )

    async def reconcile_guild_permissions(
        self,
        guild: discord.Guild,
    ) -> tuple[int, list[str]]:
        """Reconcile permissions across all permanent categories and channels.

        Applies Core Team permissions to private areas and appropriate public
        permissions (standard vs read-only) to all other channels.

        Args:
            guild: The Discord guild.

        Returns:
            A tuple of ``(reconciled_count, errors)``.
        """
        reconciled_count = 0
        errors: list[str] = []

        # 1. Reconcile categories
        for category in guild.categories:
            cat_norm = category.name.strip().lower()
            try:
                if "core team" in cat_norm:
                    await self.apply_core_permissions(category)
                    reconciled_count += 1
                elif "start here" in cat_norm:
                    await self.apply_public_permissions(category, readonly=True)
                    reconciled_count += 1
            except discord.Forbidden:
                err = f"Permission denied configuring category '{category.name}'"
                log_action(
                    log,
                    action="reconcile_guild_permissions",
                    result="forbidden",
                    guild_id=guild.id,
                    channel=category.name,
                    level=logging.ERROR,
                )
                errors.append(err)
            except discord.HTTPException as exc:
                err = f"HTTP error configuring category '{category.name}': {exc.text}"
                errors.append(err)

        # 2. Reconcile text channels
        for channel in guild.text_channels:
            parent_name = channel.category.name.strip().lower() if channel.category else ""
            try:
                if "core team" in parent_name:
                    await self.apply_core_permissions(channel)
                    reconciled_count += 1
                elif channel.name in READONLY_CHANNELS or "start here" in parent_name:
                    await self.apply_public_permissions(channel, readonly=True)
                    reconciled_count += 1
                elif not parent_name.startswith("🚀 project"):
                    # Regular public channel
                    await self.apply_public_permissions(channel, readonly=False)
                    reconciled_count += 1
            except discord.Forbidden:
                err = f"Permission denied configuring channel '{channel.name}'"
                log_action(
                    log,
                    action="reconcile_guild_permissions",
                    result="forbidden",
                    guild_id=guild.id,
                    channel=channel.name,
                    level=logging.ERROR,
                )
                errors.append(err)
            except discord.HTTPException as exc:
                err = f"HTTP error configuring channel '{channel.name}': {exc.text}"
                errors.append(err)

        return reconciled_count, errors

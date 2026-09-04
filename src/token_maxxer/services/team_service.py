"""Team service for token-maxxer.

Handles project team roster operations:
- Adding and removing team members
- Granting and revoking channel write permissions
- Transferring project leadership
- Validating caller authorization for team actions
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord

from token_maxxer.database import (
    Database,
    Project,
    ProjectMember,
)
from token_maxxer.database import (
    db as global_db,
)
from token_maxxer.services.permission_service import PermissionService
from token_maxxer.utils.constants import (
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ProjectMemberRole,
)
from token_maxxer.utils.logging import get_logger, log_action

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


# ─── Exceptions ───────────────────────────────────────────────────────────────


class TeamError(Exception):
    """Base exception for team management errors."""


class TeamValidationError(TeamError):
    """Raised when team operation input is invalid."""


class TeamAuthorizationError(TeamError):
    """Raised when caller lacks authority to modify the project team."""


# ─── Team Service ─────────────────────────────────────────────────────────────


class TeamService:
    """Business logic service for managing project teams and channel access."""

    def __init__(
        self,
        bot: discord.Client | None = None,
        database: Database | None = None,
        permission_service: PermissionService | None = None,
    ) -> None:
        self.bot = bot
        self._db = database
        self.permission_service = permission_service or PermissionService(bot)

    @property
    def db(self) -> Database:
        """Return the database client instance."""
        if self._db is not None:
            return self._db
        return global_db  # type: ignore[return-value]

    # ─── Authorization ────────────────────────────────────────────────────────

    def can_manage_team(self, caller: discord.Member, project: Project) -> bool:
        """Check if caller has permission to manage the team for this project.

        Allowed if caller is:
        - The project lead
        - Server owner
        - Has Administrator permission
        - Has Core Member, Coordinator, or Club Admin role
        """
        if caller.id == project.lead_id:
            return True

        if caller.id == caller.guild.owner_id or caller.guild_permissions.administrator:
            return True

        admin_role_names = {
            ROLE_ADMIN.strip().lower(),
            ROLE_COORDINATOR.strip().lower(),
            ROLE_CORE_MEMBER.strip().lower(),
        }
        user_roles = {r.name.strip().lower() for r in caller.roles}
        return bool(user_roles & admin_role_names)

    def verify_caller_authorization(self, caller: discord.Member, project: Project) -> None:
        """Raise TeamAuthorizationError if caller is not authorized."""
        if not self.can_manage_team(caller, project):
            raise TeamAuthorizationError(
                f"You do not have permission to manage the team for project '{project.name}'. "
                "Only the project lead, core members, coordinators, and admins can manage teams."
            )

    # ─── Member Operations ────────────────────────────────────────────────────

    async def add_member(
        self,
        guild: discord.Guild,
        project_id: int,
        member: discord.Member,
        role: str = ProjectMemberRole.MEMBER.value,
    ) -> ProjectMember:
        """Add a member to a project and grant them channel write permissions.

        Args:
            guild: The Discord guild.
            project_id: Project ID.
            member: Discord member to add.
            role: Project role ('lead' or 'member').

        Returns:
            The created or updated ProjectMember model.

        Raises:
            TeamValidationError: If member is already in the project.
        """
        project = await self.db.get_project(project_id)
        if project is None:
            raise TeamValidationError(f"Project #{project_id} does not exist.")

        # Check if already a member
        if await self.db.is_member(project_id, member.id):
            raise TeamValidationError(
                f"{member.mention} is already a member of **{project.name}**."
            )

        # 1. Update database
        pm = await self.db.add_member(project_id, member.id, role=role)

        # 2. Grant permissions on Discord category & channels
        if project.category_id is not None:
            category = guild.get_channel(project.category_id)
            if isinstance(category, discord.CategoryChannel):
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    await self.permission_service.grant_project_member_access(
                        category,
                        member,
                        is_lead=(role == ProjectMemberRole.LEAD.value),
                    )

                # Also ensure write permissions on all text channels under category
                for ch in category.text_channels:
                    with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                        await self.permission_service.grant_project_member_access(
                            ch,
                            member,
                            is_lead=(role == ProjectMemberRole.LEAD.value),
                        )

        log_action(
            log,
            action="add_project_member",
            result="success",
            guild_id=guild.id,
            project_id=project_id,
            user_id=member.id,
            role=role,
        )

        return pm

    async def remove_member(
        self,
        guild: discord.Guild,
        project_id: int,
        member: discord.Member,
    ) -> bool:
        """Remove a member from a project and revoke their write access.

        Args:
            guild: The Discord guild.
            project_id: Project ID.
            member: Discord member to remove.

        Returns:
            True if removed successfully.

        Raises:
            TeamValidationError: If user is not in the project or is the lead.
        """
        project = await self.db.get_project(project_id)
        if project is None:
            raise TeamValidationError(f"Project #{project_id} does not exist.")

        if member.id == project.lead_id:
            raise TeamValidationError(
                f"Cannot remove {member.mention} because they are the project lead. "
                "Transfer leadership using `/team transfer-lead` first."
            )

        if not await self.db.is_member(project_id, member.id):
            raise TeamValidationError(
                f"{member.mention} is not a member of **{project.name}**."
            )

        # 1. Remove from database
        await self.db.remove_member(project_id, member.id)

        # 2. Revoke write permissions from category and channels
        if project.category_id is not None:
            category = guild.get_channel(project.category_id)
            if isinstance(category, discord.CategoryChannel):
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    await self.permission_service.revoke_project_member_access(category, member)

                for ch in category.text_channels:
                    with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                        await self.permission_service.revoke_project_member_access(ch, member)

        log_action(
            log,
            action="remove_project_member",
            result="success",
            guild_id=guild.id,
            project_id=project_id,
            user_id=member.id,
        )

        return True

    async def transfer_lead(
        self,
        guild: discord.Guild,
        project_id: int,
        new_lead: discord.Member,
    ) -> Project:
        """Transfer project leadership to another Discord member.

        Args:
            guild: The Discord guild.
            project_id: Project ID.
            new_lead: The new leader member.

        Returns:
            The updated Project model.

        Raises:
            TeamValidationError: If project doesn't exist or new lead is already lead.
        """
        project = await self.db.get_project(project_id)
        if project is None:
            raise TeamValidationError(f"Project #{project_id} does not exist.")

        if new_lead.id == project.lead_id:
            raise TeamValidationError(
                f"{new_lead.mention} is already the leader of **{project.name}**."
            )

        old_lead_id = project.lead_id

        # 1. Update database
        await self.db.update_project_lead(project_id, new_lead.id)
        project.lead_id = new_lead.id

        # 2. Adjust Discord channel permissions
        if project.category_id is not None:
            category = guild.get_channel(project.category_id)
            if isinstance(category, discord.CategoryChannel):
                # Grant new lead thread management & write access
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    await self.permission_service.grant_project_member_access(
                        category, new_lead, is_lead=True
                    )

                for ch in category.text_channels:
                    with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                        await self.permission_service.grant_project_member_access(
                            ch, new_lead, is_lead=True
                        )

                # Demote old lead permissions to standard project member
                old_lead = guild.get_member(old_lead_id)
                if old_lead is not None:
                    with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                        await self.permission_service.grant_project_member_access(
                            category, old_lead, is_lead=False
                        )
                    for ch in category.text_channels:
                        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                            await self.permission_service.grant_project_member_access(
                                ch, old_lead, is_lead=False
                            )

        log_action(
            log,
            action="transfer_project_lead",
            result="success",
            guild_id=guild.id,
            project_id=project_id,
            old_lead=old_lead_id,
            new_lead=new_lead.id,
        )

        return project

    async def list_members(self, project_id: int) -> list[ProjectMember]:
        """Fetch all members registered for a project."""
        return await self.db.get_members(project_id)

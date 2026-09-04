"""Project service for token-maxxer.

Encapsulates all business logic for project lifecycle management:
- Staged workspace provisioning (DB -> Discord resources -> permissions -> sync)
- Transaction rollback/cleanup on Discord API failures
- Status transitions and archive workflows
- Project discovery and detail retrieval
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

from token_maxxer.database import (
    Database,
    Project,
    ProjectMember,
    ProjectUpdate,
)
from token_maxxer.database import (
    db as global_db,
)
from token_maxxer.services.permission_service import PermissionService
from token_maxxer.utils.constants import (
    PROJECT_CATEGORY_TEMPLATE,
    PROJECT_CHANNEL_TYPES,
    PROJECT_WORKSPACE_CHANNELS,
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ProjectStatus,
)
from token_maxxer.utils.helpers import utcnow_iso
from token_maxxer.utils.logging import get_logger, log_action

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


# ─── Exceptions ───────────────────────────────────────────────────────────────


class ProjectError(Exception):
    """Base exception for all project-related errors."""


class ProjectValidationError(ProjectError):
    """Raised when project input validation fails."""


class ProjectCreationError(ProjectError):
    """Raised when staged Discord workspace creation encounters an error."""


class ProjectNotFoundError(ProjectError):
    """Raised when a requested project cannot be found."""


# ─── Data Transfer Objects ───────────────────────────────────────────────────


@dataclass
class ProjectWorkspace:
    """Represents the Discord resources created for a project workspace.

    Attributes:
        project: The persisted Project model instance.
        category: The Discord CategoryChannel.
        channels: Mapping of channel type name (e.g. 'announcements') to TextChannel.
    """

    project: Project
    category: discord.CategoryChannel
    channels: dict[str, discord.TextChannel] = field(default_factory=dict)


@dataclass
class ProjectDetails:
    """Aggregated information about a project including members, channels, and updates."""

    project: Project
    members: list[ProjectMember]
    channels: dict[str, int]
    updates: list[ProjectUpdate]


# ─── Project Service ──────────────────────────────────────────────────────────


class ProjectService:
    """Business logic service for managing projects."""

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

    # ─── Validation ───────────────────────────────────────────────────────────

    async def validate_new_project(
        self,
        guild_id: int,
        name: str,
        description: str,
    ) -> None:
        """Validate input parameters for a new project.

        Raises:
            ProjectValidationError: If validation rules are violated.
        """
        clean_name = name.strip()
        if len(clean_name) < 2 or len(clean_name) > 50:
            raise ProjectValidationError(
                "Project name must be between 2 and 50 characters long."
            )

        clean_desc = description.strip()
        if len(clean_desc) < 5 or len(clean_desc) > 500:
            raise ProjectValidationError(
                "Project description must be between 5 and 500 characters long."
            )

        # Check for name collision in guild
        existing = await self.db.get_project_by_name(guild_id, clean_name)
        if existing is not None and existing.is_active:
            raise ProjectValidationError(
                f"An active project named '{clean_name}' already exists in this server."
            )

    # ─── Workspace Creation Flow ──────────────────────────────────────────────

    async def create_project(
        self,
        *,
        guild: discord.Guild,
        name: str,
        description: str,
        lead: discord.Member,
        tech_stack: str | None = None,
    ) -> ProjectWorkspace:
        """Create a new project workspace with staged transactional rollback.

        Flow:
        1. Validate inputs and name uniqueness.
        2. Create database record in SQLite.
        3. Create Discord CategoryChannel with project permission overwrites.
        4. Create Discord TextChannels for workspace under category.
        5. Persist CategoryChannel ID and TextChannel IDs to SQLite.
        6. Return complete ProjectWorkspace.

        If any Discord operation fails, created channels and categories are
        cleaned up to avoid leaving orphaned resources in the guild.

        Args:
            guild: The Discord guild where the workspace will live.
            name: Project name.
            description: Project description.
            lead: The project lead Discord Member.
            tech_stack: Technologies or frameworks used.

        Returns:
            A ``ProjectWorkspace`` containing the project record and Discord objects.

        Raises:
            ProjectValidationError: If inputs are invalid or name conflicts.
            ProjectCreationError: If Discord channel or category creation fails.
        """
        clean_name = name.strip()
        clean_desc = description.strip()
        clean_stack = tech_stack.strip() if tech_stack else None

        await self.validate_new_project(guild.id, clean_name, clean_desc)

        log_action(
            log,
            action="create_project_start",
            guild_id=guild.id,
            user_id=lead.id,
            name=clean_name,
        )

        # Step 1: Create DB project record
        project = await self.db.create_project(
            guild_id=guild.id,
            name=clean_name,
            description=clean_desc,
            lead_id=lead.id,
            tech_stack=clean_stack,
            status=ProjectStatus.ACTIVE.value,
        )

        created_channels: list[discord.TextChannel] = []
        created_category: discord.CategoryChannel | None = None

        try:
            # Step 2: Create category with project overwrites
            category_name = PROJECT_CATEGORY_TEMPLATE.format(name=clean_name.upper())
            overwrites = self.permission_service.build_project_workspace_overwrites(
                guild, lead=lead
            )

            created_category = await guild.create_category(
                name=category_name,
                overwrites=overwrites,
                reason=f"token-maxxer project workspace for {clean_name}",
            )

            # Update DB with category ID
            await self.db.update_project_category(project.id, created_category.id)
            project.category_id = created_category.id

            # Step 3: Create channels under category
            channel_map: dict[str, discord.TextChannel] = {}

            for ch_name in PROJECT_WORKSPACE_CHANNELS:
                channel = await guild.create_text_channel(
                    name=ch_name,
                    category=created_category,
                    topic=f"{clean_name} • {clean_desc[:200]}",
                    reason=f"token-maxxer project workspace channel for {clean_name}",
                )
                created_channels.append(channel)

                # Channel type key (e.g. 'announcements', 'team-chat')
                ch_type = PROJECT_CHANNEL_TYPES.get(ch_name, ch_name)
                channel_map[ch_type] = channel

                # Persist channel mapping in SQLite
                await self.db.set_channel(project.id, ch_type, channel.id)

            log_action(
                log,
                action="create_project_success",
                result="success",
                guild_id=guild.id,
                user_id=lead.id,
                project_id=project.id,
                category_id=created_category.id,
                channels_count=len(created_channels),
            )

            return ProjectWorkspace(
                project=project,
                category=created_category,
                channels=channel_map,
            )

        except Exception as exc:
            # Rollback: Clean up any Discord resources created during failed attempt
            log.exception(
                "Discord workspace creation failed for project %s (ID %s). Rolling back resources.",
                clean_name,
                project.id,
            )
            for ch in created_channels:
                with contextlib.suppress(discord.HTTPException):
                    await ch.delete(reason="token-maxxer rollback failed project creation")

            if created_category is not None:
                with contextlib.suppress(discord.HTTPException):
                    await created_category.delete(
                        reason="token-maxxer rollback failed project creation"
                    )

            # Mark project status as ARCHIVED/failed in database
            await self.db.update_project_status(project.id, ProjectStatus.ARCHIVED.value)

            log_action(
                log,
                action="create_project_rollback",
                result="rolled_back",
                guild_id=guild.id,
                project_id=project.id,
                error=str(exc),
                level=logging.ERROR,
            )

            raise ProjectCreationError(
                f"Failed to create Discord workspace for '{clean_name}': {exc}"
            ) from exc

    # ─── Querying ─────────────────────────────────────────────────────────────

    async def get_project(self, project_id: int) -> Project:
        """Retrieve a project by ID or raise ProjectNotFoundError."""
        project = await self.db.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project #{project_id} does not exist.")
        return project

    async def get_project_by_name(self, guild_id: int, name: str) -> Project:
        """Retrieve a project by name or raise ProjectNotFoundError."""
        project = await self.db.get_project_by_name(guild_id, name)
        if project is None:
            raise ProjectNotFoundError(f"Project '{name}' does not exist.")
        return project

    async def list_projects(
        self,
        guild_id: int,
        status: ProjectStatus | str | None = None,
    ) -> list[Project]:
        """List projects for a guild, optionally filtered by status."""
        status_val = status.value if isinstance(status, ProjectStatus) else status
        return await self.db.list_projects(guild_id, status=status_val)

    async def get_project_details(self, project_id: int) -> ProjectDetails:
        """Fetch aggregated details for a project."""
        project = await self.get_project(project_id)
        members = await self.db.get_members(project_id)
        channels = await self.db.get_channels(project_id)
        updates = await self.db.get_updates(project_id, limit=5)

        return ProjectDetails(
            project=project,
            members=members,
            channels=channels,
            updates=updates,
        )

    # ─── Lifecycle & Status Transitions ───────────────────────────────────────

    async def update_project_status(
        self,
        project_id: int,
        new_status: ProjectStatus | str,
    ) -> Project:
        """Update a project's status in SQLite.

        Args:
            project_id: The project ID.
            new_status: Desired ProjectStatus.

        Returns:
            The updated Project model.
        """
        project = await self.get_project(project_id)
        status_str = new_status.value if isinstance(new_status, ProjectStatus) else new_status

        archived_at = utcnow_iso() if status_str == ProjectStatus.ARCHIVED.value else None
        await self.db.update_project_status(project_id, status_str, archived_at=archived_at)

        project.status = status_str
        project.archived_at = archived_at

        log_action(
            log,
            action="update_project_status",
            result="success",
            project_id=project_id,
            status=status_str,
        )

        return project

    async def archive_project(
        self,
        project_id: int,
        guild: discord.Guild | None = None,
    ) -> Project:
        """Archive a project and preserve workspace history.

        Marks the database status as ARCHIVED and optionally restricts channel writes.

        Args:
            project_id: The project ID to archive.
            guild: Optional Discord guild to update category/channel permissions.

        Returns:
            The archived Project model.
        """
        project = await self.update_project_status(project_id, ProjectStatus.ARCHIVED)

        # If guild is provided and category exists, restrict write permissions
        if guild is not None and project.category_id is not None:
            category = guild.get_channel(project.category_id)
            if isinstance(category, discord.CategoryChannel):
                try:
                    # Update category name with archive prefix
                    archive_name = f"📦 ARCHIVED — {project.name.upper()}"
                    await category.edit(name=archive_name, reason="token-maxxer project archived")

                    # Revoke write permissions from all project channels
                    for ch in category.text_channels:
                        await self.permission_service.apply_public_permissions(
                            ch, readonly=True
                        )
                except (discord.Forbidden, discord.HTTPException):
                    log.warning(
                        "Failed to update category permissions for archived project %s",
                        project.id,
                    )

        return project

    async def complete_project(self, project_id: int) -> Project:
        """Mark a project as COMPLETED."""
        return await self.update_project_status(project_id, ProjectStatus.COMPLETED)

    # ─── Update & Status Flow ─────────────────────────────────────────────────

    async def can_post_update(self, caller: discord.Member, project_id: int) -> bool:
        """Check if caller has authorization to submit an update for the project."""
        project = await self.get_project(project_id)
        if caller.id == project.lead_id or caller.id == caller.guild.owner_id:
            return True
        if caller.guild_permissions.administrator:
            return True
        admin_roles = {
            ROLE_ADMIN.strip().lower(),
            ROLE_COORDINATOR.strip().lower(),
            ROLE_CORE_MEMBER.strip().lower(),
        }
        user_roles = {r.name.strip().lower() for r in caller.roles}
        if bool(user_roles & admin_roles):
            return True
        return await self.db.is_member(project_id, caller.id)

    async def can_change_status(self, caller: discord.Member, project: Project) -> bool:
        """Check if caller has authorization to update project status."""
        if caller.id == project.lead_id or caller.id == caller.guild.owner_id:
            return True
        if caller.guild_permissions.administrator:
            return True
        admin_roles = {
            ROLE_ADMIN.strip().lower(),
            ROLE_COORDINATOR.strip().lower(),
            ROLE_CORE_MEMBER.strip().lower(),
        }
        user_roles = {r.name.strip().lower() for r in caller.roles}
        return bool(user_roles & admin_roles)

    async def post_project_update(
        self,
        *,
        guild: discord.Guild,
        project_id: int,
        author: discord.Member,
        completed: str | None = None,
        working_on: str | None = None,
        blocked_by: str | None = None,
        next_steps: str | None = None,
    ) -> ProjectUpdate:
        """Record and broadcast a project progress update.

        Args:
            guild: Discord guild.
            project_id: Project ID.
            author: Discord member submitting the update.
            completed: Completed accomplishments.
            working_on: Current tasks.
            blocked_by: Obstacles/blockers.
            next_steps: Planned next actions.

        Returns:
            The recorded ProjectUpdate.

        Raises:
            ProjectError: If author lacks authorization or project doesn't exist.
        """
        if not await self.can_post_update(author, project_id):
            raise ProjectError(
                "You must be an active member or leader of this project to submit updates."
            )

        project = await self.get_project(project_id)

        update = await self.db.add_update(
            project_id=project_id,
            author_id=author.id,
            completed=completed,
            working_on=working_on,
            blocked_by=blocked_by,
            next_steps=next_steps,
        )

        # Notify project channel if available
        channels = await self.db.get_channels(project_id)
        target_channel_id = channels.get("announcements") or channels.get("team-chat")
        if target_channel_id is not None:
            target_channel = guild.get_channel(target_channel_id)
            if isinstance(target_channel, discord.TextChannel):
                with contextlib.suppress(discord.HTTPException):
                    content = (
                        f"📣 **New update posted for {project.name} by {author.mention}!**"
                    )
                    await target_channel.send(content=content)

        log_action(
            log,
            action="post_project_update",
            result="success",
            guild_id=guild.id,
            project_id=project_id,
            user_id=author.id,
            update_id=update.id,
        )

        return update

    async def change_project_status(
        self,
        guild: discord.Guild,
        project_id: int,
        new_status: ProjectStatus | str,
        caller: discord.Member,
    ) -> Project:
        """Change a project's status with authorization validation.

        Args:
            guild: Discord guild.
            project_id: Project ID.
            new_status: The target ProjectStatus.
            caller: Discord member initiating the change.

        Returns:
            The updated Project model.

        Raises:
            ProjectError: If caller is not authorized.
        """
        project = await self.get_project(project_id)
        if not await self.can_change_status(caller, project):
            raise ProjectError(
                "Only the project lead, core members, coordinators, and admins "
                "can change project status."
            )

        status_str = new_status.value if isinstance(new_status, ProjectStatus) else new_status

        if status_str == ProjectStatus.ARCHIVED.value:
            return await self.archive_project(project_id, guild=guild)

        return await self.update_project_status(project_id, new_status)


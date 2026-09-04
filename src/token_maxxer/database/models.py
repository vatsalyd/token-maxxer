"""Data models for token-maxxer SQLite persistence.

Type-safe dataclasses mapping directly to SQLite tables.
"""

from __future__ import annotations

from dataclasses import dataclass

from token_maxxer.utils.constants import ProjectMemberRole, ProjectStatus


@dataclass(slots=True)
class Project:
    """Represents a project stored in the database.

    Attributes:
        id: Primary key project ID.
        guild_id: Discord guild ID.
        name: Project display name.
        description: Brief project purpose/summary.
        tech_stack: Technologies/frameworks used.
        lead_id: Discord user ID of the project leader.
        status: Lifecycle status (IDEA, ACTIVE, COMPLETED, ARCHIVED).
        category_id: Discord CategoryChannel ID if provisioned.
        created_at: ISO 8601 UTC timestamp when created.
        archived_at: ISO 8601 UTC timestamp when archived, if applicable.
    """

    id: int
    guild_id: int
    name: str
    description: str
    tech_stack: str | None
    lead_id: int
    status: str = ProjectStatus.ACTIVE.value
    category_id: int | None = None
    created_at: str = ""
    archived_at: str | None = None

    @property
    def is_active(self) -> bool:
        """Whether the project is currently in an active state."""
        return self.status == ProjectStatus.ACTIVE.value

    @property
    def is_archived(self) -> bool:
        """Whether the project is archived."""
        return self.status == ProjectStatus.ARCHIVED.value

    @property
    def is_completed(self) -> bool:
        """Whether the project is completed."""
        return self.status == ProjectStatus.COMPLETED.value


@dataclass(slots=True)
class ProjectMember:
    """Represents a member assigned to a project.

    Attributes:
        id: Primary key record ID.
        project_id: Foreign key to projects.id.
        user_id: Discord user ID.
        role: Member role ("lead" or "member").
        joined_at: ISO 8601 UTC timestamp.
    """

    id: int
    project_id: int
    user_id: int
    role: str = ProjectMemberRole.MEMBER.value
    joined_at: str = ""

    @property
    def is_lead(self) -> bool:
        """Whether this member is a project lead."""
        return self.role == ProjectMemberRole.LEAD.value


@dataclass(slots=True)
class ProjectChannel:
    """Represents a channel created for a project workspace.

    Attributes:
        id: Primary key record ID.
        project_id: Foreign key to projects.id.
        channel_type: Type identifier (e.g. announcements, team-chat).
        channel_id: Discord TextChannel ID.
    """

    id: int
    project_id: int
    channel_type: str
    channel_id: int


@dataclass(slots=True)
class ProjectUpdate:
    """Represents a weekly or milestone project update.

    Attributes:
        id: Primary key record ID.
        project_id: Foreign key to projects.id.
        author_id: Discord user ID of update author.
        completed: Work accomplished recently.
        working_on: Current tasks in progress.
        blocked_by: Current blockers or challenges.
        next_steps: Upcoming planned tasks.
        created_at: ISO 8601 UTC timestamp.
    """

    id: int
    project_id: int
    author_id: int
    completed: str | None = None
    working_on: str | None = None
    blocked_by: str | None = None
    next_steps: str | None = None
    created_at: str = ""

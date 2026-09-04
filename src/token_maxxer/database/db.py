"""Async SQLite database manager for token-maxxer.

Provides connection pooling, schema initialization, and typed CRUD operations
using aiosqlite.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

from token_maxxer.database.models import (
    Project,
    ProjectChannel,
    ProjectMember,
    ProjectUpdate,
)
from token_maxxer.utils.constants import ProjectMemberRole, ProjectStatus
from token_maxxer.utils.helpers import utcnow_iso
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            from token_maxxer.config.settings import settings

            self.db_path = settings.database_path
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database schema and enable foreign keys."""
        if self._initialized:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.executescript(schema_sql)
            with contextlib.suppress(Exception):
                await conn.execute("ALTER TABLE projects ADD COLUMN deadline TEXT;")
            await conn.commit()

        self._initialized = True
        log.info("Database initialized at %s", self.db_path)

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Context manager providing an active database connection with row factory."""
        if not self._initialized:
            await self.initialize()

        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            await conn.close()

    # ─── Projects CRUD ────────────────────────────────────────────────────────

    async def create_project(
        self,
        *,
        guild_id: int,
        name: str,
        description: str,
        lead_id: int,
        tech_stack: str | None = None,
        status: str = ProjectStatus.ACTIVE.value,
        category_id: int | None = None,
        deadline: str | None = None,
    ) -> Project:
        """Insert a new project and add the lead as a member."""
        created_at = utcnow_iso()
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO projects (
                    guild_id, name, description, tech_stack,
                    lead_id, status, category_id, created_at, deadline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    name,
                    description,
                    tech_stack,
                    lead_id,
                    status,
                    category_id,
                    created_at,
                    deadline,
                ),
            )
            project_id = cursor.lastrowid
            assert project_id is not None

            # Add creator as lead in project_members
            await conn.execute(
                """
                INSERT INTO project_members (project_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, lead_id, ProjectMemberRole.LEAD.value, created_at),
            )

            await conn.commit()

        log_action(
            log,
            action="create_project_db",
            result="success",
            guild_id=guild_id,
            user_id=lead_id,
            project_id=project_id,
            name=name,
        )

        return Project(
            id=project_id,
            guild_id=guild_id,
            name=name,
            description=description,
            tech_stack=tech_stack,
            lead_id=lead_id,
            status=status,
            category_id=category_id,
            created_at=created_at,
            deadline=deadline,
        )

    async def get_project(self, project_id: int) -> Project | None:
        """Fetch a project by its primary key ID."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_project(row)

    async def get_project_by_name(self, guild_id: int, name: str) -> Project | None:
        """Fetch a project by case-insensitive name within a guild."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM projects WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
                (guild_id, name.strip()),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_project(row)

    async def list_projects(
        self,
        guild_id: int,
        status: str | None = None,
    ) -> list[Project]:
        """List all projects for a guild, optionally filtered by status."""
        query = "SELECT * FROM projects WHERE guild_id = ?"
        params: list[object] = [guild_id]

        if status is not None:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY id DESC"

        async with self.connect() as conn:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [self._row_to_project(r) for r in rows]

    async def update_project_status(
        self,
        project_id: int,
        status: str,
        archived_at: str | None = None,
    ) -> bool:
        """Update a project's lifecycle status."""
        if status == ProjectStatus.ARCHIVED.value and archived_at is None:
            archived_at = utcnow_iso()

        async with self.connect() as conn:
            cursor = await conn.execute(
                "UPDATE projects SET status = ?, archived_at = ? WHERE id = ?",
                (status, archived_at, project_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def update_project_deadline(
        self, project_id: int, deadline: str | None
    ) -> bool:
        """Update a project's target deadline."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "UPDATE projects SET deadline = ? WHERE id = ?",
                (deadline, project_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def update_project_category(self, project_id: int, category_id: int) -> bool:
        """Update the Discord category ID for a project workspace."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "UPDATE projects SET category_id = ? WHERE id = ?",
                (category_id, project_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def update_project_lead(self, project_id: int, new_lead_id: int) -> bool:
        """Transfer project leadership to another user."""
        async with self.connect() as conn:
            # 1. Update project table
            cursor = await conn.execute(
                "UPDATE projects SET lead_id = ? WHERE id = ?",
                (new_lead_id, project_id),
            )
            if cursor.rowcount == 0:
                return False

            # 2. Demote old lead to member
            await conn.execute(
                """
                UPDATE project_members
                SET role = ?
                WHERE project_id = ? AND role = ?
                """,
                (
                    ProjectMemberRole.MEMBER.value,
                    project_id,
                    ProjectMemberRole.LEAD.value,
                ),
            )

            # 3. Promote or insert new lead
            now = utcnow_iso()
            await conn.execute(
                """
                INSERT INTO project_members (project_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET role = ?
                """,
                (
                    project_id,
                    new_lead_id,
                    ProjectMemberRole.LEAD.value,
                    now,
                    ProjectMemberRole.LEAD.value,
                ),
            )

            await conn.commit()
            return True

    # ─── Project Members CRUD ─────────────────────────────────────────────────

    async def add_member(
        self,
        project_id: int,
        user_id: int,
        role: str = ProjectMemberRole.MEMBER.value,
    ) -> ProjectMember:
        """Add or update a project member."""
        joined_at = utcnow_iso()
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO project_members (project_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET role = excluded.role
                RETURNING id, project_id, user_id, role, joined_at
                """,
                (project_id, user_id, role, joined_at),
            )
            row = await cursor.fetchone()
            await conn.commit()
            assert row is not None
            return ProjectMember(
                id=row["id"],
                project_id=row["project_id"],
                user_id=row["user_id"],
                role=row["role"],
                joined_at=row["joined_at"],
            )

    async def remove_member(self, project_id: int, user_id: int) -> bool:
        """Remove a member from a project."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_members(self, project_id: int) -> list[ProjectMember]:
        """List all members for a project."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM project_members WHERE project_id = ? ORDER BY id ASC",
                (project_id,),
            )
            rows = await cursor.fetchall()
            return [
                ProjectMember(
                    id=r["id"],
                    project_id=r["project_id"],
                    user_id=r["user_id"],
                    role=r["role"],
                    joined_at=r["joined_at"],
                )
                for r in rows
            ]

    async def get_member(self, project_id: int, user_id: int) -> ProjectMember | None:
        """Fetch a specific member record."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ProjectMember(
                id=row["id"],
                project_id=row["project_id"],
                user_id=row["user_id"],
                role=row["role"],
                joined_at=row["joined_at"],
            )

    async def is_member(self, project_id: int, user_id: int) -> bool:
        """Check if a user is a member of the project."""
        return (await self.get_member(project_id, user_id)) is not None

    async def get_user_projects(self, guild_id: int, user_id: int) -> list[Project]:
        """Fetch all projects that a user belongs to in a guild."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT p.* FROM projects p
                INNER JOIN project_members pm ON p.id = pm.project_id
                WHERE p.guild_id = ? AND pm.user_id = ?
                ORDER BY p.id DESC
                """,
                (guild_id, user_id),
            )
            rows = await cursor.fetchall()
            return [self._row_to_project(r) for r in rows]

    # ─── Project Channels CRUD ────────────────────────────────────────────────

    async def set_channel(
        self,
        project_id: int,
        channel_type: str,
        channel_id: int,
    ) -> ProjectChannel:
        """Record a channel associated with a project."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO project_channels (project_id, channel_type, channel_id)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id, channel_type) DO UPDATE SET channel_id = excluded.channel_id
                RETURNING id, project_id, channel_type, channel_id
                """,
                (project_id, channel_type, channel_id),
            )
            row = await cursor.fetchone()
            await conn.commit()
            assert row is not None
            return ProjectChannel(
                id=row["id"],
                project_id=row["project_id"],
                channel_type=row["channel_type"],
                channel_id=row["channel_id"],
            )

    async def get_channels(self, project_id: int) -> dict[str, int]:
        """Return a mapping of channel_type -> channel_id for a project."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                "SELECT channel_type, channel_id FROM project_channels WHERE project_id = ?",
                (project_id,),
            )
            rows = await cursor.fetchall()
            return {r["channel_type"]: r["channel_id"] for r in rows}

    async def get_project_by_channel_id(self, channel_id: int) -> Project | None:
        """Look up a project associated with a specific TextChannel ID."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT p.* FROM projects p
                INNER JOIN project_channels pc ON p.id = pc.project_id
                WHERE pc.channel_id = ?
                """,
                (channel_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_project(row)

    # ─── Project Updates CRUD ─────────────────────────────────────────────────

    async def add_update(
        self,
        *,
        project_id: int,
        author_id: int,
        completed: str | None = None,
        working_on: str | None = None,
        blocked_by: str | None = None,
        next_steps: str | None = None,
    ) -> ProjectUpdate:
        """Record a progress update for a project."""
        created_at = utcnow_iso()
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO project_updates (
                    project_id, author_id, completed, working_on,
                    blocked_by, next_steps, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id, project_id, author_id, completed,
                          working_on, blocked_by, next_steps, created_at
                """,
                (
                    project_id,
                    author_id,
                    completed,
                    working_on,
                    blocked_by,
                    next_steps,
                    created_at,
                ),
            )
            row = await cursor.fetchone()
            await conn.commit()
            assert row is not None
            return ProjectUpdate(
                id=row["id"],
                project_id=row["project_id"],
                author_id=row["author_id"],
                completed=row["completed"],
                working_on=row["working_on"],
                blocked_by=row["blocked_by"],
                next_steps=row["next_steps"],
                created_at=row["created_at"],
            )

    async def get_updates(self, project_id: int, limit: int = 5) -> list[ProjectUpdate]:
        """Return the most recent updates for a project."""
        async with self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM project_updates
                WHERE project_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                ProjectUpdate(
                    id=r["id"],
                    project_id=r["project_id"],
                    author_id=r["author_id"],
                    completed=r["completed"],
                    working_on=r["working_on"],
                    blocked_by=r["blocked_by"],
                    next_steps=r["next_steps"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _row_to_project(row: aiosqlite.Row) -> Project:
        deadline: str | None = None
        with contextlib.suppress(KeyError, IndexError):
            deadline = row["deadline"]
        return Project(
            id=row["id"],
            guild_id=row["guild_id"],
            name=row["name"],
            description=row["description"],
            tech_stack=row["tech_stack"],
            lead_id=row["lead_id"],
            status=row["status"],
            category_id=row["category_id"],
            created_at=row["created_at"],
            archived_at=row["archived_at"],
            deadline=deadline,
        )


_db_instance: Database | None = None


def get_db() -> Database:
    """Get or create the global Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


class _DatabaseProxy:
    """Proxy providing lazy access to the global Database singleton."""

    def __getattr__(self, name: str) -> object:
        return getattr(get_db(), name)


# Global lazy database instance
db = _DatabaseProxy()  # type: ignore[assignment]


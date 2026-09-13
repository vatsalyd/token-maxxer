"""Unit tests for SQLite database layer and typed models."""

import pytest

from token_maxxer.database.db import Database
from token_maxxer.utils.constants import ProjectMemberRole, ProjectStatus


@pytest.mark.asyncio
async def test_database_initialization(temp_db: Database) -> None:
    """Ensure database initializes idempotently and tables exist."""
    await temp_db.initialize()
    async with temp_db.connect() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row["name"] for row in await cursor.fetchall()]
        assert "projects" in tables
        assert "project_members" in tables
        assert "project_channels" in tables
        assert "project_updates" in tables


@pytest.mark.asyncio
async def test_project_crud(temp_db: Database) -> None:
    """Test creating, reading, updating, and listing projects."""
    guild_id = 123456789
    lead_id = 987654321

    # 1. Create project
    proj = await temp_db.create_project(
        guild_id=guild_id,
        name="Auto-Pilot AI",
        description="Autonomous flight navigation assistant.",
        tech_stack="PyTorch, ROS",
        lead_id=lead_id,
        deadline="2026-11-15",
    )
    assert proj.id > 0
    assert proj.name == "Auto-Pilot AI"
    assert proj.status == ProjectStatus.ACTIVE.value
    assert proj.deadline == "2026-11-15"
    assert proj.is_active is True
    assert proj.is_archived is False

    # 2. Verify lead was added to project_members
    members = await temp_db.get_members(proj.id)
    assert len(members) == 1
    assert members[0].user_id == lead_id
    assert members[0].is_lead is True

    # 3. Read by ID and by name
    fetched = await temp_db.get_project(proj.id)
    assert fetched is not None
    assert fetched.name == "Auto-Pilot AI"

    fetched_by_name = await temp_db.get_project_by_name(guild_id, "auto-pilot ai")
    assert fetched_by_name is not None
    assert fetched_by_name.id == proj.id

    # 4. Update deadline
    updated_deadline = await temp_db.update_project_deadline(proj.id, "2026-12-01")
    assert updated_deadline is True
    proj_with_deadline = await temp_db.get_project(proj.id)
    assert proj_with_deadline is not None
    assert proj_with_deadline.deadline == "2026-12-01"

    # 5. Update status
    updated_status = await temp_db.update_project_status(
        proj.id, ProjectStatus.ARCHIVED.value
    )
    assert updated_status is True
    archived_proj = await temp_db.get_project(proj.id)
    assert archived_proj is not None
    assert archived_proj.is_archived is True
    assert archived_proj.archived_at is not None

    # 6. Listing and filtering
    active_projects = await temp_db.list_projects(guild_id, status=ProjectStatus.ACTIVE.value)
    assert len(active_projects) == 0

    archived_projects = await temp_db.list_projects(
        guild_id, status=ProjectStatus.ARCHIVED.value
    )
    assert len(archived_projects) == 1


@pytest.mark.asyncio
async def test_project_members_management(temp_db: Database) -> None:
    """Test adding, listing, and removing team members."""
    proj = await temp_db.create_project(
        guild_id=1,
        name="Team Test Project",
        description="Testing roster manipulation",
        lead_id=1001,
    )

    # Add second member
    member2 = await temp_db.add_member(
        project_id=proj.id,
        user_id=1002,
        role=ProjectMemberRole.MEMBER.value,
    )
    assert member2.user_id == 1002
    assert member2.role == ProjectMemberRole.MEMBER.value
    assert await temp_db.is_member(proj.id, 1002) is True

    # Check member count
    members = await temp_db.get_members(proj.id)
    assert len(members) == 2

    # Member role upsert (ON CONFLICT update)
    updated_role = await temp_db.add_member(
        proj.id, 1002, role=ProjectMemberRole.LEAD.value
    )
    assert updated_role.role == ProjectMemberRole.LEAD.value

    # Lead transfer
    transfer_success = await temp_db.update_project_lead(proj.id, new_lead_id=1002)
    assert transfer_success is True

    updated_proj = await temp_db.get_project(proj.id)
    assert updated_proj is not None
    assert updated_proj.lead_id == 1002

    updated_members = await temp_db.get_members(proj.id)
    lead_member = next(m for m in updated_members if m.user_id == 1002)
    assert lead_member.is_lead is True

    old_lead = next(m for m in updated_members if m.user_id == 1001)
    assert old_lead.is_lead is False

    # Remove member
    removed = await temp_db.remove_member(proj.id, 1001)
    assert removed is True
    assert await temp_db.is_member(proj.id, 1001) is False
    assert len(await temp_db.get_members(proj.id)) == 1


@pytest.mark.asyncio
async def test_project_channels(temp_db: Database) -> None:
    """Test channel registration and lookups."""
    proj = await temp_db.create_project(
        guild_id=1,
        name="Channel Test Project",
        description="Testing channel mappings",
        lead_id=10,
    )

    # Register channels
    await temp_db.set_channel(proj.id, "announcements", 5001)
    await temp_db.set_channel(proj.id, "team-chat", 5002)

    channels = await temp_db.get_channels(proj.id)
    assert channels == {"announcements": 5001, "team-chat": 5002}

    # Reverse lookup by channel ID
    found_proj = await temp_db.get_project_by_channel_id(5002)
    assert found_proj is not None
    assert found_proj.id == proj.id


@pytest.mark.asyncio
async def test_project_updates(temp_db: Database) -> None:
    """Test recording and querying weekly updates."""
    proj = await temp_db.create_project(
        guild_id=1,
        name="Updates Test Project",
        description="Testing progress logging",
        lead_id=20,
    )

    update1 = await temp_db.add_update(
        project_id=proj.id,
        author_id=20,
        completed="Designed system architecture",
        working_on="Implementing database layer",
        blocked_by="None",
        next_steps="Write unit tests",
    )
    assert update1.id > 0
    assert update1.completed == "Designed system architecture"

    updates = await temp_db.get_updates(proj.id, limit=5)
    assert len(updates) == 1
    assert updates[0].working_on == "Implementing database layer"


@pytest.mark.asyncio
async def test_get_project_by_name_prioritizes_active_project(temp_db: Database) -> None:
    """Verify get_project_by_name returns the active project over an archived project with the same name."""
    guild_id = 999

    # 1. Create older project that gets archived
    p1 = await temp_db.create_project(
        guild_id=guild_id,
        name="Transformer Tool",
        description="Older version",
        lead_id=1,
    )
    await temp_db.update_project_status(p1.id, ProjectStatus.ARCHIVED.value)

    # 2. Create newer project with same name that is active
    p2 = await temp_db.create_project(
        guild_id=guild_id,
        name="Transformer Tool",
        description="New active version",
        lead_id=2,
    )

    # Lookup should return the active project (p2), not the older archived project (p1)
    resolved = await temp_db.get_project_by_name(guild_id, "transformer tool")
    assert resolved is not None
    assert resolved.id == p2.id
    assert resolved.status == ProjectStatus.ACTIVE.value
    assert resolved.lead_id == 2


@pytest.mark.asyncio
async def test_project_hub_message_id_persistence(temp_db: Database) -> None:
    """Verify storing and retrieving hub_message_id on a project."""
    p = await temp_db.create_project(
        guild_id=1,
        name="Hub Sync Project",
        description="Testing live card tracking",
        lead_id=42,
    )
    assert p.hub_message_id is None

    # Update message ID
    success = await temp_db.update_project_hub_message(p.id, 9876543210)
    assert success is True

    fetched = await temp_db.get_project(p.id)
    assert fetched is not None
    assert fetched.hub_message_id == 9876543210


@pytest.mark.asyncio
async def test_delete_project_cascades(temp_db: Database) -> None:
    """Verify deleting a project cascades to members, channels, and updates."""
    p = await temp_db.create_project(
        guild_id=1,
        name="Delete Me Project",
        description="Testing cascading deletion",
        lead_id=10,
    )
    # Add member, channel, update
    await temp_db.add_member(p.id, 20)
    await temp_db.set_channel(p.id, "team-chat", 777)
    await temp_db.add_update(project_id=p.id, author_id=10, completed="Phase 1")

    # Delete project
    deleted = await temp_db.delete_project(p.id)
    assert deleted is True

    # Verify project is gone
    assert await temp_db.get_project(p.id) is None

    # Verify cascades
    assert await temp_db.get_members(p.id) == []
    assert await temp_db.get_channels(p.id) == {}
    assert await temp_db.get_updates(p.id) == []




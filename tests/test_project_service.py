"""Unit tests for ProjectService business logic and workflows."""


import discord
import pytest

from tests.conftest import make_member
from token_maxxer.services.project_service import (
    ProjectError,
    ProjectService,
    ProjectValidationError,
)
from token_maxxer.utils.constants import (
    ROLE_ADMIN,
    ProjectStatus,
)


@pytest.mark.asyncio
async def test_create_project_validation(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test validation constraints on project name."""
    lead = make_member(1001, "Alice", mock_guild)

    # Empty name
    with pytest.raises(ProjectValidationError, match="between 2 and 50"):
        await project_service.create_project(
            guild=mock_guild,
            name="   ",
            description="Some description",
            lead=lead,
        )

    # Name too long
    with pytest.raises(ProjectValidationError, match="between 2 and 50"):
        await project_service.create_project(
            guild=mock_guild,
            name="A" * 60,
            description="Some description",
            lead=lead,
        )


@pytest.mark.asyncio
async def test_create_project_success(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test full staged project workspace creation."""
    lead = make_member(1001, "Alice", mock_guild)

    workspace = await project_service.create_project(
        guild=mock_guild,
        name="Vision Transformer",
        description="Vision model project",
        tech_stack="PyTorch, OpenCV",
        lead=lead,
    )

    assert workspace.project.id > 0
    assert workspace.project.name == "Vision Transformer"
    assert workspace.category is not None
    assert len(workspace.channels) == 4
    assert "announcements" in workspace.channels
    assert "team-chat" in workspace.channels
    assert "tasks" in workspace.channels
    assert "work" in workspace.channels


@pytest.mark.asyncio
async def test_project_status_transitions(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test status updates with role authorization checks."""
    lead = make_member(1001, "Alice", mock_guild)
    outsider = make_member(2001, "Bob", mock_guild)

    admin_role = next(r for r in mock_guild.roles if r.name == ROLE_ADMIN)
    admin = make_member(3001, "Charlie", mock_guild, roles=[admin_role])

    workspace = await project_service.create_project(
        guild=mock_guild,
        name="Status Test Project",
        description="Testing state transitions",
        lead=lead,
    )
    proj_id = workspace.project.id

    # 1. Outsider cannot change status
    with pytest.raises(ProjectError, match="Only the project lead"):
        await project_service.change_project_status(
            guild=mock_guild,
            project_id=proj_id,
            new_status=ProjectStatus.COMPLETED,
            caller=outsider,
        )

    # 2. Lead can update status
    completed = await project_service.change_project_status(
        guild=mock_guild,
        project_id=proj_id,
        new_status=ProjectStatus.COMPLETED,
        caller=lead,
    )
    assert completed.status == ProjectStatus.COMPLETED.value

    # 3. Admin can update status
    active = await project_service.change_project_status(
        guild=mock_guild,
        project_id=proj_id,
        new_status=ProjectStatus.ACTIVE,
        caller=admin,
    )
    assert active.status == ProjectStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_project_deadline_flow(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test setting, updating, and clearing deadlines."""
    lead = make_member(1001, "Alice", mock_guild)
    outsider = make_member(2002, "Dave", mock_guild)

    workspace = await project_service.create_project(
        guild=mock_guild,
        name="Deadline Test Project",
        description="Testing deadlines",
        lead=lead,
    )
    proj_id = workspace.project.id

    # Unauthorized user rejected
    with pytest.raises(ProjectError, match="Only the project lead"):
        await project_service.set_project_deadline(
            guild=mock_guild,
            project_id=proj_id,
            deadline="2026-11-30",
            caller=outsider,
        )

    # Lead sets deadline
    updated = await project_service.set_project_deadline(
        guild=mock_guild,
        project_id=proj_id,
        deadline="2026-11-30",
        caller=lead,
    )
    assert updated.deadline == "2026-11-30"

    # Lead clears deadline
    cleared = await project_service.set_project_deadline(
        guild=mock_guild,
        project_id=proj_id,
        deadline="clear",
        caller=lead,
    )
    assert cleared.deadline is None


@pytest.mark.asyncio
async def test_archive_project_flow(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test project workspace archival."""
    lead = make_member(1001, "Alice", mock_guild)

    workspace = await project_service.create_project(
        guild=mock_guild,
        name="Archive Test Project",
        description="Testing archive flow",
        lead=lead,
    )
    proj_id = workspace.project.id

    archived = await project_service.archive_project(
        project_id=proj_id,
        guild=mock_guild,
        caller=lead,
    )

    assert archived.is_archived is True
    assert archived.archived_at is not None
    workspace.category.edit.assert_called_once()


@pytest.mark.asyncio
async def test_project_updates_authorization(
    project_service: ProjectService,
    mock_guild: discord.Guild,
) -> None:
    """Test permission check on posting weekly updates."""
    lead = make_member(1001, "Alice", mock_guild)
    outsider = make_member(2003, "Eve", mock_guild)

    workspace = await project_service.create_project(
        guild=mock_guild,
        name="Update Auth Test",
        description="Testing updates authorization",
        lead=lead,
    )
    proj_id = workspace.project.id

    # Outsider cannot post update
    with pytest.raises(ProjectError, match="must be an active member"):
        await project_service.post_project_update(
            guild=mock_guild,
            project_id=proj_id,
            author=outsider,
            completed="Nothing",
        )

    # Lead can post update
    upd = await project_service.post_project_update(
        guild=mock_guild,
        project_id=proj_id,
        author=lead,
        completed="Completed phase 1",
        working_on="Phase 2",
    )
    assert upd.completed == "Completed phase 1"

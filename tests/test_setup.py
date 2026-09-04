"""Unit tests for server setup, GuildService reconciliation, and role checks."""

import discord
import pytest

from tests.conftest import make_member
from token_maxxer.services.guild_service import GuildService
from token_maxxer.utils.checks import (
    NotAuthorizedError,
    can_create_projects,
    is_coordinator_or_admin,
)
from token_maxxer.utils.constants import (
    ADMIN_ROLES,
    ROLE_ADMIN,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
    CategoryDefinition,
    RoleDefinition,
)


@pytest.mark.asyncio
async def test_get_or_create_role(mock_guild: discord.Guild) -> None:
    """Test find-or-create behavior for server roles."""
    service = GuildService()

    # Existing role should be returned without calling create_role
    admin_def = next(r for r in ADMIN_ROLES if r.name == ROLE_ADMIN)
    admin_role, created = await service.get_or_create_role(mock_guild, admin_def)
    assert admin_role is not None
    assert admin_role.name == ROLE_ADMIN
    assert created is False
    mock_guild.create_role.assert_not_called()

    # Non-existing role should be created
    new_def = RoleDefinition(name="Special Guest", color=discord.Color.teal())
    new_role, created2 = await service.get_or_create_role(mock_guild, new_def)
    assert new_role is not None
    assert new_role.name == "Special Guest"
    assert created2 is True
    mock_guild.create_role.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_category(mock_guild: discord.Guild) -> None:
    """Test find-or-create behavior for categories."""
    service = GuildService()

    cat_def = CategoryDefinition(name="CLUB", emoji="📢")

    # First call creates category
    cat1, created1 = await service.get_or_create_category(mock_guild, cat_def)
    assert cat1 is not None
    assert created1 is True
    mock_guild.create_category.assert_called_once()

    # Second call returns existing category
    mock_guild.create_category.reset_mock()
    cat2, created2 = await service.get_or_create_category(mock_guild, cat_def)
    assert cat2.id == cat1.id
    assert created2 is False
    mock_guild.create_category.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_server_structure_idempotency(
    mock_guild: discord.Guild,
) -> None:
    """Ensure reconcile_server_structure sets up server and is idempotent."""
    service = GuildService()

    # Run 1: Provisions missing elements
    report1 = await service.reconcile_server_structure(mock_guild)
    assert report1.has_errors is False
    assert report1.total_categories > 0
    assert report1.total_channels > 0

    # Run 2: Re-running should find everything already existing
    report2 = await service.reconcile_server_structure(mock_guild)
    assert report2.has_errors is False
    assert len(report2.categories_created) == 0
    assert len(report2.channels_created) == 0


@pytest.mark.asyncio
async def test_permission_checks(mock_guild: discord.Guild) -> None:
    """Test custom command check predicates for server management and project creation."""
    admin_role = next(r for r in mock_guild.roles if r.name == ROLE_ADMIN)
    core_role = next(r for r in mock_guild.roles if r.name == ROLE_CORE_MEMBER)
    member_role = next(r for r in mock_guild.roles if r.name == ROLE_MEMBER)

    admin_user = make_member(1, "Admin", mock_guild, roles=[admin_role])
    core_user = make_member(2, "Core", mock_guild, roles=[core_role])
    regular_user = make_member(3, "Member", mock_guild, roles=[member_role])

    # is_coordinator_or_admin check predicate: admin passes, core and regular raise error
    manage_check = is_coordinator_or_admin().predicate
    interaction_admin = type("Interaction", (), {"user": admin_user, "guild": mock_guild})()
    interaction_core = type("Interaction", (), {"user": core_user, "guild": mock_guild})()
    interaction_member = type("Interaction", (), {"user": regular_user, "guild": mock_guild})()

    assert await manage_check(interaction_admin) is True
    with pytest.raises(NotAuthorizedError):
        await manage_check(interaction_core)
    with pytest.raises(NotAuthorizedError):
        await manage_check(interaction_member)

    # can_create_projects check predicate: admin and core pass, regular raises NotAuthorizedError
    create_check = can_create_projects().predicate
    assert await create_check(interaction_admin) is True
    assert await create_check(interaction_core) is True
    with pytest.raises(NotAuthorizedError):
        await create_check(interaction_member)

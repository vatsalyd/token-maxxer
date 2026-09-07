"""Unit tests for Discord permissions and role enforcement."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from token_maxxer.services.permission_service import PermissionService
from token_maxxer.utils.constants import (
    ADMIN_ROLES,
    ROLE_ADMIN,
    ROLE_ALUMNI,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
    ROLE_PROJECT_LEAD,
)


def test_role_hierarchy_ordering() -> None:
    """Verify role hierarchy precedence order."""
    role_names = [spec.name for spec in ADMIN_ROLES]
    assert role_names == [
        ROLE_ADMIN,
        ROLE_COORDINATOR,
        ROLE_CORE_MEMBER,
        ROLE_PROJECT_LEAD,
        ROLE_ALUMNI,
        ROLE_MEMBER,
    ]


def test_role_permissions_least_privilege() -> None:
    """Ensure standard member and alumni roles do not have admin or management permissions."""
    member_spec = next(r for r in ADMIN_ROLES if r.name == ROLE_MEMBER)
    member_perms = member_spec.permissions
    assert member_perms.administrator is False
    assert member_perms.manage_channels is False
    assert member_perms.manage_guild is False
    assert member_perms.manage_roles is False
    assert member_perms.manage_messages is False

    alumni_spec = next(r for r in ADMIN_ROLES if r.name == ROLE_ALUMNI)
    assert alumni_spec.hoist is True
    assert alumni_spec.mentionable is True
    assert alumni_spec.permissions.administrator is False


@pytest.mark.asyncio
async def test_apply_public_permissions(
    permission_service: PermissionService,
    mock_guild: discord.Guild,
) -> None:
    """Test public channel read-only vs write permission overwrites."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "announcements"
    channel.guild = mock_guild
    channel.edit = AsyncMock()

    # 1. Read-only configuration
    await permission_service.apply_public_permissions(channel, readonly=True)
    channel.edit.assert_called_once()
    overwrites = channel.edit.call_args[1]["overwrites"]
    everyone_overwrite = overwrites[mock_guild.default_role]
    assert everyone_overwrite.view_channel is True
    assert everyone_overwrite.send_messages is False
    assert everyone_overwrite.add_reactions is True

    # 2. Write-enabled configuration
    channel.edit.reset_mock()
    await permission_service.apply_public_permissions(channel, readonly=False)
    channel.edit.assert_called_once()
    overwrites = channel.edit.call_args[1]["overwrites"]
    everyone_overwrite = overwrites[mock_guild.default_role]
    assert everyone_overwrite.view_channel is True
    assert everyone_overwrite.send_messages is True


@pytest.mark.asyncio
async def test_grant_and_revoke_project_member_access(
    permission_service: PermissionService,
    mock_guild: discord.Guild,
) -> None:
    """Test granting and revoking member write access on project channels."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "team-chat"
    channel.guild = mock_guild
    channel.set_permissions = AsyncMock()

    member = MagicMock(spec=discord.Member)
    member.id = 55555

    # Grant access
    await permission_service.grant_project_member_access(channel, member)
    target = channel.set_permissions.call_args[0][0]
    overwrite = channel.set_permissions.call_args.kwargs["overwrite"]
    assert target == member
    assert overwrite.view_channel is True
    assert overwrite.send_messages is True

    # Revoke access
    channel.set_permissions.reset_mock()
    await permission_service.revoke_project_member_access(channel, member)
    channel.set_permissions.assert_called_once_with(
        member,
        overwrite=None,
        reason="token-maxxer revoke project access",
    )


@pytest.mark.asyncio
async def test_reconcile_guild_permissions_skips_project_workspaces(
    permission_service: PermissionService,
    mock_guild: MagicMock,
) -> None:
    """Verify reconcile_guild_permissions does not touch project workspace channels/categories."""
    project_cat = MagicMock(spec=discord.CategoryChannel)
    project_cat.id = 7001
    project_cat.name = "🚀 PROJECT — GNN Water Quality"
    project_cat._is_category = True
    project_cat.edit = AsyncMock()

    proj_announcements = MagicMock(spec=discord.TextChannel)
    proj_announcements.id = 7002
    proj_announcements.name = "📢・announcements"
    proj_announcements.category = project_cat
    proj_announcements.guild = mock_guild
    proj_announcements._is_category = False
    proj_announcements.edit = AsyncMock()

    club_cat = MagicMock(spec=discord.CategoryChannel)
    club_cat.id = 7003
    club_cat.name = "📢 CLUB"
    club_cat._is_category = True
    club_cat.edit = AsyncMock()

    club_announcements = MagicMock(spec=discord.TextChannel)
    club_announcements.id = 7004
    club_announcements.name = "📢・announcements"
    club_announcements.category = club_cat
    club_announcements.guild = mock_guild
    club_announcements._is_category = False
    club_announcements.edit = AsyncMock()

    mock_guild._channels.clear()
    mock_guild._channels[project_cat.id] = project_cat
    mock_guild._channels[proj_announcements.id] = proj_announcements
    mock_guild._channels[club_cat.id] = club_cat
    mock_guild._channels[club_announcements.id] = club_announcements

    reconciled_count, errors = await permission_service.reconcile_guild_permissions(mock_guild)

    assert errors == []
    # Project announcement and category should NOT be edited
    proj_announcements.edit.assert_not_called()
    project_cat.edit.assert_not_called()
    # Club announcement SHOULD be edited
    club_announcements.edit.assert_called_once()


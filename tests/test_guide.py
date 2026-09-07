"""Unit tests for the Core Team GuideService and guide commands."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from token_maxxer.services.guide_service import GuideService
from token_maxxer.utils.checks import NotAuthorizedError, is_core_or_higher
from token_maxxer.utils.constants import (
    CHANNEL_BOT_GUIDE,
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
)


@pytest.fixture
def guide_service(mock_bot: MagicMock) -> GuideService:
    """Provide a GuideService instance with a mocked bot."""
    return GuideService(mock_bot)


def test_embed_builders(guide_service: GuideService) -> None:
    """Verify that all 7 guide section builders produce well-formed embeds."""
    # 1. Overview
    overview = guide_service.build_overview_embed()
    assert "Bot Overview & Architecture" in (overview.title or "")
    assert len(overview.fields) >= 2

    # 2. Governance
    governance = guide_service.build_governance_embed()
    assert "Server Provisioning" in (governance.title or "")
    assert any("/setup" in (governance.title or "") for _ in [1])

    # 3. Onboarding
    onboarding = guide_service.build_onboarding_guide_embed()
    assert "Onboarding" in (onboarding.title or "")

    # 4. Projects
    projects = guide_service.build_projects_guide_embed()
    assert "Project Workspace Lifecycle" in (projects.title or "")

    # 5. Teams
    teams = guide_service.build_teams_guide_embed()
    assert "Team Management & Permissions" in (teams.title or "")

    # 6. Developer
    dev = guide_service.build_developer_embed()
    assert "Core Developer Guide" in (dev.title or "")

    # 7. Troubleshooting
    trouble = guide_service.build_troubleshooting_embed()
    assert "Troubleshooting" in (trouble.title or "")


def test_get_section_embed(guide_service: GuideService) -> None:
    """Verify section lookup by key."""
    sections = [
        "overview",
        "governance",
        "onboarding",
        "projects",
        "teams",
        "developer",
        "troubleshooting",
    ]
    for sec in sections:
        embed = guide_service.get_section_embed(sec)
        assert isinstance(embed, discord.Embed)

    with pytest.raises(KeyError):
        guide_service.get_section_embed("nonexistent_section")


def test_get_all_sections(guide_service: GuideService) -> None:
    """Verify that get_all_sections returns exactly 7 sections in order."""
    all_sections = guide_service.get_all_sections()
    assert len(all_sections) == 7
    keys = [k for k, _ in all_sections]
    assert keys == [
        "overview",
        "governance",
        "onboarding",
        "projects",
        "teams",
        "developer",
        "troubleshooting",
    ]


@pytest.mark.asyncio
async def test_publish_bot_guide_success(
    guide_service: GuideService,
    mock_guild: MagicMock,
) -> None:
    """Verify publishing all 7 embeds to #🤖・bot-guide."""
    guide_channel = MagicMock(spec=discord.TextChannel)
    guide_channel.id = 5001
    guide_channel.name = CHANNEL_BOT_GUIDE
    guide_channel._is_category = False
    guide_channel.send = AsyncMock()

    # Empty channel history mock
    async def empty_history(*args, **kwargs):
        if False:
            yield None

    guide_channel.history = MagicMock(return_value=empty_history())
    mock_guild._channels[guide_channel.id] = guide_channel

    success, msg = await guide_service.publish_bot_guide(mock_guild)
    assert success is True
    assert "Successfully published 7 guide sections" in msg
    assert guide_channel.send.call_count == 7


@pytest.mark.asyncio
async def test_publish_bot_guide_channel_missing(
    guide_service: GuideService,
    mock_guild: MagicMock,
) -> None:
    """Verify appropriate error message when #🤖・bot-guide does not exist."""
    success, msg = await guide_service.publish_bot_guide(mock_guild)
    assert success is False
    assert "not found" in msg


@pytest.mark.asyncio
async def test_is_core_or_higher_permission_checks(
    mock_guild: MagicMock,
) -> None:
    """Verify that is_core_or_higher allows core roles and rejects standard members."""
    decorator = is_core_or_higher()
    predicate = decorator.predicate

    mock_member = MagicMock(spec=discord.Member)
    mock_member.guild = mock_guild
    mock_member.guild_permissions = MagicMock(spec=discord.Permissions)
    mock_member.guild_permissions.administrator = False

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = mock_guild
    interaction.user = mock_member

    # 1. Regular Member only -> Unauthorized
    regular_role = MagicMock(spec=discord.Role)
    regular_role.name = ROLE_MEMBER
    mock_member.roles = [regular_role]
    mock_member.guild_permissions.administrator = False
    mock_member.id = 999999
    mock_guild.owner_id = 111111

    with pytest.raises(NotAuthorizedError):
        await predicate(interaction)

    # 2. Core Member -> Authorized
    core_role = MagicMock(spec=discord.Role)
    core_role.name = ROLE_CORE_MEMBER
    mock_member.roles = [regular_role, core_role]
    assert await predicate(interaction) is True

    # 3. Coordinator -> Authorized
    coord_role = MagicMock(spec=discord.Role)
    coord_role.name = ROLE_COORDINATOR
    mock_member.roles = [coord_role]
    assert await predicate(interaction) is True

    # 4. Club Admin -> Authorized
    admin_role = MagicMock(spec=discord.Role)
    admin_role.name = ROLE_ADMIN
    mock_member.roles = [admin_role]
    assert await predicate(interaction) is True

    # 5. Server Owner -> Always Authorized
    mock_member.roles = []
    mock_member.id = mock_guild.owner_id
    assert await predicate(interaction) is True

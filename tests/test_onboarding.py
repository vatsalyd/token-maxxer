"""Unit tests for the onboarding service, views, and event flows."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from token_maxxer.cogs.onboarding import Onboarding
from token_maxxer.services.onboarding_service import OnboardingService
from token_maxxer.utils.constants import INTEREST_ROLES, ROLE_ALUMNI, ROLE_MEMBER
from token_maxxer.views.onboarding_views import RoleSelectionView


@pytest.fixture
def onboarding_service(mock_bot: MagicMock) -> OnboardingService:
    """Provide an OnboardingService instance with a mocked bot."""
    return OnboardingService(mock_bot)


def test_embed_builders(onboarding_service: OnboardingService) -> None:
    """Verify that all START HERE embed builders produce well-formed embeds."""
    # 1. Rules
    rules_embed = onboarding_service.build_rules_embed()
    assert "Rules & Code of Conduct" in (rules_embed.title or "")
    assert len(rules_embed.fields) >= 5

    # 2. Welcome
    welcome_embed = onboarding_service.build_welcome_embed()
    assert "Welcome to the DSAI Club" in (welcome_embed.title or "")
    assert any("Mission" in f.name for f in welcome_embed.fields)

    # 3. Server Guide
    guide_embed = onboarding_service.build_server_guide_embed()
    assert "Server Navigation" in (guide_embed.title or "")
    assert any("START HERE" in f.name for f in guide_embed.fields)
    assert any("Cheat Sheet" in f.name for f in guide_embed.fields)

    # 4. Roles
    roles_embed = onboarding_service.build_roles_embed()
    assert "Role Selection" in (roles_embed.title or "")
    assert any("Available Interest Roles" in f.name for f in roles_embed.fields)


def test_role_selection_view_components() -> None:
    """Verify that RoleSelectionView is persistent and contains expected components."""
    view = RoleSelectionView()
    assert view.is_persistent()

    # Find the dropdown
    select_items = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(select_items) == 1
    dropdown = select_items[0]
    assert dropdown.custom_id == "token_maxxer:onboarding:interest_select"
    assert len(dropdown.options) == len(INTEREST_ROLES)

    # Find the action buttons
    button_items = [item for item in view.children if isinstance(item, discord.ui.Button)]
    custom_ids = {b.custom_id for b in button_items}
    assert "token_maxxer:onboarding:claim_member" in custom_ids
    assert "token_maxxer:onboarding:claim_alumni" in custom_ids
    assert "token_maxxer:onboarding:clear_interests" in custom_ids


@pytest.mark.asyncio
async def test_populate_start_here_channels(
    onboarding_service: OnboardingService,
    mock_guild: MagicMock,
) -> None:
    """Test populating all four START HERE channels."""
    channel_names = ["📜・rules", "👋・welcome", "🧭・server-guide", "🎭・roles"]
    channels = {}
    for idx, name in enumerate(channel_names):
        ch = MagicMock(spec=discord.TextChannel)
        ch.id = 3000 + idx
        ch.name = name
        ch._is_category = False
        ch.history = MagicMock()

        # Mock async generator for history
        async def empty_history(*args, **kwargs):
            if False:
                yield None

        ch.history.return_value = empty_history()
        ch.send = AsyncMock()
        mock_guild._channels[ch.id] = ch
        channels[name] = ch

    count, errors = await onboarding_service.populate_start_here_channels(mock_guild)
    assert count == 4
    assert len(errors) == 0

    for ch in channels.values():
        ch.send.assert_called_once()


@pytest.mark.asyncio
async def test_on_member_join_assigns_role_and_greets(
    mock_bot: MagicMock,
    mock_guild: MagicMock,
) -> None:
    """Verify that on_member_join auto-assigns Member role and sends welcome greeting."""
    from token_maxxer.config.settings import settings

    cog = Onboarding(mock_bot)

    # Configure guild ID to match settings.target_guild_id
    mock_guild.id = settings.target_guild_id

    member_role = discord.utils.get(mock_guild.roles, name=ROLE_MEMBER)
    assert member_role is not None

    welcome_channel = MagicMock(spec=discord.TextChannel)
    welcome_channel.id = 4001
    welcome_channel.name = "👋・welcome"
    welcome_channel._is_category = False
    welcome_channel.send = AsyncMock()
    mock_guild._channels[welcome_channel.id] = welcome_channel

    # Mock newcomer
    new_member = MagicMock(spec=discord.Member)
    new_member.id = 555555555555555555
    new_member.guild = mock_guild
    new_member.roles = []
    new_member.display_name = "NewCoder"
    new_member.mention = "<@555555555555555555>"
    new_member.display_avatar.url = "https://example.com/avatar.png"
    new_member.add_roles = AsyncMock()

    await cog.on_member_join(new_member)

    # Role added
    new_member.add_roles.assert_called_once_with(
        member_role,
        reason="token-maxxer auto-onboarding: default member role",
    )
    # Welcome card posted
    welcome_channel.send.assert_called_once()
    assert welcome_channel.send.call_args[1]["content"] == new_member.mention


@pytest.mark.asyncio
async def test_claim_alumni_button_toggle(mock_guild: MagicMock) -> None:
    """Verify that clicking Claim Alumni Role assigns both Alumni and Member roles, and toggles off when repeated."""
    view = RoleSelectionView()
    button = next(
        b for b in view.children
        if isinstance(b, discord.ui.Button) and b.custom_id == "token_maxxer:onboarding:claim_alumni"
    )

    alumni_role = discord.utils.get(mock_guild.roles, name=ROLE_ALUMNI)
    member_role = discord.utils.get(mock_guild.roles, name=ROLE_MEMBER)
    assert alumni_role is not None
    assert member_role is not None

    user = MagicMock(spec=discord.Member)
    user.guild = mock_guild
    user.roles = []
    user.add_roles = AsyncMock()
    user.remove_roles = AsyncMock()

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = mock_guild
    interaction.user = user
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # 1. First click: grants alumni_role (and member_role if absent)
    await button.callback(interaction)
    user.add_roles.assert_called_once_with(alumni_role, member_role, reason="Self-claimed Alumni role")

    # 2. Second click: user already holds alumni_role -> toggles off
    user.roles = [alumni_role, member_role]
    await button.callback(interaction)
    user.remove_roles.assert_called_once_with(alumni_role, reason="Self-removed Alumni role")


"""Shared fixtures and mocks for token-maxxer test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from token_maxxer.database.db import Database
from token_maxxer.services.permission_service import PermissionService
from token_maxxer.services.project_service import ProjectService
from token_maxxer.services.team_service import TeamService
from token_maxxer.utils.constants import (
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
)


@pytest.fixture
async def temp_db(tmp_path: Path) -> AsyncGenerator[Database, None]:
    """Provide a freshly initialized, isolated Database instance."""
    db_path = tmp_path / "test_token_maxxer.db"
    database = Database(db_path=db_path)
    await database.initialize()
    yield database


@pytest.fixture
def mock_bot() -> MagicMock:
    """Provide a mock Bot client."""
    bot = MagicMock(spec=discord.Client)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999999999
    bot.user.name = "token-maxxer"
    return bot


@pytest.fixture
def mock_guild() -> MagicMock:
    """Provide a mock Discord Guild with realistic roles and channels."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123456789012345678
    guild.name = "DSAI Club Server"
    guild.owner_id = 111111111111111111

    # Standard roles
    admin_role = MagicMock(spec=discord.Role)
    admin_role.id = 101
    admin_role.name = ROLE_ADMIN

    coord_role = MagicMock(spec=discord.Role)
    coord_role.id = 102
    coord_role.name = ROLE_COORDINATOR

    core_role = MagicMock(spec=discord.Role)
    core_role.id = 103
    core_role.name = ROLE_CORE_MEMBER

    member_role = MagicMock(spec=discord.Role)
    member_role.id = 104
    member_role.name = ROLE_MEMBER

    everyone_role = MagicMock(spec=discord.Role)
    everyone_role.id = guild.id
    everyone_role.name = "@everyone"

    guild.roles = [admin_role, coord_role, core_role, member_role, everyone_role]
    guild.default_role = everyone_role

    # bot member in guild
    bot_member = MagicMock(spec=discord.Member)
    bot_member.id = 999999999
    bot_member.name = "token-maxxer"
    bot_member.guild_permissions = MagicMock(spec=discord.Permissions)
    bot_member.guild_permissions.manage_roles = True
    bot_member.guild_permissions.administrator = True
    top_role = MagicMock(spec=discord.Role)
    top_role.position = 999
    bot_member.top_role = top_role
    guild.me = bot_member

    def role_lt(self: discord.Role, other: discord.Role) -> bool:
        return getattr(self, "position", 0) < getattr(other, "position", 0)

    for idx, r in enumerate(guild.roles):
        r.position = len(guild.roles) - idx
        r.__lt__ = role_lt
        r.edit = AsyncMock(return_value=r)

    # Helper to get role by name
    def get_role(role_id: int) -> discord.Role | None:
        return next((r for r in guild.roles if r.id == role_id), None)

    guild.get_role.side_effect = get_role

    # Channel storage and lookup
    guild._channels = {}

    def get_channel(channel_id: int) -> discord.abc.GuildChannel | None:
        return guild._channels.get(channel_id)

    guild.get_channel.side_effect = get_channel

    type(guild).categories = property(
        lambda self: [c for c in self._channels.values() if getattr(c, "_is_category", False)]
    )
    type(guild).text_channels = property(
        lambda self: [c for c in self._channels.values() if not getattr(c, "_is_category", False)]
    )

    # Channel / category creation mocks
    async def create_category(name: str, **kwargs: object) -> MagicMock:
        cat = MagicMock(spec=discord.CategoryChannel)
        cat.id = len(guild._channels) + 2000
        cat.name = name
        cat.guild = guild
        cat.text_channels = []
        cat.overwrites = kwargs.get("overwrites", {})
        cat.edit = AsyncMock(return_value=cat)
        cat.set_permissions = AsyncMock()
        cat._is_category = True
        guild._channels[cat.id] = cat
        return cat

    async def create_text_channel(name: str, **kwargs: object) -> MagicMock:
        ch = MagicMock(spec=discord.TextChannel)
        ch.id = len(guild._channels) + 3000
        ch.name = name
        ch.guild = guild
        ch.category = kwargs.get("category")
        ch.overwrites = kwargs.get("overwrites", {})
        ch.send = AsyncMock()
        ch.edit = AsyncMock(return_value=ch)
        ch.set_permissions = AsyncMock()
        ch._is_category = False
        guild._channels[ch.id] = ch
        if ch.category and hasattr(ch.category, "text_channels"):
            ch.category.text_channels.append(ch)
        return ch

    async def create_role(name: str, **kwargs: object) -> MagicMock:
        r = MagicMock(spec=discord.Role)
        r.id = len(guild.roles) + 100
        r.name = name
        r.color = kwargs.get("color", discord.Color.default())
        r.hoist = kwargs.get("hoist", False)
        r.mentionable = kwargs.get("mentionable", False)
        r.position = len(guild.roles)
        r.__lt__ = role_lt
        r.edit = AsyncMock(return_value=r)
        guild.roles.append(r)
        return r

    guild.create_category = AsyncMock(side_effect=create_category)
    guild.create_text_channel = AsyncMock(side_effect=create_text_channel)
    guild.create_role = AsyncMock(side_effect=create_role)

    return guild


def make_member(
    user_id: int,
    name: str,
    guild: discord.Guild,
    roles: list[discord.Role] | None = None,
    is_admin: bool = False,
) -> MagicMock:
    """Helper to construct a mock Discord Member."""
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.display_name = name
    member.mention = f"<@{user_id}>"
    member.guild = guild
    member.roles = roles or []
    member.guild_permissions = MagicMock(spec=discord.Permissions)
    member.guild_permissions.administrator = is_admin
    return member


@pytest.fixture
def permission_service() -> PermissionService:
    """Provide a PermissionService instance."""
    return PermissionService()


@pytest.fixture
def project_service(mock_bot: MagicMock, temp_db: Database) -> ProjectService:
    """Provide a ProjectService wired to the temporary test database."""
    return ProjectService(bot=mock_bot, database=temp_db)


@pytest.fixture
def team_service(mock_bot: MagicMock, temp_db: Database) -> TeamService:
    """Provide a TeamService wired to the temporary test database."""
    return TeamService(bot=mock_bot, database=temp_db)

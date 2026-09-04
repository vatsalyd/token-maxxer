"""Authorization checks and command predicates for token-maxxer.

Provides reusable Discord slash-command check decorators based on
the DSAI Club role model and hierarchy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import discord
from discord import app_commands

from token_maxxer.utils.constants import (
    PROJECT_CREATE_ALLOWED_ROLES,
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    SETUP_ALLOWED_ROLES,
)

T = TypeVar("T")


class NotAuthorizedError(app_commands.CheckFailure):
    """Raised when an interaction caller lacks required role(s).

    Attributes:
        required_roles: Roles that would satisfy authorization.
    """

    def __init__(
        self,
        message: str | None = None,
        required_roles: list[str] | None = None,
    ) -> None:
        self.required_roles = required_roles or []
        default_msg = (
            f"You need one of the following roles to run this command: "
            f"{', '.join(self.required_roles)}"
            if self.required_roles
            else "You are not authorized to use this command."
        )
        super().__init__(message or default_msg)


def has_any_role(*role_names: str) -> Callable[[T], T]:
    """Check if the calling member has any of the specified roles.

    The guild owner and members with administrator permissions always pass.

    Args:
        *role_names: Role names (e.g. ``"👑 Club Admin"``, ``"⚡ Coordinator"``).

    Returns:
        An ``app_commands.check`` decorator.
    """
    normalized_expected = {r.strip().lower() for r in role_names}

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            raise NotAuthorizedError("This command can only be used in a server.")

        # Server owner bypass
        if interaction.user.id == interaction.guild.owner_id:
            return True

        # Administrator permission bypass
        if interaction.user.guild_permissions.administrator:
            return True

        # Check member roles
        user_role_names = {r.name.strip().lower() for r in interaction.user.roles}
        if bool(user_role_names & normalized_expected):
            return True

        raise NotAuthorizedError(
            required_roles=list(role_names),
        )

    return app_commands.check(predicate)


def is_coordinator_or_admin() -> Callable[[T], T]:
    """Check if the user is a Coordinator, Club Admin, or Guild Owner.

    Required for server infrastructure commands like ``/setup``.
    """
    return has_any_role(*SETUP_ALLOWED_ROLES)


def is_core_or_higher() -> Callable[[T], T]:
    """Check if the user is Core Member, Coordinator, Club Admin, or Guild Owner."""
    return has_any_role(ROLE_ADMIN, ROLE_COORDINATOR, ROLE_CORE_MEMBER)


def can_create_projects() -> Callable[[T], T]:
    """Check if the user has permission to create new projects."""
    return has_any_role(*PROJECT_CREATE_ALLOWED_ROLES)

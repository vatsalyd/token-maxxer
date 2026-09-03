"""Guild service for token-maxxer.

Handles server structure provisioning, role reconciliation, category/channel
management, and idempotency guarantees. All operations are safe to run multiple
times without creating duplicates.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field

import discord

from token_maxxer.utils.constants import (
    ALL_ROLES,
    SERVER_STRUCTURE,
    CategoryDefinition,
    RoleDefinition,
)
from token_maxxer.utils.helpers import make_embed, success_embed, warning_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)


# ─── Report Dataclasses ───────────────────────────────────────────────────────


@dataclass
class ReconciliationReport:
    """Summary of actions taken during server reconciliation.

    Attributes:
        roles_created: Names of newly created roles.
        roles_existing: Names of verified existing roles.
        categories_created: Names of newly created categories.
        categories_existing: Names of verified existing categories.
        channels_created: Names of newly created channels.
        channels_existing: Names of verified existing channels.
        errors: Error messages encountered during reconciliation.
    """

    roles_created: list[str] = field(default_factory=list)
    roles_existing: list[str] = field(default_factory=list)
    categories_created: list[str] = field(default_factory=list)
    categories_existing: list[str] = field(default_factory=list)
    channels_created: list[str] = field(default_factory=list)
    channels_existing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_roles(self) -> int:
        return len(self.roles_created) + len(self.roles_existing)

    @property
    def total_categories(self) -> int:
        return len(self.categories_created) + len(self.categories_existing)

    @property
    def total_channels(self) -> int:
        return len(self.channels_created) + len(self.channels_existing)

    @property
    def total_created(self) -> int:
        return len(self.roles_created) + len(self.categories_created) + len(self.channels_created)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def to_embed(self) -> discord.Embed:
        """Create a formatted Discord embed presenting the report."""
        if self.has_errors:
            embed = warning_embed(
                title="token-maxxer setup completed with warnings",
                description="Server structure was reconciled, but some items encountered issues.",
            )
        else:
            embed = success_embed(
                title="token-maxxer setup complete",
                description="All roles, categories, and channels verified. No duplicates created.",
            )

        # Roles summary
        roles_desc = f"✅ {self.total_roles} verified"
        if self.roles_created:
            roles_desc += f" ({len(self.roles_created)} created: {', '.join(self.roles_created)})"
        embed.add_field(name="Roles", value=roles_desc, inline=False)

        # Categories summary
        cats_desc = f"✅ {self.total_categories} verified"
        if self.categories_created:
            cats_desc += (
                f" ({len(self.categories_created)} created: {', '.join(self.categories_created)})"
            )
        embed.add_field(name="Categories", value=cats_desc, inline=False)

        # Channels summary
        chans_desc = f"✅ {self.total_channels} verified"
        if self.channels_created:
            chans_desc += (
                f" ({len(self.channels_created)} created: {', '.join(self.channels_created)})"
            )
        embed.add_field(name="Channels", value=chans_desc, inline=False)

        # Errors if any
        if self.errors:
            error_text = "\n".join(f"• {err}" for err in self.errors[:5])
            if len(self.errors) > 5:
                error_text += f"\n*...and {len(self.errors) - 5} more*"
            embed.add_field(name="⚠️ Warnings / Issues", value=error_text, inline=False)

        return embed


@dataclass
class VerificationReport:
    """Results of verifying server structure against expected configuration.

    Attributes:
        is_complete: Whether all expected items exist and are positioned properly.
        missing_roles: Names of expected roles that are missing.
        missing_categories: Names of expected categories that are missing.
        missing_channels: Names of expected channels that are missing.
        misplaced_channels: Channels that exist but are in the wrong category.
    """

    is_complete: bool
    missing_roles: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    missing_channels: list[str] = field(default_factory=list)
    misplaced_channels: list[tuple[str, str, str]] = field(default_factory=list)

    def to_embed(self) -> discord.Embed:
        """Create a formatted Discord embed for the verification results."""
        if self.is_complete:
            return success_embed(
                title="Server Structure Verified",
                description="All roles, categories, and channels match the expected specification.",
            )

        embed = make_embed(
            title="⚠️ Server Structure Verification Issues",
            description="The following discrepancies were found against the desired server state:",
            color=discord.Color.orange(),
        )

        if self.missing_roles:
            embed.add_field(
                name=f"Missing Roles ({len(self.missing_roles)})",
                value="\n".join(f"• {r}" for r in self.missing_roles),
                inline=False,
            )

        if self.missing_categories:
            embed.add_field(
                name=f"Missing Categories ({len(self.missing_categories)})",
                value="\n".join(f"• {c}" for c in self.missing_categories),
                inline=False,
            )

        if self.missing_channels:
            chan_lines = "\n".join(f"• {ch}" for ch in self.missing_channels[:10])
            if len(self.missing_channels) > 10:
                chan_lines += f"\n*...and {len(self.missing_channels) - 10} more*"
            embed.add_field(
                name=f"Missing Channels ({len(self.missing_channels)})",
                value=chan_lines,
                inline=False,
            )

        if self.misplaced_channels:
            lines = [
                f"• `{ch}` (in `{actual}`, expected in `{expected}`)"
                for ch, actual, expected in self.misplaced_channels[:5]
            ]
            embed.add_field(
                name=f"Misplaced Channels ({len(self.misplaced_channels)})",
                value="\n".join(lines),
                inline=False,
            )

        return embed


# ─── Helper Functions ─────────────────────────────────────────────────────────


def _normalize_name(name: str) -> str:
    """Normalize a name for case-insensitive and whitespace-tolerant comparison."""
    return name.strip().lower()


def _strip_emoji_prefix(name: str) -> str:
    """Strip common emoji prefixes and separators from channel or category names."""
    if "・" in name:
        return name.split("・", 1)[1].strip().lower()
    parts = name.strip().split(" ", 1)
    if len(parts) > 1:
        return parts[1].strip().lower()
    return name.strip().lower()


# ─── Guild Service ────────────────────────────────────────────────────────────


class GuildService:
    """Service for managing Discord guild structure and roles.

    Provides idempotent methods to find, create, and repair server resources:
    - Roles (administrative and interest)
    - Categories
    - Text channels
    """

    def __init__(self, bot: discord.Client | None = None) -> None:
        self.bot = bot

    async def get_or_create_role(
        self,
        guild: discord.Guild,
        definition: RoleDefinition,
    ) -> tuple[discord.Role, bool]:
        """Find an existing role matching the definition or create it.

        Matches by exact name first, then normalized case-insensitive name,
        and finally by name without emoji prefix. If an existing role is found,
        its color, hoist, and mentionable properties are verified and updated
        if permitted by the bot's hierarchy.

        Args:
            guild: The Discord guild to operate on.
            definition: The desired role definition.

        Returns:
            A tuple of ``(role, created)`` where ``created`` is True if a new
            role was created, False if an existing role was reused.
        """
        target_norm = _normalize_name(definition.name)
        target_base = _strip_emoji_prefix(definition.name)

        # 1. Look for existing role
        existing_role: discord.Role | None = None
        for role in guild.roles:
            role_norm = _normalize_name(role.name)
            if role_norm == target_norm:
                existing_role = role
                break
            if _strip_emoji_prefix(role.name) == target_base:
                existing_role = role

        if existing_role is not None:
            needs_edit = False
            edit_kwargs: dict[str, object] = {}

            if existing_role.name != definition.name:
                edit_kwargs["name"] = definition.name
                needs_edit = True
            if existing_role.color != definition.color:
                edit_kwargs["color"] = definition.color
                needs_edit = True
            if existing_role.hoist != definition.hoist:
                edit_kwargs["hoist"] = definition.hoist
                needs_edit = True
            if existing_role.mentionable != definition.mentionable:
                edit_kwargs["mentionable"] = definition.mentionable
                needs_edit = True

            if needs_edit:
                bot_member = guild.me
                can_manage = (
                    bot_member.guild_permissions.manage_roles
                    and existing_role < bot_member.top_role
                )
                if can_manage:
                    try:
                        existing_role = await existing_role.edit(
                            reason="token-maxxer setup role reconciliation",
                            **edit_kwargs,
                        )
                        log_action(
                            log,
                            action="edit_role",
                            result="updated",
                            guild_id=guild.id,
                            role=definition.name,
                        )
                    except discord.Forbidden:
                        log_action(
                            log,
                            action="edit_role",
                            result="forbidden",
                            guild_id=guild.id,
                            role=definition.name,
                            level=logging.WARNING,
                        )
                else:
                    log_action(
                        log,
                        action="edit_role",
                        result="hierarchy_skip",
                        guild_id=guild.id,
                        role=definition.name,
                        level=logging.WARNING,
                    )

            return existing_role, False

        # 2. Create new role
        role = await guild.create_role(
            name=definition.name,
            color=definition.color,
            hoist=definition.hoist,
            mentionable=definition.mentionable,
            permissions=definition.permissions,
            reason="token-maxxer setup role provisioning",
        )
        log_action(
            log,
            action="create_role",
            result="success",
            guild_id=guild.id,
            role=definition.name,
        )
        return role, True

    async def get_or_create_category(
        self,
        guild: discord.Guild,
        definition: CategoryDefinition,
    ) -> tuple[discord.CategoryChannel, bool]:
        """Find an existing category matching the definition or create it.

        Matches by display name (``"🏠 START HERE"``), base name (``"START HERE"``),
        or case-insensitive normalized variants.

        Args:
            guild: The Discord guild to operate on.
            definition: The category definition.

        Returns:
            A tuple of ``(category, created)``.
        """
        display_name = definition.display_name
        target_display_norm = _normalize_name(display_name)
        target_base_norm = _normalize_name(definition.name)

        # 1. Search existing categories
        for cat in guild.categories:
            cat_norm = _normalize_name(cat.name)
            if cat_norm in (target_display_norm, target_base_norm):
                if cat.name != display_name and guild.me.guild_permissions.manage_channels:
                    with contextlib.suppress(discord.Forbidden):
                        cat = await cat.edit(
                            name=display_name,
                            reason="token-maxxer setup category naming reconciliation",
                        )
                return cat, False

        # 2. Create category
        category = await guild.create_category(
            name=display_name,
            reason="token-maxxer setup category provisioning",
        )
        log_action(
            log,
            action="create_category",
            result="success",
            guild_id=guild.id,
            category=display_name,
        )
        return category, True

    async def get_or_create_text_channel(
        self,
        guild: discord.Guild,
        name: str,
        category: discord.CategoryChannel | None = None,
        topic: str | None = None,
    ) -> tuple[discord.TextChannel, bool]:
        """Find an existing text channel or create it under the given category.

        Searches inside the target category first, then guild-wide for channels
        matching the exact or stripped name. If a channel exists outside the target
        category, it will be moved into the category.

        Args:
            guild: The Discord guild.
            name: The desired channel name (e.g. ``"📜・rules"``).
            category: The parent CategoryChannel, if any.
            topic: Optional channel topic description.

        Returns:
            A tuple of ``(channel, created)``.
        """
        target_norm = _normalize_name(name)
        target_base = _strip_emoji_prefix(name)

        # 1. Search inside category first if provided
        search_channels = category.text_channels if category else guild.text_channels
        for ch in search_channels:
            ch_norm = _normalize_name(ch.name)
            if ch_norm == target_norm or _strip_emoji_prefix(ch.name) == target_base:
                if topic is not None and ch.topic != topic:
                    with contextlib.suppress(discord.Forbidden):
                        ch = await ch.edit(topic=topic, reason="token-maxxer setup topic update")
                return ch, False

        # 2. If category specified, search outside category across all guild channels
        if category is not None:
            for ch in guild.text_channels:
                ch_norm = _normalize_name(ch.name)
                if ch_norm == target_norm or _strip_emoji_prefix(ch.name) == target_base:
                    try:
                        ch = await ch.edit(
                            category=category,
                            reason="token-maxxer setup move channel to category",
                        )
                        log_action(
                            log,
                            action="move_channel",
                            result="success",
                            guild_id=guild.id,
                            channel=name,
                            category=category.name,
                        )
                    except discord.Forbidden:
                        log_action(
                            log,
                            action="move_channel",
                            result="forbidden",
                            guild_id=guild.id,
                            channel=name,
                            level=logging.WARNING,
                        )
                    return ch, False

        # 3. Channel does not exist — create it
        created_channel = await guild.create_text_channel(
            name=name,
            category=category,
            topic=topic,
            reason="token-maxxer setup channel provisioning",
        )
        log_action(
            log,
            action="create_text_channel",
            result="success",
            guild_id=guild.id,
            channel=name,
            category=category.name if category else None,
        )
        return created_channel, True

    async def reconcile_roles(
        self,
        guild: discord.Guild,
        definitions: list[RoleDefinition] | None = None,
    ) -> tuple[dict[str, discord.Role], list[str], list[str], list[str]]:
        """Reconcile all specified roles against the guild.

        Args:
            guild: The Discord guild.
            definitions: List of RoleDefinitions to reconcile (default: ALL_ROLES).

        Returns:
            A tuple of (role_map, created_names, existing_names, errors).
        """
        if definitions is None:
            definitions = ALL_ROLES

        role_map: dict[str, discord.Role] = {}
        created_names: list[str] = []
        existing_names: list[str] = []
        errors: list[str] = []

        for defn in definitions:
            try:
                role, created = await self.get_or_create_role(guild, defn)
                role_map[defn.name] = role
                if created:
                    created_names.append(defn.name)
                else:
                    existing_names.append(defn.name)
            except discord.Forbidden:
                err = f"Permission denied creating/editing role '{defn.name}'"
                log_action(
                    log,
                    action="reconcile_role",
                    result="forbidden",
                    guild_id=guild.id,
                    role=defn.name,
                    level=logging.ERROR,
                )
                errors.append(err)
            except discord.HTTPException as exc:
                err = f"Discord HTTP error with role '{defn.name}': {exc.text}"
                log_action(
                    log,
                    action="reconcile_role",
                    result="http_error",
                    guild_id=guild.id,
                    role=defn.name,
                    error=str(exc),
                    level=logging.ERROR,
                )
                errors.append(err)

        return role_map, created_names, existing_names, errors

    async def reconcile_categories_and_channels(
        self,
        guild: discord.Guild,
        structure: list[CategoryDefinition] | None = None,
    ) -> tuple[
        dict[str, discord.CategoryChannel],
        list[str],
        list[str],
        list[str],
        list[str],
        list[str],
    ]:
        """Reconcile categories and channels according to the structure.

        Args:
            guild: The Discord guild.
            structure: Server structure definition (default: SERVER_STRUCTURE).

        Returns:
            A tuple of (cat_map, cats_created, cats_existing,
            chans_created, chans_existing, errors).
        """
        if structure is None:
            structure = SERVER_STRUCTURE

        cat_map: dict[str, discord.CategoryChannel] = {}
        cats_created: list[str] = []
        cats_existing: list[str] = []
        chans_created: list[str] = []
        chans_existing: list[str] = []
        errors: list[str] = []

        for cat_def in structure:
            try:
                category, cat_is_new = await self.get_or_create_category(guild, cat_def)
                cat_map[cat_def.name] = category
                if cat_is_new:
                    cats_created.append(cat_def.display_name)
                else:
                    cats_existing.append(cat_def.display_name)
            except discord.Forbidden:
                err = f"Permission denied creating category '{cat_def.display_name}'"
                errors.append(err)
                continue
            except discord.HTTPException as exc:
                err = f"HTTP error creating category '{cat_def.display_name}': {exc.text}"
                errors.append(err)
                continue

            for ch_name in cat_def.channels:
                try:
                    _, ch_is_new = await self.get_or_create_text_channel(
                        guild=guild,
                        name=ch_name,
                        category=category,
                    )
                    if ch_is_new:
                        chans_created.append(ch_name)
                    else:
                        chans_existing.append(ch_name)
                except discord.Forbidden:
                    err = (
                        f"Permission denied creating channel '{ch_name}' in "
                        f"'{cat_def.display_name}'"
                    )
                    errors.append(err)
                except discord.HTTPException as exc:
                    err = f"HTTP error creating channel '{ch_name}': {exc.text}"
                    errors.append(err)

        return cat_map, cats_created, cats_existing, chans_created, chans_existing, errors

    async def reconcile_server_structure(
        self,
        guild: discord.Guild,
    ) -> ReconciliationReport:
        """Run complete idempotent reconciliation of the server structure.

        Verifies and creates missing roles, categories, and channels according to
        the DSAI Club specification.

        Args:
            guild: The Discord guild.

        Returns:
            A ``ReconciliationReport`` summarizing all actions taken.
        """
        log_action(log, action="reconcile_server_structure", result="start", guild_id=guild.id)

        report = ReconciliationReport()

        # 1. Reconcile roles
        (
            _,
            report.roles_created,
            report.roles_existing,
            role_errors,
        ) = await self.reconcile_roles(guild)
        report.errors.extend(role_errors)

        # 2. Reconcile categories and channels
        (
            _,
            report.categories_created,
            report.categories_existing,
            report.channels_created,
            report.channels_existing,
            struct_errors,
        ) = await self.reconcile_categories_and_channels(guild)
        report.errors.extend(struct_errors)

        log_action(
            log,
            action="reconcile_server_structure",
            result="finished",
            guild_id=guild.id,
            roles_verified=report.total_roles,
            categories_verified=report.total_categories,
            channels_verified=report.total_channels,
            created_count=report.total_created,
            error_count=len(report.errors),
        )

        return report

    def verify_server_structure(
        self,
        guild: discord.Guild,
    ) -> VerificationReport:
        """Verify the current state of the guild against expected specifications.

        Does not modify the guild.

        Args:
            guild: The Discord guild to inspect.

        Returns:
            A ``VerificationReport`` detailing any missing or misplaced resources.
        """
        # 1. Check roles
        existing_role_names = {r.name for r in guild.roles}
        existing_role_bases = {_strip_emoji_prefix(r.name) for r in guild.roles}

        missing_roles: list[str] = []
        for defn in ALL_ROLES:
            if (
                defn.name not in existing_role_names
                and _strip_emoji_prefix(defn.name) not in existing_role_bases
            ):
                missing_roles.append(defn.name)

        # 2. Check categories
        existing_cats = {cat.name: cat for cat in guild.categories}
        missing_categories: list[str] = []
        cat_lookup: dict[str, discord.CategoryChannel] = {}

        for cat_def in SERVER_STRUCTURE:
            found_cat: discord.CategoryChannel | None = None
            target_display = cat_def.display_name
            target_base = cat_def.name

            for name, cat in existing_cats.items():
                if _normalize_name(name) in (
                    _normalize_name(target_display),
                    _normalize_name(target_base),
                ):
                    found_cat = cat
                    break

            if found_cat is None:
                missing_categories.append(target_display)
            else:
                cat_lookup[cat_def.name] = found_cat

        # 3. Check channels & their categories
        missing_channels: list[str] = []
        misplaced_channels: list[tuple[str, str, str]] = []

        for cat_def in SERVER_STRUCTURE:
            expected_cat = cat_lookup.get(cat_def.name)

            for ch_name in cat_def.channels:
                target_norm = _normalize_name(ch_name)
                target_base = _strip_emoji_prefix(ch_name)

                matched_channel: discord.TextChannel | None = None
                for ch in guild.text_channels:
                    ch_norm = _normalize_name(ch.name)
                    if ch_norm == target_norm or _strip_emoji_prefix(ch.name) == target_base:
                        matched_channel = ch
                        break

                if matched_channel is None:
                    missing_channels.append(ch_name)
                elif expected_cat is not None and matched_channel.category_id != expected_cat.id:
                    actual_cat = (
                        matched_channel.category.name if matched_channel.category else "None"
                    )
                    misplaced_channels.append((ch_name, actual_cat, expected_cat.name))

        is_complete = not (
            missing_roles or missing_categories or missing_channels or misplaced_channels
        )

        return VerificationReport(
            is_complete=is_complete,
            missing_roles=missing_roles,
            missing_categories=missing_categories,
            missing_channels=missing_channels,
            misplaced_channels=misplaced_channels,
        )

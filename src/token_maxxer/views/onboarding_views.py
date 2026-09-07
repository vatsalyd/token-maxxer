"""Onboarding views and persistent interactive components for token-maxxer.

Provides interactive role selection views and UI components for newcomer onboarding.
"""

from __future__ import annotations

import discord
from discord import ui

from token_maxxer.utils.constants import INTEREST_ROLES, ROLE_ALUMNI, ROLE_MEMBER
from token_maxxer.utils.helpers import error_embed, info_embed, success_embed
from token_maxxer.utils.logging import get_logger, log_action

log = get_logger(__name__)


class RoleSelectDropdown(ui.Select):
    """Multi-select dropdown for assigning technical interest roles."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=r.name,
                value=r.name,
                description=f"Focus group and discussions for {r.name}",
            )
            for r in INTEREST_ROLES
        ]
        super().__init__(
            placeholder="🎯 Select your technical interests...",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="token_maxxer:onboarding:interest_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle role selection updates."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        guild = interaction.guild
        selected_names = set(self.values)

        added: list[str] = []
        already_had: list[str] = []
        errors: list[str] = []

        for role_name in selected_names:
            role = discord.utils.get(guild.roles, name=role_name)
            if role is None:
                errors.append(f"Role `{role_name}` not found in server.")
                continue

            if role in member.roles:
                already_had.append(role_name)
            else:
                try:
                    await member.add_roles(role, reason="Self-assigned interest role")
                    added.append(role_name)
                except discord.Forbidden:
                    errors.append(f"Missing permissions to add `{role_name}`.")

        # Ensure user also has the base Member role
        member_role = discord.utils.get(guild.roles, name=ROLE_MEMBER)
        if member_role and member_role not in member.roles:
            try:
                await member.add_roles(member_role, reason="Auto-assigned base member role")
            except discord.Forbidden:
                pass

        # Build response embed
        lines: list[str] = []
        if added:
            lines.append(f"✅ **Added roles:** {', '.join(added)}")
        if already_had:
            lines.append(f"ℹ️ **Already had:** {', '.join(already_had)}")
        if errors:
            lines.append(f"⚠️ **Issues:** {', '.join(errors)}")

        embed = success_embed(
            title="Roles Updated",
            description="\n\n".join(lines) if lines else "No changes were made.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        log_action(
            log,
            action="self_assign_roles",
            guild_id=guild.id,
            user_id=member.id,
            added=len(added),
        )


class RoleSelectionView(ui.View):
    """Persistent interactive view for self-service role selection in #🎭・roles."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(RoleSelectDropdown())

    @ui.button(
        label="Claim Member Role",
        style=discord.ButtonStyle.primary,
        custom_id="token_maxxer:onboarding:claim_member",
        emoji="👤",
    )
    async def claim_member_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Allow newcomers to claim the Member role if not yet granted."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        guild = interaction.guild
        member_role = discord.utils.get(guild.roles, name=ROLE_MEMBER)

        if member_role is None:
            err = error_embed(
                title="Role Not Found",
                description=f"`{ROLE_MEMBER}` does not exist yet. Please ask an admin to run `/setup`.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)
            return

        if member_role in member.roles:
            info = info_embed(
                title="Already a Member",
                description=f"You already hold the {member_role.mention} role! Welcome to the club.",
            )
            await interaction.response.send_message(embed=info, ephemeral=True)
            return

        try:
            await member.add_roles(member_role, reason="Self-claimed Member role")
            resp = success_embed(
                title="Welcome to the DSAI Club!",
                description=(
                    f"🎉 You have received the {member_role.mention} role!\n\n"
                    "You now have access to general club discussions, study groups, and project channels. "
                    "Make sure to pick your technical focus roles from the dropdown above!"
                ),
            )
            await interaction.response.send_message(embed=resp, ephemeral=True)
        except discord.Forbidden:
            err = error_embed(
                title="Permission Denied",
                description="The bot lacks permissions to grant the Member role. Please contact an admin.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)

    @ui.button(
        label="Claim Alumni Role",
        style=discord.ButtonStyle.secondary,
        custom_id="token_maxxer:onboarding:claim_alumni",
        emoji="🎓",
    )
    async def claim_alumni_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Allow graduated club members to self-claim or toggle the Alumni role."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        guild = interaction.guild
        alumni_role = discord.utils.get(guild.roles, name=ROLE_ALUMNI)
        member_role = discord.utils.get(guild.roles, name=ROLE_MEMBER)

        if alumni_role is None:
            err = error_embed(
                title="Role Not Found",
                description=f"`{ROLE_ALUMNI}` does not exist yet. Please ask an admin to run `/setup`.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)
            return

        if alumni_role in member.roles:
            try:
                await member.remove_roles(alumni_role, reason="Self-removed Alumni role")
                resp = info_embed(
                    title="Alumni Role Removed",
                    description=f"You have surrendered the {alumni_role.mention} role.",
                )
                await interaction.response.send_message(embed=resp, ephemeral=True)
            except discord.Forbidden:
                err = error_embed(
                    title="Permission Denied",
                    description="The bot lacks permissions to remove the Alumni role.",
                )
                await interaction.response.send_message(embed=err, ephemeral=True)
            return

        roles_to_add = [alumni_role]
        if member_role and member_role not in member.roles:
            roles_to_add.append(member_role)

        try:
            await member.add_roles(*roles_to_add, reason="Self-claimed Alumni role")
            resp = success_embed(
                title="Welcome, Club Alum! 🎓",
                description=(
                    f"🎉 You have received the {alumni_role.mention} role!\n\n"
                    "You are recognized as a valued club veteran and have access to our community "
                    "as well as `#🎓・alumni-network` to connect and mentor current students."
                ),
            )
            await interaction.response.send_message(embed=resp, ephemeral=True)
        except discord.Forbidden:
            err = error_embed(
                title="Permission Denied",
                description="The bot lacks permissions to assign the Alumni role. Please contact an admin.",
            )
            await interaction.response.send_message(embed=err, ephemeral=True)

    @ui.button(
        label="Clear My Interest Roles",
        style=discord.ButtonStyle.secondary,
        custom_id="token_maxxer:onboarding:clear_interests",
        emoji="🧹",
    )
    async def clear_interests_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Remove all technical interest roles from the user."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        guild = interaction.guild
        removed: list[str] = []

        for r_def in INTEREST_ROLES:
            role = discord.utils.get(guild.roles, name=r_def.name)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Self-cleared interest role")
                    removed.append(r_def.name)
                except discord.Forbidden:
                    pass

        if removed:
            resp = success_embed(
                title="Interest Roles Cleared",
                description=f"Removed: {', '.join(removed)}.\nYou can re-select any roles at any time using the dropdown.",
            )
        else:
            resp = info_embed(
                title="No Roles to Remove",
                description="You do not currently have any technical interest roles assigned.",
            )

        await interaction.response.send_message(embed=resp, ephemeral=True)

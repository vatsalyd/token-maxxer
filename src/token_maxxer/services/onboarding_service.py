"""Onboarding service for token-maxxer.

Generates authoritative club embeds and populates START HERE channels with
rules, welcome instructions, server navigation, and persistent role pickers.
"""

from __future__ import annotations

import contextlib

import discord

from token_maxxer.utils.constants import (
    CHANNEL_PROJECT_DISCUSSIONS,
    CHANNEL_PROJECT_HUB,
    INTEREST_ROLES,
    ROLE_ADMIN,
    ROLE_COORDINATOR,
    ROLE_CORE_MEMBER,
    ROLE_MEMBER,
    ROLE_PROJECT_LEAD,
)
from token_maxxer.utils.helpers import make_embed
from token_maxxer.utils.logging import get_logger, log_action
from token_maxxer.views.onboarding_views import RoleSelectionView

log = get_logger(__name__)


class OnboardingService:
    """Service managing channel content and newcomer onboarding flows."""

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot

    # ─── Embed Builders ───────────────────────────────────────────────────────

    def build_rules_embed(self) -> discord.Embed:
        """Build the authoritative Code of Conduct embed for #📜・rules."""
        embed = make_embed(
            title="📜 Data Science & AI Club — Rules & Code of Conduct",
            description=(
                "Welcome to the **Data Science and Artificial Intelligence Club** workspace!\n\n"
                "To foster an inclusive, intellectually stimulating, and collaborative environment, "
                "all members must adhere to these guidelines. By participating in this server, "
                "you agree to uphold these standards."
            ),
            color=discord.Color.from_str("#E0245E"),
        )

        embed.add_field(
            name="1. 🤝 Respect & Professionalism",
            value=(
                "Treat all peers, mentors, and collaborators with respect. Harassment, discrimination, "
                "derogatory remarks, condescending attitudes, or personal attacks will not be tolerated."
            ),
            inline=False,
        )
        embed.add_field(
            name="2. 🎓 Academic & Intellectual Integrity",
            value=(
                "Plagiarism and dishonesty are strictly forbidden. When referencing external code, research, "
                "or datasets, provide proper attribution. Disclose AI assistance where expected in club submissions."
            ),
            inline=False,
        )
        embed.add_field(
            name="3. 💡 Constructive Collaboration & Sharing",
            value=(
                "Encourage beginner questions. No question is too basic in `#❓・help-desk`. "
                "Provide actionable, polite peer feedback in `#👀・code-review`."
            ),
            inline=False,
        )
        embed.add_field(
            name="4. 🚀 Project Channel Etiquette",
            value=(
                "Dynamic project channels are reserved for active project development. Keep discussions focused. "
                f"Casual questions or suggestions for a project belong in `{CHANNEL_PROJECT_DISCUSSIONS}`."
            ),
            inline=False,
        )
        embed.add_field(
            name="5. 🚫 No Spam, Scams, or Self-Promotion",
            value=(
                "Do not post unsolicited commercial advertisements, third-party promotional campaigns, "
                "or spam member DMs. Share relevant open-source tools or personal tech projects in `#📚・resources`."
            ),
            inline=False,
        )
        embed.add_field(
            name="6. 🔐 Confidentiality & Security",
            value=(
                "Never share API keys, private tokens, passwords, or internal club credentials in public channels. "
                "Respect shared cloud resources and institutional compute limits."
            ),
            inline=False,
        )

        embed.set_footer(
            text="DSAI Club • Guidelines apply to all channels, threads, and project workspaces."
        )
        return embed

    def build_welcome_embed(self) -> discord.Embed:
        """Build the official welcome and mission statement embed for #👋・welcome."""
        embed = make_embed(
            title="👋 Welcome to the DSAI Club!",
            description=(
                "We are the premier student-led technical community for **Machine Learning, "
                "Deep Learning, LLMs, AI Agents, and Software Systems**.\n\n"
                "Whether you're training your first model, deploying enterprise pipelines, "
                "or writing your next research paper — you belong here."
            ),
            color=discord.Color.from_str("#00BCD4"),
        )

        embed.add_field(
            name="🎯 Our Mission",
            value=(
                "• **Build Production Systems**: Build hands-on, high-impact open source projects.\n"
                "• **Democratize Knowledge**: Demystify cutting-edge AI through workshops & study groups.\n"
                "• **Collaborate & Win**: Form teams for hackathons, competitions, and research challenges."
            ),
            inline=False,
        )

        embed.add_field(
            name="🚀 Quick Start Checklist (3 Steps)",
            value=(
                "1. **Read the Rules**: Check `#📜・rules` to understand community expectations.\n"
                "2. **Pick Your Interests**: Go to `#🎭・roles` to select your tech domains and claim your Member role.\n"
                "3. **Introduce Yourself**: Say hello in `#💬・general` and tell us what you're currently building or learning!"
            ),
            inline=False,
        )

        embed.add_field(
            name="📌 Key Starting Points",
            value=(
                f"• Announcements & Schedule: `#📢・announcements` & `#📅・events`\n"
                f"• Explore Active Projects: `{CHANNEL_PROJECT_HUB}`\n"
                f"• Server Roadmap & Commands: `#🧭・server-guide`"
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club • Innovating with Intelligence")
        return embed

    def build_server_guide_embed(self) -> discord.Embed:
        """Build the server navigation directory embed for #🧭・server-guide."""
        embed = make_embed(
            title="🧭 Server Navigation & Workspace Guide",
            description=(
                "Here is your roadmap to navigating channels, finding projects, and leveraging bot commands."
            ),
            color=discord.Color.from_str("#4CAF50"),
        )

        embed.add_field(
            name="🏠 START HERE",
            value=(
                "`#📜・rules` — Official community guidelines & code of conduct.\n"
                "`#👋・welcome` — Mission statement & newcomer orientation.\n"
                "`#🧭・server-guide` — This navigation index & command cheat sheet.\n"
                "`#🎭・roles` — Interactive role self-assignment for tech domains."
            ),
            inline=False,
        )

        embed.add_field(
            name="📢 CLUB",
            value=(
                "`#📢・announcements` — Official club updates and news.\n"
                "`#📅・events` — Workshops, hackathons, and tech talks.\n"
                "`#📝・meeting-notes` — Summaries of core team and general meetings.\n"
                "`#📚・resources` — Shared articles, cheat sheets, and tool links."
            ),
            inline=False,
        )

        embed.add_field(
            name="🚀 PROJECTS",
            value=(
                f"`{CHANNEL_PROJECT_HUB}` — Dynamic project cards & milestone updates.\n"
                "`#💡・project-ideas` — Pitch concepts and gather feedback.\n"
                "`#🧩・team-formation` — Find teammates for projects and hackathons.\n"
                f"`{CHANNEL_PROJECT_DISCUSSIONS}` — Public discussions about active projects.\n"
                "`#🏆・project-showcase` — Demos, release announcements, and presentations."
            ),
            inline=False,
        )

        embed.add_field(
            name="🧠 LEARNING",
            value=(
                "`#💬・technical-discussion` — Deep-dives into papers, models, and architectures.\n"
                "`#❓・help-desk` — Debugging assistance and troubleshooting.\n"
                "`#👀・code-review` — Peer review for PRs, scripts, and repositories.\n"
                "`#📚・learning-resources` — Curated courses, tutorials, and textbooks."
            ),
            inline=False,
        )

        embed.add_field(
            name="💬 COMMUNITY",
            value=(
                "`#💬・general` — Main chat for daily conversation.\n"
                "`#😂・memes` — AI, tech, and developer humor.\n"
                "`#🎮・off-topic` — Gaming, music, hobbies, and casual talk."
            ),
            inline=False,
        )

        embed.add_field(
            name="🤖 Slash Command Cheat Sheet",
            value=(
                "`/project list` — View all registered club projects with status filter.\n"
                "`/project info <name>` — View team members, GitHub repo, tech stack, and deadlines.\n"
                "`/project create` — Launch an interactive project creation modal (Admins/Leads).\n"
                "`/project update <name>` — Post a structured milestone update.\n"
                "`/team list <name>` — View active collaborators on any project.\n"
                "`/ping` & `/botinfo` — Bot latency, uptime, and system health."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club • Keep this guide handy for quick reference.")
        return embed

    def build_roles_embed(self) -> discord.Embed:
        """Build the role self-assignment embed for #🎭・roles."""
        embed = make_embed(
            title="🎭 Technical Interest & Role Selection",
            description=(
                "Customize your server notifications and profile! Choose the technical focus areas "
                "you are interested in or actively working on.\n\n"
                "**How to use:**\n"
                "1. Click the **dropdown menu below** to select your technical interests.\n"
                "2. Click **Claim Member Role** if you are new and don't have base access yet.\n"
                "3. You can update your selections or clear them at any time."
            ),
            color=discord.Color.from_str("#9C27B0"),
        )

        role_descriptions = [
            f"{r.name} — Focused updates on {r.name.split()[-1]} discussions and initiatives."
            for r in INTEREST_ROLES
        ]
        embed.add_field(
            name="Available Interest Roles",
            value="\n".join(f"• {desc}" for desc in role_descriptions),
            inline=False,
        )

        embed.add_field(
            name="Role Hierarchy Note",
            value=(
                f"• `{ROLE_MEMBER}`: Standard access for all club members.\n"
                f"• `{ROLE_PROJECT_LEAD}`: Assigned dynamically when leading a project.\n"
                f"• `{ROLE_CORE_MEMBER}`, `{ROLE_COORDINATOR}`, `{ROLE_ADMIN}`: Operational club leadership."
            ),
            inline=False,
        )

        embed.set_footer(text="DSAI Club • Self-service role assignment powered by token-maxxer.")
        return embed

    def build_welcome_greeting_embed(self, member: discord.Member) -> discord.Embed:
        """Build a personalized greeting card embed when a new member joins the server."""
        embed = make_embed(
            title=f"🎉 Welcome to the DSAI Club, {member.display_name}!",
            description=(
                f"Hey {member.mention}, welcome to the official **Data Science and AI Club** workspace!\n\n"
                "We are thrilled to have you with us. Here's how to get onboarded in under a minute:"
            ),
            color=discord.Color.from_str("#00BCD4"),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="1. 📜 Review the Rules",
            value="Familiarize yourself with our `#📜・rules` for academic and project integrity.",
            inline=False,
        )
        embed.add_field(
            name="2. 🎭 Select Your Interests",
            value="Head over to `#🎭・roles` to grab your technical focus roles (Python, ML, LLMs, etc.).",
            inline=False,
        )
        embed.add_field(
            name="3. 💬 Say Hello",
            value="Drop a line in `#💬・general` and let us know what you're working on or hoping to learn!",
            inline=False,
        )

        embed.set_footer(text=f"Member #{member.guild.member_count} • DSAI Club")
        return embed

    # ─── Channel Population ───────────────────────────────────────────────────

    async def _clean_and_post(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View | None = None,
    ) -> bool:
        """Purge previous bot messages in a channel and post the updated embed."""
        try:
            # Delete previous messages sent by the bot
            async for msg in channel.history(limit=50):
                if msg.author.id == self.bot.user.id:
                    with contextlib.suppress(discord.HTTPException):
                        await msg.delete()

            # Post the fresh embed
            if view is not None:
                await channel.send(embed=embed, view=view)
            else:
                await channel.send(embed=embed)
            return True
        except discord.Forbidden:
            log.warning("Permission denied writing to channel %s", channel.name)
            return False
        except discord.HTTPException as exc:
            log.warning("HTTP error writing to channel %s: %s", channel.name, exc)
            return False

    async def populate_start_here_channels(
        self,
        guild: discord.Guild,
    ) -> tuple[int, list[str]]:
        """Populate all four START HERE channels with authoritative embeds and components.

        Returns:
            A tuple of ``(success_count, error_messages)``.
        """
        targets = [
            ("📜・rules", self.build_rules_embed(), None),
            ("👋・welcome", self.build_welcome_embed(), None),
            ("🧭・server-guide", self.build_server_guide_embed(), None),
            ("🎭・roles", self.build_roles_embed(), RoleSelectionView()),
        ]

        success_count = 0
        errors: list[str] = []

        for ch_name, embed, view in targets:
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if channel is None:
                err = f"Channel '{ch_name}' not found. Run `/setup` first to create it."
                errors.append(err)
                continue

            success = await self._clean_and_post(channel, embed, view)
            if success:
                success_count += 1
                log_action(
                    log,
                    action="populate_channel",
                    result="success",
                    guild_id=guild.id,
                    channel=ch_name,
                )
            else:
                errors.append(f"Failed to post to '{ch_name}' (permission denied or HTTP error).")

        return success_count, errors

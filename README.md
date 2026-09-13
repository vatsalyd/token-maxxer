# token-maxxer

> Internal Discord workspace and lightweight project-management bot for the DSAI Club.

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-blue.svg)](https://github.com/Rapptz/discord.py)
[![Tests](https://img.shields.io/badge/tests-47%20passed-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-ruff-black.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Server Architecture & Roles](#server-architecture--roles)
- [Permission Architecture](#permission-architecture)
- [Slash Commands Reference](#slash-commands-reference)
- [Architecture & Design](#architecture--design)
- [Installation & Quick Start](#installation--quick-start)
- [Testing](#testing)
- [Production Deployment (Render)](#production-deployment-render)
- [Disaster Recovery & Operational Safety](#disaster-recovery--operational-safety)

---

## Overview

`token-maxxer` turns the DSAI Club Discord server into a structured collaboration workspace. Instead of forcing club members into external project-management applications, Discord remains the primary user interface. `token-maxxer` handles administrative provisioning, role and channel synchronization, team rosters, and project lifecycle tracking behind the scenes.

---

## Key Features

- **Automated Workspace Provisioning**: Creates standardized categories and channels with a single command or interactive modal.
- **Least-Privilege Security**: All club members can discover and read project workspaces, but only assigned team members and leadership can send messages or post work.
- **Idempotent Reconciliation**: The `/setup` command safely verifies and provisions roles, categories, and channels without creating duplicates or clobbering existing configuration.
- **Live Project Hub Dashboard**: Project announcements in `#📌・project-hub` update in real time with progress bars, team size, lead info, and status transitions.
- **Lifecycle Management & Safe Deletion**: Projects transition smoothly through `IDEA` → `ACTIVE` → `COMPLETED` → `ARCHIVED`. Safe archiving locks channels to read-only, while `/project delete` provides interactive confirmation before cascading deletion of DB entries and channels.
- **Newcomer Onboarding & Role Sync**: Interactive self-service role selector with interest tags, member and alumni claim buttons, automated welcome greetings, and background member role reconciliation.
- **Core Team Developer Guide**: Built-in 7-section operational manual published directly to `#🤖・bot-guide` via `/guide publish`.
- **Asynchronous SQLite Persistence**: Powered by `aiosqlite` with WAL mode and foreign key cascades for high performance and reliability.
- **Interactive Discord Modals & Views**: Native forms for project creation, weekly progress logs, and safety confirmation prompts.

---

## Server Architecture & Roles

The bot provisions a standardized role hierarchy and permanent channel structure:

### Role Hierarchy (Precedence Order)

1. **👑 Club Admin**: Highest internal leadership authority. Full management permissions.
2. **⚡ Coordinator**: Active club coordinators. Can run `/setup`, manage channels, and organize activities.
3. **🔧 Core Member**: Active core team members. Elevated communication and project creation rights.
4. **🚀 Project Lead**: Dynamic title granted to leaders of active projects. Automatically assigned and revoked on leadership transfer.
5. **🎓 Alumni**: Dedicated recognition and community channel for club graduates and mentors.
6. **👤 Member**: General club member. Can read all workspaces and participate in public discussions.

### Interest Roles (Self-Selectable)
- 🐍 Python
- 🤖 Machine Learning
- 🧠 Deep Learning
- ✨ LLMs
- 🔗 AI Agents
- 📊 Data Science
- 💻 Software Engineering
- 🎨 Design

### Standard Server Structure
```text
🏠 START HERE
├── 📜・rules
├── 👋・welcome
├── 🧭・server-guide
└── 🎭・roles

📢 CLUB
├── 📢・announcements
├── 📅・events
├── 📝・meeting-notes
└── 📚・resources

🚀 PROJECTS
├── 📌・project-hub
├── 💡・project-ideas
├── 🧩・team-formation
├── 💬・project-discussion
└── 🏆・project-showcase

🧠 LEARNING
├── 💬・technical-discussion
├── ❓・help-desk
├── 👀・code-review
└── 📚・learning-resources

💬 COMMUNITY
├── 💬・general
├── 🎓・alumni-network
├── 😂・memes
└── 🎮・off-topic

🔐 CORE TEAM (Restricted)
├── 💭・internal
├── 📋・planning
├── 📊・project-tracking
├── 📝・tasks
└── 🤖・bot-guide
```

---

## Permission Architecture

`token-maxxer` enforces the principle of least privilege:

| Channel Type | @everyone / Member | Project Team Member | Project Lead | Core Team / Admin |
|---|---|---|---|---|
| **Public Information** | Read-Only | Read-Only | Read-Only | Post & Manage |
| **Community Discussion**| Read & Write | Read & Write | Read & Write | Post & Manage |
| **Project Workspaces** | **Read-Only** | **Read & Write** | **Read, Write, Threads** | Post & Manage |
| **Archived Workspaces** | Read-Only | **Read-Only** | **Read-Only** | Manage |
| **Core Team** | *Hidden* | *Hidden* | *Hidden* | Full Access |

---

## Slash Commands Reference

### 🛠️ Setup & Maintenance
- `/setup [verify_only]` — *(Coordinator / Admin)* Idempotently reconcile all roles, categories, and channels. If `verify_only=True`, reports discrepancies without making modifications.

### 🚀 Projects (`/project`)
- `/project create` — Opens an interactive modal (Name, Description, Tech Stack, Deadline) and provisions workspace channels and announcement.
- `/project list [status]` — Lists club projects with optional lifecycle status filter (`IDEA`, `ACTIVE`, `COMPLETED`, `ARCHIVED`).
- `/project info <project>` — Detailed card with tech stack, team roster, workspace channel links, and recent update history.
- `/project update <project>` — Opens an interactive modal to submit structured progress updates (completed, blockers, next steps). Automatically syncs the live announcement card in `#📌・project-hub`.
- `/project status <project> <new_status>` — *(Lead / Core / Admin)* Transitions project lifecycle state (`IDEA` → `ACTIVE` → `COMPLETED` → `ARCHIVED`). Automatically updates live dashboard card in `#📌・project-hub`.
- `/project deadline <project> [deadline]` — Views current deadline or sets a target completion date. Automatically updates live dashboard card in `#📌・project-hub`.
- `/project archive <project> [force]` — Safely archives a project workspace, locking channels to read-only and preserving history.
- `/project delete <project>` — *(Admin / Coordinator)* Permanently deletes a project workspace and cascades database removal. Prompts an interactive safety confirmation dialog before deleting Discord channels and records.

### 👥 Teams (`/team`)
- `/team add <project> <member>` — Adds a member to the project and grants workspace write permissions.
- `/team remove <project> <member>` — Removes a member from the project and revokes workspace write permissions.
- `/team list <project>` — Displays the current project roster with roles and join dates.
- `/team transfer-lead <project> <new_lead>` — *(Lead / Admin)* Transfers project leadership to another team member, dynamically updating the `🚀 Project Lead` role.

### 🧭 Onboarding (`/onboard`)
- `/onboard setup` — *(Coordinator / Admin)* Bulk purges old bot messages and populates `#📜・rules`, `#👋・welcome`, `#🧭・server-guide`, and `#🎭・roles` with authoritative embeds and persistent role-picker components.
- `/onboard sync-members` — *(Coordinator / Admin)* Scans all guild members and assigns the `👤 Member` role to anyone missing it. Automatically runs at bot startup as well.
- `/onboard test-welcome [member]` — *(Coordinator / Admin)* Dispatches a test welcome greeting card to `#👋・welcome`.

### 📖 Internal Documentation (`/guide`)
- `/guide publish` — *(Core / Coordinator / Admin)* Purges and publishes the full 7-section core developer and operations manual to the private `#🤖・bot-guide` channel.
- `/guide view [section]` — *(Core / Coordinator / Admin)* Ephemerally inspects any specific manual section (`overview`, `governance`, `onboarding`, `projects`, `teams`, `developer`, `troubleshooting`).

### ℹ️ Utility
- `/ping` — Checks Discord gateway and API latency.
- `/botinfo` — Displays bot version, uptime, guild count, and runtime environment.

---

## Architecture & Design

`token-maxxer` follows clean layered architecture:

```text
Discord Interactions (UI)
        │
        ▼
   Cogs Layer          [src/token_maxxer/cogs/]
   (Commands, Modals, Autocompletes)
        │
        ▼
  Services Layer       [src/token_maxxer/services/]
  (GuildService, PermissionService, ProjectService, TeamService)
        │
        ▼
  Database Layer       [src/token_maxxer/database/]
  (aiosqlite Connection Pool, Typed Dataclass Models, Schema Migrations)
```

- **Separation of Concerns**: Cogs handle input parsing and UI interactions; Services encapsulate business logic and Discord API calls; Database layer isolates persistence.
- **Atomic Operations & Rollback**: In `ProjectService`, if Discord channel creation fails mid-process, created resources are cleaned up to prevent orphaned categories.

---

## Installation & Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Git
- A Discord Bot Application token with **Server Members** and **Message Content** intents enabled.

### Local Setup

```powershell
# 1. Clone the repository
git clone https://github.com/vatsalyd/token-maxxer.git
cd token-maxxer

# 2. Create and activate a virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install production and development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff

# 4. Configure environment variables
cp .env.example .env
# Edit .env:
# DISCORD_TOKEN=your_bot_token_here
# TARGET_GUILD_ID=your_discord_guild_id
# LOG_LEVEL=INFO

# 5. Run the bot
python -m token_maxxer.bot
```

---

## Testing

The test suite contains 47 automated tests covering database operations, permission overrides, project lifecycle flows, live hub sync, cascade deletion, member role sync, guide publishing, and setup idempotency.

```powershell
# Run the test suite
pytest tests/

# Run tests with verbose output
pytest tests/ -v

# Run linter
ruff check src/ tests/
```

---

## Production Deployment (Render)

When continuous 24/7 uptime is required, `token-maxxer` deploys on **Render** as a **Background Worker**:

1. **Create a Background Worker**:
   - Repository: `vatsalyd/token-maxxer`
   - Branch: `main`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m token_maxxer.bot`
2. **Configure Persistent Disk**:
   - Mount Path: `/var/data`
   - Environment Variable: `DATABASE_PATH=/var/data/token_maxxer.db`
3. **Configure Environment Variables**:
   - `DISCORD_TOKEN`: Your production bot token.
   - `TARGET_GUILD_ID`: Your target Discord guild ID.
   - `LOG_LEVEL`: `INFO`

---

## Disaster Recovery & Operational Safety

- **WAL Mode**: SQLite is configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) for maximum concurrency and resilience against unexpected shutdowns.
- **Foreign Key Constraints**: Foreign keys are enforced (`PRAGMA foreign_keys = ON;`) with cascading deletions.
- **Idempotent Repair**: If Discord roles or channels are accidentally deleted or corrupted, running `/setup` automatically restores the structure without duplicating existing data.
- **Database Backup**: Periodic backups of the `.db` file can be scheduled via cron or backup scripts.

---

## License

Private — DSAI Club internal use only.

# token-maxxer

> Internal Discord workspace and lightweight project-management bot for the DSAI Club.

## Overview

`token-maxxer` is a private Discord bot that turns the DSAI Club's Discord server into a structured collaboration workspace:

- **Project workspaces** — auto-provisioned channels with correct permissions
- **Team management** — add/remove members, transfer leads
- **Project lifecycle** — Idea → Active → Completed → Archived
- **Server setup** — idempotent `/setup` command to provision roles, categories, and channels

## Tech Stack

- Python 3.12+
- discord.py 2.x
- SQLite (via aiosqlite)

## Quick Start

```powershell
# Clone & setup
git clone https://github.com/vatsalyd/token-maxxer.git
cd token-maxxer

# Create virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your bot token and guild ID

# Run
$env:PYTHONPATH="src"
python -m token_maxxer.bot
```

## Project Structure

```
token-maxxer/
├── src/token_maxxer/
│   ├── bot.py            # Bot entry point
│   ├── config/           # Settings & environment
│   ├── cogs/             # Slash command handlers
│   ├── services/         # Business logic
│   ├── database/         # SQLite persistence
│   ├── views/            # Discord UI components
│   └── utils/            # Constants, helpers, logging
├── tests/                # Unit & integration tests
├── data/                 # SQLite database (gitignored)
└── requirements.txt
```

## License

Private — DSAI Club internal use only.

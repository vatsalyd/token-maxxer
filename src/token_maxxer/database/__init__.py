"""Database package for token-maxxer.

Provides SQLite database connectivity and type-safe data models.
"""

from token_maxxer.database.db import Database, db
from token_maxxer.database.models import (
    Project,
    ProjectChannel,
    ProjectMember,
    ProjectUpdate,
)

__all__ = [
    "Database",
    "Project",
    "ProjectChannel",
    "ProjectMember",
    "ProjectUpdate",
    "db",
]

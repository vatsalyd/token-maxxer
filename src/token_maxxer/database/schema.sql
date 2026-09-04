-- SQLite schema for token-maxxer database.
-- Enforces foreign keys and cascades.

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tech_stack TEXT,
    lead_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    category_id INTEGER,
    created_at TEXT NOT NULL,
    archived_at TEXT,
    deadline TEXT
);

CREATE TABLE IF NOT EXISTS project_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TEXT NOT NULL,
    UNIQUE(project_id, user_id),
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    channel_type TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    UNIQUE(project_id, channel_type),
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    completed TEXT,
    working_on TEXT,
    blocked_by TEXT,
    next_steps TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_projects_guild_status ON projects(guild_id, status);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id);
CREATE INDEX IF NOT EXISTS idx_project_channels_project ON project_channels(project_id);
CREATE INDEX IF NOT EXISTS idx_project_updates_project ON project_updates(project_id);

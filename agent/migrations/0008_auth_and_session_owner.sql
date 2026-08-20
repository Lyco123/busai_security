ALTER TABLE agent_sessions ADD COLUMN owner_id TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_sessions_owner_id ON agent_sessions(owner_id);

CREATE TABLE IF NOT EXISTS agent_users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password TEXT NOT NULL,
  role TEXT NOT NULL,
  display_name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_auth_sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_auth_sessions_user_id ON agent_auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_auth_sessions_expires_at ON agent_auth_sessions(expires_at);

INSERT OR IGNORE INTO agent_users (id, username, password, role, display_name, enabled, created_at, updated_at)
VALUES ('user_admin', 'admin', 'admin123', 'admin', 'Admin', 1, datetime('now'), datetime('now'));

INSERT OR IGNORE INTO agent_users (id, username, password, role, display_name, enabled, created_at, updated_at)
VALUES ('user_default', 'user', 'user123', 'user', 'User', 1, datetime('now'), datetime('now'));

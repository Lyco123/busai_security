CREATE TABLE IF NOT EXISTS rule_drafts (
  session_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  mode TEXT NOT NULL,
  rule_id TEXT,
  draft TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

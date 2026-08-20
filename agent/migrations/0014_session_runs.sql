CREATE TABLE IF NOT EXISTS session_runs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  status TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'chat',
  request_content TEXT NOT NULL,
  request_metadata TEXT,
  response_json TEXT,
  error_message TEXT,
  superseded_by_run_id TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT,
  lease_expires_at TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_session_runs_session_id ON session_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_session_runs_status ON session_runs(status);
CREATE INDEX IF NOT EXISTS idx_session_runs_created_at ON session_runs(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_runs_one_running
  ON session_runs(session_id)
  WHERE status = 'running';
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_runs_one_queued
  ON session_runs(session_id)
  WHERE status = 'queued';

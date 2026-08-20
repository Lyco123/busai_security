CREATE TABLE IF NOT EXISTS agent_eval_records (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  conclusion TEXT NOT NULL,
  issue_type TEXT,
  confidence REAL,
  note TEXT,
  tags_json TEXT,
  model_version TEXT,
  scenario TEXT,
  org_group TEXT,
  org_company TEXT,
  org_fleet TEXT,
  org_line TEXT,
  referenced_message_ids_json TEXT,
  is_read INTEGER NOT NULL DEFAULT 0,
  is_favorite INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'research',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_session_id ON agent_eval_records(session_id);
CREATE INDEX IF NOT EXISTS idx_eval_conclusion ON agent_eval_records(conclusion);
CREATE INDEX IF NOT EXISTS idx_eval_issue_type ON agent_eval_records(issue_type);
CREATE INDEX IF NOT EXISTS idx_eval_model_version ON agent_eval_records(model_version);
CREATE INDEX IF NOT EXISTS idx_eval_scenario ON agent_eval_records(scenario);
CREATE INDEX IF NOT EXISTS idx_eval_created_at ON agent_eval_records(created_at);

CREATE TABLE IF NOT EXISTS agent_issues (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  issue_type TEXT,
  severity TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL,
  expected_result TEXT,
  business_impact TEXT,
  repro_steps TEXT,
  session_id TEXT NOT NULL,
  source_eval_id TEXT,
  referenced_message_ids_json TEXT,
  context_summary TEXT,
  model_version TEXT,
  scenario TEXT,
  org_group TEXT,
  org_company TEXT,
  org_fleet TEXT,
  org_line TEXT,
  assignee TEXT,
  due_at TEXT,
  submit_mode TEXT NOT NULL DEFAULT 'quick',
  source_metric_json TEXT,
  created_by TEXT,
  updated_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_issue_session_id ON agent_issues(session_id);
CREATE INDEX IF NOT EXISTS idx_issue_source_eval_id ON agent_issues(source_eval_id);
CREATE INDEX IF NOT EXISTS idx_issue_status ON agent_issues(status);
CREATE INDEX IF NOT EXISTS idx_issue_severity ON agent_issues(severity);
CREATE INDEX IF NOT EXISTS idx_issue_priority ON agent_issues(priority);
CREATE INDEX IF NOT EXISTS idx_issue_model_version ON agent_issues(model_version);
CREATE INDEX IF NOT EXISTS idx_issue_scenario ON agent_issues(scenario);
CREATE INDEX IF NOT EXISTS idx_issue_created_at ON agent_issues(created_at);

CREATE TABLE IF NOT EXISTS agent_issue_events (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL,
  action TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  note TEXT,
  operator TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_events_issue_id ON agent_issue_events(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_events_created_at ON agent_issue_events(created_at);

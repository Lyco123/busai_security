CREATE TABLE IF NOT EXISTS agent_issue_types (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  merged_into_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  created_by TEXT,
  updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_issue_types_enabled ON agent_issue_types(enabled);
CREATE INDEX IF NOT EXISTS idx_issue_types_merged_into_id ON agent_issue_types(merged_into_id);

CREATE TABLE IF NOT EXISTS agent_eval_issue_types (
  eval_id TEXT NOT NULL,
  issue_type_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (eval_id, issue_type_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_issue_types_eval_id ON agent_eval_issue_types(eval_id);
CREATE INDEX IF NOT EXISTS idx_eval_issue_types_issue_type_id ON agent_eval_issue_types(issue_type_id);

CREATE TABLE IF NOT EXISTS agent_issue_issue_types (
  issue_id TEXT NOT NULL,
  issue_type_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (issue_id, issue_type_id)
);

CREATE INDEX IF NOT EXISTS idx_issue_issue_types_issue_id ON agent_issue_issue_types(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_issue_types_issue_type_id ON agent_issue_issue_types(issue_type_id);

CREATE TABLE IF NOT EXISTS agent_issue_type_merges (
  id TEXT PRIMARY KEY,
  target_type_id TEXT NOT NULL,
  source_type_id TEXT NOT NULL,
  affected_eval_count INTEGER NOT NULL DEFAULT 0,
  affected_issue_count INTEGER NOT NULL DEFAULT 0,
  operator TEXT,
  note TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_type_merges_target ON agent_issue_type_merges(target_type_id);
CREATE INDEX IF NOT EXISTS idx_issue_type_merges_source ON agent_issue_type_merges(source_type_id);
CREATE INDEX IF NOT EXISTS idx_issue_type_merges_created_at ON agent_issue_type_merges(created_at);

-- Backfill dictionary from legacy single-value columns.
INSERT INTO agent_issue_types (id, name, normalized_name, enabled, merged_into_id, created_at, updated_at, created_by, updated_by)
SELECT lower(hex(randomblob(16))) AS id,
       src.name,
       src.normalized_name,
       1,
       NULL,
       datetime('now'),
       datetime('now'),
       'migration',
       'migration'
FROM (
  SELECT DISTINCT trim(issue_type) AS name, lower(trim(issue_type)) AS normalized_name
  FROM agent_eval_records
  WHERE issue_type IS NOT NULL AND trim(issue_type) <> ''
  UNION
  SELECT DISTINCT trim(issue_type) AS name, lower(trim(issue_type)) AS normalized_name
  FROM agent_issues
  WHERE issue_type IS NOT NULL AND trim(issue_type) <> ''
) src
WHERE src.name IS NOT NULL
  AND src.name <> ''
  AND NOT EXISTS (
    SELECT 1 FROM agent_issue_types t WHERE t.normalized_name = src.normalized_name
  );

-- Backfill eval <-> issue_type mapping.
INSERT OR IGNORE INTO agent_eval_issue_types (eval_id, issue_type_id, created_at)
SELECT e.id,
       t.id,
       COALESCE(e.updated_at, e.created_at, datetime('now'))
FROM agent_eval_records e
JOIN agent_issue_types t
  ON t.normalized_name = lower(trim(e.issue_type))
WHERE e.issue_type IS NOT NULL
  AND trim(e.issue_type) <> '';

-- Backfill issue <-> issue_type mapping.
INSERT OR IGNORE INTO agent_issue_issue_types (issue_id, issue_type_id, created_at)
SELECT i.id,
       t.id,
       COALESCE(i.updated_at, i.created_at, datetime('now'))
FROM agent_issues i
JOIN agent_issue_types t
  ON t.normalized_name = lower(trim(i.issue_type))
WHERE i.issue_type IS NOT NULL
  AND trim(i.issue_type) <> '';

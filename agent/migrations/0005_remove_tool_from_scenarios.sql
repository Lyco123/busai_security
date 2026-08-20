-- Remove tool and required_params fields from work_scenarios
-- Scenarios are now only used for accept/reject decisions, not tool routing

-- Drop the tool index first
DROP INDEX IF EXISTS idx_work_scenarios_tool;

-- SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
CREATE TABLE IF NOT EXISTS work_scenarios_new (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  keywords TEXT,
  embedding TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Copy data (excluding tool and required_params)
INSERT INTO work_scenarios_new (id, name, description, keywords, embedding, enabled, created_at, updated_at)
SELECT id, name, description, keywords, embedding, enabled, created_at, updated_at
FROM work_scenarios;

-- Drop old table
DROP TABLE work_scenarios;

-- Rename new table
ALTER TABLE work_scenarios_new RENAME TO work_scenarios;

-- Recreate the enabled index
CREATE INDEX IF NOT EXISTS idx_work_scenarios_enabled ON work_scenarios(enabled);


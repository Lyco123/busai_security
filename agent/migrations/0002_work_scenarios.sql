CREATE TABLE IF NOT EXISTS work_scenarios (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  tool TEXT NOT NULL,
  required_params TEXT,
  keywords TEXT,
  embedding TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_work_scenarios_enabled ON work_scenarios(enabled);
CREATE INDEX IF NOT EXISTS idx_work_scenarios_tool ON work_scenarios(tool);

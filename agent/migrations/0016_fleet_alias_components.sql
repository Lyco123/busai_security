DROP INDEX IF EXISTS idx_entity_standard_names_type;
DROP INDEX IF EXISTS idx_entity_aliases_type_status;
DROP INDEX IF EXISTS idx_entity_aliases_alias;

CREATE TABLE entity_standard_names_next (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'route', 'fleet')),
  standard_name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  unit_level TEXT,
  can_compose_with_fleet INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(entity_type, standard_name)
);

INSERT INTO entity_standard_names_next (
  id, entity_type, standard_name, enabled, unit_level, can_compose_with_fleet, created_at, updated_at
)
SELECT
  id,
  entity_type,
  standard_name,
  enabled,
  CASE
    WHEN entity_type = 'unit' AND standard_name LIKE '%车队%' THEN 'fleet_unit'
    WHEN entity_type = 'unit' AND standard_name LIKE '%集团%' THEN 'group'
    WHEN entity_type = 'unit' AND (
      standard_name LIKE '%分公司' OR standard_name LIKE '%片区' OR standard_name LIKE '%公司'
    ) THEN 'company'
    ELSE NULL
  END,
  CASE
    WHEN entity_type = 'unit'
      AND standard_name NOT LIKE '%车队%'
      AND (
        standard_name LIKE '%分公司' OR standard_name LIKE '%片区' OR standard_name LIKE '%公司'
      )
    THEN 1
    ELSE 0
  END,
  created_at,
  updated_at
FROM entity_standard_names;

CREATE TABLE entity_aliases_next (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'route', 'fleet')),
  standard_name TEXT NOT NULL,
  alias TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
  submitted_by TEXT,
  submitted_by_role TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT INTO entity_aliases_next (
  id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
  created_at, updated_at
)
SELECT
  id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
  created_at, updated_at
FROM entity_aliases;

DROP TABLE entity_standard_names;
ALTER TABLE entity_standard_names_next RENAME TO entity_standard_names;

DROP TABLE entity_aliases;
ALTER TABLE entity_aliases_next RENAME TO entity_aliases;

CREATE INDEX idx_entity_standard_names_type
  ON entity_standard_names(entity_type, enabled);

CREATE INDEX idx_entity_aliases_type_status
  ON entity_aliases(entity_type, status);

CREATE INDEX idx_entity_aliases_alias
  ON entity_aliases(entity_type, alias);

INSERT OR IGNORE INTO entity_standard_names (
  id, entity_type, standard_name, enabled, unit_level, can_compose_with_fleet, created_at, updated_at
) VALUES
  ('seed_standard_fleet_1', 'fleet', '一车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_2', 'fleet', '二车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_3', 'fleet', '三车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_4', 'fleet', '四车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_5', 'fleet', '五车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_6', 'fleet', '六车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_7', 'fleet', '七车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_8', 'fleet', '八车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_9', 'fleet', '九车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_fleet_10', 'fleet', '十车队', 1, 'fleet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO entity_aliases (
  id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at,
  created_at, updated_at
) VALUES
  ('seed_alias_fleet_1_1', 'fleet', '一车队', '一队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_1_2', 'fleet', '一车队', '第一车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_1_3', 'fleet', '一车队', '1队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_1_4', 'fleet', '一车队', '车一队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_2_1', 'fleet', '二车队', '二队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_2_2', 'fleet', '二车队', '第二车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_2_3', 'fleet', '二车队', '2队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_2_4', 'fleet', '二车队', '车二队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_3_1', 'fleet', '三车队', '三队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_3_2', 'fleet', '三车队', '第三车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_3_3', 'fleet', '三车队', '3队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_3_4', 'fleet', '三车队', '车三队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_4_1', 'fleet', '四车队', '四队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_4_2', 'fleet', '四车队', '第四车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_4_3', 'fleet', '四车队', '4队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_4_4', 'fleet', '四车队', '车四队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_5_1', 'fleet', '五车队', '五队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_5_2', 'fleet', '五车队', '第五车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_5_3', 'fleet', '五车队', '5队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_5_4', 'fleet', '五车队', '车五队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_6_1', 'fleet', '六车队', '六队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_6_2', 'fleet', '六车队', '第六车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_6_3', 'fleet', '六车队', '6队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_6_4', 'fleet', '六车队', '车六队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_7_1', 'fleet', '七车队', '七队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_7_2', 'fleet', '七车队', '第七车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_7_3', 'fleet', '七车队', '7队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_7_4', 'fleet', '七车队', '车七队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_8_1', 'fleet', '八车队', '八队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_8_2', 'fleet', '八车队', '第八车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_8_3', 'fleet', '八车队', '8队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_8_4', 'fleet', '八车队', '车八队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_9_1', 'fleet', '九车队', '九队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_9_2', 'fleet', '九车队', '第九车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_9_3', 'fleet', '九车队', '9队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_9_4', 'fleet', '九车队', '车九队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_10_1', 'fleet', '十车队', '十队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_10_2', 'fleet', '十车队', '第十车队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_10_3', 'fleet', '十车队', '10队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_fleet_10_4', 'fleet', '十车队', '车十队', 'approved', 'migration:0016', 'admin', 'migration:0016', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

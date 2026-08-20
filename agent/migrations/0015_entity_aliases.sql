CREATE TABLE IF NOT EXISTS entity_standard_names (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'route')),
  standard_name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(entity_type, standard_name)
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'route')),
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

CREATE INDEX IF NOT EXISTS idx_entity_standard_names_type
  ON entity_standard_names(entity_type, enabled);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_type_status
  ON entity_aliases(entity_type, status);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias
  ON entity_aliases(entity_type, alias);

INSERT OR IGNORE INTO entity_standard_names (id, entity_type, standard_name, enabled, created_at, updated_at) VALUES
  ('seed_standard_unit_bus_group', 'unit', '巴士集团', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_first_company', 'unit', '一分公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_second_company', 'unit', '二分公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_third_company', 'unit', '三分公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_fourth_company', 'unit', '四分公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_trolley_company', 'unit', '电车分公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_erba_company', 'unit', '二巴公司', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_fannan_area', 'unit', '番南片区', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_zengcong_area', 'unit', '增从片区', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_huadu_area', 'unit', '花都片区', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_foguang_group', 'unit', '佛广集团', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_standard_unit_mahui_bus', 'unit', '马会巴士', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO entity_aliases (
  id, entity_type, standard_name, alias, status, submitted_by, submitted_by_role, reviewed_by, reviewed_at, created_at, updated_at
) VALUES
  ('seed_alias_unit_bus_group_1', 'unit', '巴士集团', '巴集', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_bus_group_2', 'unit', '巴士集团', '广州巴士集团', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_bus_group_3', 'unit', '巴士集团', '广州巴士集团有限公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_first_company_1', 'unit', '一分公司', '一分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_first_company_2', 'unit', '一分公司', '广州巴士集团一分公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_first_company_3', 'unit', '一分公司', '巴集一分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_second_company_1', 'unit', '二分公司', '二分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_second_company_2', 'unit', '二分公司', '广州巴士集团二分公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_second_company_3', 'unit', '二分公司', '巴集二分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_third_company_1', 'unit', '三分公司', '三分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_third_company_2', 'unit', '三分公司', '广州巴士集团三分公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_third_company_3', 'unit', '三分公司', '巴集三分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fourth_company_1', 'unit', '四分公司', '四分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fourth_company_2', 'unit', '四分公司', '广州巴士集团四分公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fourth_company_3', 'unit', '四分公司', '巴集四分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_trolley_company_1', 'unit', '电车分公司', '电分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_trolley_company_2', 'unit', '电车分公司', '广州巴士集团电车公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_trolley_company_3', 'unit', '电车分公司', '巴集电分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_erba_company_1', 'unit', '二巴公司', '二巴', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_erba_company_2', 'unit', '二巴公司', '广州巴士集团二巴公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_erba_company_3', 'unit', '二巴公司', '巴集二巴', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fannan_area_1', 'unit', '番南片区', '番南', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fannan_area_2', 'unit', '番南片区', '广州巴士集团番南片区', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_fannan_area_3', 'unit', '番南片区', '巴集番南', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_zengcong_area_1', 'unit', '增从片区', '增从', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_zengcong_area_2', 'unit', '增从片区', '增分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_zengcong_area_3', 'unit', '增从片区', '广州巴士集团增从片区', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_zengcong_area_4', 'unit', '增从片区', '巴集增从', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_zengcong_area_5', 'unit', '增从片区', '巴集增分', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_huadu_area_1', 'unit', '花都片区', '花恒', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_huadu_area_2', 'unit', '花都片区', '广州巴士集团花都片区', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_huadu_area_3', 'unit', '花都片区', '巴集花都', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_huadu_area_4', 'unit', '花都片区', '巴集花恒', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_foguang_group_1', 'unit', '佛广集团', '佛广', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_foguang_group_2', 'unit', '佛广集团', '广州巴士集团佛广公司', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_foguang_group_3', 'unit', '佛广集团', '巴集佛广', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_mahui_bus_1', 'unit', '马会巴士', '马会', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_mahui_bus_2', 'unit', '马会巴士', '广州巴士集团马会巴士', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('seed_alias_unit_mahui_bus_3', 'unit', '马会巴士', '巴集马会', 'approved', 'migration:0015', 'admin', 'migration:0015', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

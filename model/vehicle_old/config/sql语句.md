# 车辆画像模型 SQL 清单

> 说明：本文件按 `build_feature_table()` 中的读取顺序整理。主表先构建，再按序号 1~8 逐个合并特征表。  
> 合并键说明：  
> - 日级特征表：统一输出 `stat_date` / `obuid`，或者输出可被 Python 重命名为这两个键的字段  
> - 静态表：按 `obuid` 合并  
> - 线路上下文：当前拆成两张 SQL 结果表，分别输出站点数和转弯点数  
> - 下文“中文表名”优先采用你提供的“表描述”；若原表描述为空，则写为“表描述未提供（按表名理解）”

---

## 0. 基础宽表主表（对应 `build_feature_table` 的 `base_df`）

**对应物理表**
- 表名：`ads_bus_energy_day_stat`
- 中文表名：车辆能耗统计

**用途**
- 作为最终特征宽表的主表
- 提供 `信息_统计日期`、`信息_车辆ID`、`信息_线路ID`
- 提供基础运营指标：运营里程、百公里能耗、运营时长

**建议输出字段**
- `ppartition`
- `obuid`
- `route_id`
- `run_mileage`
- `energy`
- `total_second`

```sql
-- 0. 基础宽表主表
-- 对应函数：build_feature_table()
-- 对应物理表：ai_security.ads_bus_energy_day_stat（车辆能耗统计）
SELECT
    ppartition,
    obuid,
    route_id,
    run_mileage,
    energy,
    total_second
FROM ai_security.ads_bus_energy_day_stat;
```

---

## 1. CAN 压差温差（对应 `_process_can_data`）

**对应物理表**
- 表名：`abs_can_stats_result`
- 中文表名：can零件解密汇总表

**用途**
- 计算 `车辆设备_电池最大电压差`
- 计算 `CAN_最大温差`

**建议输出字段**
- `ppartition` 或 `data_time`
- `obuid`
- `D30`
- `D31`
- `D34`
- `D35`

```sql
-- 1. CAN 压差温差原始字段
-- 对应函数：_process_can_data()
-- 对应物理表：ai_security.abs_can_stats_result（can零件解密汇总表）
-- Python 会继续计算：
-- derived_volt_diff = abs(D30 - D31)
-- derived_temp_diff = abs(D34 - D35)
SELECT
    ppartition,
    obuid,
    D30,
    D31,
    D34,
    D35
FROM ai_security.abs_can_stats_result;
```

---

## 2. 车辆静态档案（对应 `_get_static_features`）

**对应物理表**
- 表名：`ods_jituan_bs_bus`
- 中文表名：车辆基础数据

**用途**
- 生成车辆品牌、自重、车长、电池容量、车龄
- 同时给维修表提供 `number_plate -> obuid` 映射

**建议输出字段**
- `obuid`
- `number_plate`
- `bus_brand`
- `total_weight`
- `bus_length`
- `battery_capacity`
- `put_production_day`

```sql
-- 2. 车辆静态档案
-- 对应函数：_get_static_features()
-- 对应物理表：ai_security.ods_jituan_bs_bus（车辆基础数据）
SELECT
    obuid,
    number_plate,
    bus_brand,
    total_weight,
    bus_length,
    battery_capacity,
    put_production_day
FROM ai_security.ods_jituan_bs_bus;
```

---

## 3. 驾驶行为统计（对应 `_get_behavior_features`）

**对应物理表**
- 表名：`abs_driver_behavior_sum`
- 中文表名：驾驶行为汇总表（原始表描述未提供）

**用途**
- 生成 `驾驶不良行为_*_次数`
- 依赖 `驾驶行为透视表.csv` 做列名映射

**建议输出字段**
- `ppartition`
- `obuid`
- 所有 `report_type*_count` 字段

```sql
-- 3. 驾驶行为统计
-- 对应函数：_get_behavior_features()
-- 对应物理表：ai_security.abs_driver_behavior_sum（驾驶行为汇总表；原始表描述未提供）
-- 如果 ClickHouse 支持 COLUMNS()，可直接批量选择所有 report_type*_count 字段
SELECT
    ppartition,
    obuid,
    COLUMNS('^report_type.*_count$')
FROM ai_security.abs_driver_behavior_sum;
```

> 如果当前环境不支持 `COLUMNS()`，就需要把 `report_type1_count ~ report_typeN_count` 显式展开。

---

## 4. 车辆故障数据（对应 `_get_fault_features`）

**对应物理表**
- 表名：`ads_fault_analysis`
- 中文表名：故障管理

**用途**
- 生成 `故障_当日总次数`
- 若存在 `fault_type_name`，进一步生成各故障类型次数

**建议输出字段**
- `ppartition`
- `obuid`
- `fault_type_name`

```sql
-- 4. 车辆故障数据
-- 对应函数：_get_fault_features()
-- 对应物理表：ai_security.ads_fault_analysis（故障管理）
SELECT
    ppartition,
    obuid,
    fault_type_name
FROM ai_security.ads_fault_analysis;
```

---

## 5. 空调使用开关次数和开启时间（对应 `_get_aircond_features`）

**对应物理表**
- 表名：`ads_air_conditioner_use`
- 中文表名：空调使用明细

**用途**
- 生成 `车辆设备_空气压缩机开启时长`
- 生成 `车辆设备_空气压缩机开启次数`

**当前 Python 需要的输出字段**
- `ppartition`
- `obuid`
- `total_open_time`
- `record_count`

**说明**
- 你原 SQL 里还统计了 `SUM(close_time)`，但当前 Python 代码没有使用该字段
- 因此在导出到 `sql_data` 时，可以不保留 `total_close_time`

```sql
-- 5. 空调使用开关次数和开启时间
-- 对应函数：_get_aircond_features()
-- 对应物理表：ai_security.ads_air_conditioner_use（空调使用明细）
-- 当前 Python 实际使用字段：ppartition, obuid, total_open_time, record_count
SELECT 
    ppartition,
    obuid,
    SUM(open_time) AS total_open_time,
    COUNT(*) AS record_count
FROM ai_security.ads_air_conditioner_use
GROUP BY 
    ppartition, 
    obuid;
```

> 如果你后续想保留 `SUM(close_time)` 做补充分析，可以额外输出，但当前 Python 不会读取。

---

## 6. 充电能耗数据（对应 `_get_charge_features`）

**对应物理表**
- 表名：`ads_day_energy_analysis`
- 中文表名：每日电量分析

**用途**
- 生成 `车辆设备_日充电次数`
- 生成 `车辆设备_日充电量`
- 计算 `车辆设备_每公里耗电量`

**建议输出字段**
- `ppartition`
- `obuid`
- `day_charge_count`
- `night_charge_count`
- `day_charge_soc`
- `night_charge_soc`
- `use_soc`
- `run_mileage`

```sql
-- 6. 充电能耗数据
-- 对应函数：_get_charge_features()
-- 对应物理表：ai_security.ads_day_energy_analysis（每日电量分析）
SELECT
    ppartition,
    obuid,
    day_charge_count,
    night_charge_count,
    day_charge_soc,
    night_charge_soc,
    use_soc,
    run_mileage
FROM ai_security.ads_day_energy_analysis;
```

---

## 7. 车辆维修记录（对应 `_get_repair_features`）

**对应物理表**
- 主表名：`ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project`
- 主表中文表名：巴士集团维修主表
- 映射表名：`ods_jituan_bs_bus`
- 映射表中文表名：车辆基础数据

**用途**
- 根据维修记录构造 `车辆维修_维修工单数`
- 当前 Python 会把车牌映射为 `obuid`，再计算 7 日滚动工单数

**建议输出字段**
- `f_buslisence`
- `f_indatetime`

```sql
-- 7. 车辆维修记录
-- 对应函数：_get_repair_features()
-- 对应物理表：ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project（巴士集团维修主表）
-- 映射依赖：ai_security.ods_jituan_bs_bus（车辆基础数据）
SELECT
    f_buslisence,
    f_indatetime
FROM ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project;
```

> 如果后续你想把这部分也提前用 SQL 聚合成最终结果表，可以直接输出  
> `stat_date, obuid, 车辆维修_维修工单数`，那 Python 逻辑还能再简化一层。

---

## 8. 车辆每日线路上下文特征（对应 `_get_trip_context_features`）

该函数当前读取两张 SQL 结果表：  
- 8.1 车辆每日线路转弯点统计  
- 8.2 车辆每日线路站点数统计  

最终在 Python 中合并成：  
- `车辆运营_线路转弯点数`  
- `车辆运营_线路站点数`

### 8.1 车辆每日线路转弯点统计

**对应物理表**
- 主表名：`ads_triplog_energy`
- 主表中文表名：更纸行驶里程统计（按你提供的表描述原文）
- 关联表名：`ads_event_black_spot`
- 关联表中文表名：黑点

**输出文件示例**
- `vehicle_codex/data/sql_data/_SELECT_drive_date_bus_id_sum_turn_count_AS_total_turn_count_FRO_202604011634.csv`

**当前 Python 需要的输出字段**
- `drive_date`
- `bus_id`
- `total_turn_count`

```sql
-- 8.1 车辆每日线路转弯点统计
-- 对应函数：_get_trip_context_features()
-- 对应主表：ai_security.ads_triplog_energy（更纸行驶里程统计）
-- 对应关联表：ai_security.ads_event_black_spot（黑点）
-- 输出字段必须是：drive_date, bus_id, total_turn_count
SELECT 
    drive_date,
    bus_id ,
    SUM(turn_count) AS total_turn_count
FROM (
    SELECT
        toDate(t.ppartition) AS drive_date,
        t.bus_id AS bus_id,
        t.route_id,
        COUNT(b.event_type) AS turn_count
    FROM ai_security.ads_triplog_energy t
    LEFT JOIN ai_security.ads_event_black_spot b
        ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
       AND b.event_type IN (2, 3)
    GROUP BY 
        drive_date,
        bus_id,
        t.route_id
) AS sub
GROUP BY 
    drive_date,
    bus_id;
```

> 说明：当前这条 SQL 统计的是“该车当天跑过的线路，对应匹配到的转弯点总数”。

### 8.2 车辆每日线路站点数统计

**对应物理表**
- 主表名：`ads_triplog_energy`
- 主表中文表名：更纸行驶里程统计（按你提供的表描述原文）
- 关联表名：`ods_jituan_mssql_10_181_92_95_basic_archives_line_site`
- 关联表中文表名：线路走法表

**输出文件示例**
- `vehicle_codex/data/sql_data/_SELECT_drive_date_bus_id_sum_station_count_AS_total_station_cou_202604011620.csv`

**当前 Python 需要的输出字段**
- `drive_date`
- `bus_id`
- `total_station_count`

```sql
-- 8.2 车辆每日线路站点数统计
-- 对应函数：_get_trip_context_features()
-- 对应主表：ai_security.ads_triplog_energy（更纸行驶里程统计）
-- 对应关联表：ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site（线路走法表）
-- 输出字段必须是：drive_date, bus_id, total_station_count
SELECT 
    drive_date,
    bus_id,
    SUM(station_count) AS total_station_count
FROM (
    SELECT 
        toDate(t.ppartition) AS drive_date,
        t.bus_id AS bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
    FROM ai_security.ads_triplog_energy t
    LEFT JOIN (
        -- 同线路同站名取最小站序，避免站点重复导致跨站数重复计算
        SELECT 
            line_code,
            motorcade_name,
            MIN(sort) AS min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY 
            line_code,
            motorcade_name
    ) s1 
        ON t.route_id = s1.line_code 
       AND t.from_station = s1.motorcade_name
    LEFT JOIN (
        SELECT 
            line_code,
            motorcade_name,
            MIN(sort) AS min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY 
            line_code,
            motorcade_name
    ) s2 
        ON t.route_id = s2.line_code 
       AND t.to_station = s2.motorcade_name
    WHERE s1.min_sort IS NOT NULL 
      AND s2.min_sort IS NOT NULL
) AS sub
GROUP BY 
    drive_date,
    bus_id;
```

> 说明：该 SQL 先按每条行程计算跨站数，再按“车-天”汇总。

---

## 9. 当前代码中的合并顺序

当前 `build_feature_table()` 的合并顺序如下：

1. `_process_can_data(start_date, end_date)`
2. `_get_static_features(df_bus_static)`
3. `_get_behavior_features(start_date, end_date)`
4. `_get_fault_features(start_date, end_date)`
5. `_get_aircond_features(start_date, end_date)`
6. `_get_charge_features(start_date, end_date)`
7. `_get_repair_features(start_date, end_date, df_bus_static)`
8. `_get_trip_context_features(start_date, end_date)`

建议后续所有 SQL 导出文件命名也按这个顺序维护，方便排查。

---

## 10. 当前 SQL 清单与物理表对应关系总表

| 序号 | 模块 | 对应函数 | 物理表名 | 中文表名 |
|---|---|---|---|---|
| 0 | 基础宽表主表 | `build_feature_table` | `ads_bus_energy_day_stat` | 车辆能耗统计 |
| 1 | CAN压差温差 | `_process_can_data` | `abs_can_stats_result` | can零件解密汇总表 |
| 2 | 车辆静态档案 | `_get_static_features` | `ods_jituan_bs_bus` | 车辆基础数据 |
| 3 | 驾驶行为统计 | `_get_behavior_features` | `abs_driver_behavior_sum` | 驾驶行为汇总表（表描述未提供） |
| 4 | 车辆故障数据 | `_get_fault_features` | `ads_fault_analysis` | 故障管理 |
| 5 | 空调开关次数和开启时间 | `_get_aircond_features` | `ads_air_conditioner_use` | 空调使用明细 |
| 6 | 充电能耗数据 | `_get_charge_features` | `ads_day_energy_analysis` | 每日电量分析 |
| 7 | 车辆维修记录 | `_get_repair_features` | `ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project` | 巴士集团维修主表 |
| 7-映射 | 维修车牌映射 | `_get_repair_features` | `ods_jituan_bs_bus` | 车辆基础数据 |
| 8.1 | 每日线路转弯点统计 | `_get_trip_context_features` | `ads_triplog_energy` + `ads_event_black_spot` | 更纸行驶里程统计 + 黑点 |
| 8.2 | 每日线路站点数统计 | `_get_trip_context_features` | `ads_triplog_energy` + `ods_jituan_mssql_10_181_92_95_basic_archives_line_site` | 更纸行驶里程统计 + 线路走法表 |

---

## 11. 建议的 SQL 文件命名规范

```text
00_bus_energy_day_stat_YYYYMMDDHHMM.csv
01_can_stats_YYYYMMDDHHMM.csv
02_bus_static_YYYYMMDDHHMM.csv
03_driver_behavior_YYYYMMDDHHMM.csv
04_fault_analysis_YYYYMMDDHHMM.csv
05_aircond_open_time_YYYYMMDDHHMM.csv
06_day_energy_analysis_YYYYMMDDHHMM.csv
07_repair_daily_YYYYMMDDHHMM.csv
08_turn_count_daily_YYYYMMDDHHMM.csv
09_station_count_daily_YYYYMMDDHHMM.csv
```

这样以后 Python 里切换成统一读取 `sql_data` 时也更好维护。

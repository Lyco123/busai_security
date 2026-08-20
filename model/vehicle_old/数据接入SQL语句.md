# 数据处理

## 1. 本文职责

本文只说明三件事：

- 每个特征由哪个函数读取哪张表生成
- 特征的统计时间维度、计算公式、单位
- 末尾附每个读取函数对应的 SQL 语句

## 2. 主表与公共派生

### 2.1 `build_feature_frames()`

来源表：`ads_bus_energy_day_stat_*.csv`

| 输出字段 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `信息_统计日期` | 当日 | `ppartition` 转日期 | 日期 |
| `信息_车辆ID` | 当日 | `obuid` 清洗后输出 | - |
| `信息_线路ID` | 当日 | `route_id` 去 `.0` | - |
| `车辆运营_运营里程` | 当日 | 直接取 `run_mileage` | km |
| `指标_百公里能耗` | 当日 | 直接取 `energy` | kWh/100km |
| `车辆运营_运营时长` | 当日 | `total_second / 3600` | h |
| `车辆运营_平均速度` | 当日 | `运营里程 / 运营时长` | km/h |
| `行驶路况_拥堵指数` | 当日 | `运营时长 / 运营里程` | h/km |

异常值清洗：

- `车辆运营_运营里程`：`0 ~ 400`
- `指标_百公里能耗`：`0 ~ 300`
- `车辆运营_运营时长`：`0 ~ 24`

## 3. 分来源特征逻辑

### 3.1 `_process_can_data()`

来源表：`abs_can_stats_result_*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆设备_电池最大电压差` | 当日 | `max(abs(D30 - D31))` | 源表单位 |
| `车辆设备_最大温差` | 当日 | `max(abs(D34 - D35))` | 源表单位 |
| `车辆设备_电池电压过低次数` | 当日 | 当前无真实数据，补 `0` | 次 |
| `车辆设备_电池电流过高次数` | 当日 | 当前无真实数据，补 `0` | 次 |
| `车辆设备_电池最大电流差` | 当日 | 当前无真实数据，补 `0` | 源表单位 |

### 3.2 `_get_static_features()`

来源表：`车辆静态数据SQL读取表.csv`

| 输出字段 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆属性_车辆品牌` | 静态 | 直接取 `bus_brand` | - |
| `车辆属性_车辆自重` | 静态 | 直接取 `total_weight` | kg |
| `车辆属性_车长` | 静态 | 直接取 `bus_length` | m |
| `车辆属性_电池容量` | 静态 | 直接取 `battery_capacity` | 源表单位 |
| `车辆属性_车龄` | 静态 | 直接取 `bus_age` | 年 |
| `信息_车牌号` | 主表 | 直接取主表 `number_plate` | - |
| `信息_公司ID` | 主表 | 直接取主表 `organ_id` | - |
| `信息_公司名称` | 主表 | 直接取主表 `organ_name` | - |

### 3.3 `_get_behavior_features()` + `_normalize_behavior_features()`

来源表：`abs_driver_behavior_sum_*.csv`

先把 `report_type*_count` 透视成 `驾驶不良行为_*_次数`，再做业务折算：

| 特征组 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| 站点类行为 | 当日 | `当日次数 / 当日线路站点数 * 100` | 次/100站 |
| 转弯类行为 | 当日 | `当日次数 / 当日线路转弯点数 * 100` | 次/100转弯点 |
| 其余驾驶行为 | 当日 | `当日次数 / 当日运营里程 * 1000` | 次/1000km |

### 3.4 `_get_fault_features()` + `_apply_weekly_per_km_counts()`

来源表：`ads_fault_analysis_*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `信息_故障当日总次数原始值` | 当日 | 当日故障明细计数 | 次 |
| `故障_近7天每公里总次数` | 近 7 天 | `近7天故障总次数和 / 近7天运营里程和` | 次/km |
| `故障_*_次数` | 近 7 天 | `近7天故障类型次数和 / 近7天运营里程和` | 次/km |
| `车辆维修_动力电池故障(电池)_次数` | 近 7 天 | `近7天次数和 / 近7天运营里程和` | 次/km |
| `车辆维修_单体高低电压差(平台定义值)_次数` | 近 7 天 | `近7天次数和 / 近7天运营里程和` | 次/km |
| `车辆维修_空调工作模式(空调)_次数` | 近 7 天 | `近7天次数和 / 近7天运营里程和` | 次/km |

### 3.5 `_get_aircond_features()`

来源表：`*_SELECT_ppartition_obuid_SUM_open_time*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆设备_空气压缩机开启时长` | 当日 | `SUM(open_time)` | 源表单位 |
| `车辆设备_空气压缩机开启次数` | 当日 | `COUNT(*)` | 次 |

### 3.6 `_get_charge_features()`

来源表：`ads_day_energy_analysis_*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆设备_日充电次数` | 当日 | `day_charge_count + night_charge_count` | 次 |
| `车辆设备_日充电量` | 当日 | `day_charge_soc + night_charge_soc` | 源表单位 |
| `车辆设备_每公里耗电量` | 当日 | `use_soc / run_mileage` | 源表单位/km |

### 3.7 `_get_repair_features()` + `_apply_weekly_per_km_counts()`

来源表：`ods_jituan_mssql_*_repair_*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆维修_维修工单数` | 近 7 天 | `近7天维修工单数和 / 近7天运营里程和` | 次/km |

### 3.8 `_get_trip_context_features()`

来源表：

- `*_SELECT_drive_date_bus_id_sum_station_count_AS_total_station*.csv`
- `*_SELECT_drive_date_bus_id_sum_turn_count_AS_total_turn*.csv`

| 输出特征 | 时间维度 | 计算公式 | 单位 |
| --- | --- | --- | --- |
| `车辆运营_线路站点数` | 当日 | `sum(total_station_count)` | 个 |
| `车辆运营_线路转弯点数` | 当日 | `sum(total_turn_count)` | 个 |

## 4. 宽表补值规则

`build_feature_frames()` 会同时生成：

- `raw_df`：保留原值和缺失状态，用于原值表与归一化值表展示
- `model_df`：按训练/评分口径补值后的模型输入表

当前 `model_df` 统一补 `0` 的列：

- 全部 `故障_` 前缀列
- 全部 `车辆维修_` 前缀列
- 全部 `车辆设备_` 前缀列
- `车辆运营_线路站点数`
- `车辆运营_线路转弯点数`

## 5. SQL 清单

### 5.1 `build_feature_frames()` 主表

```sql
SELECT
    ppartition,
	organ_id,
	organ_name,
	number_plate,
    obuid,
    route_id,
    run_mileage,
    energy,
    total_second
FROM ai_security.ads_bus_energy_day_stat;
```

### 5.2 `_process_can_data()`

```sql
SELECT
    ppartition,
    obuid,
    D30,
    D31,
    D34,
    D35
FROM ai_security.abs_can_stats_result;
```

### 5.3 `_get_static_features()`

```sql
SELECT
    obuid,
    number_plate,
    bus_brand,
    total_weight,
    bus_length,
    battery_capacity,
    bus_age,
FROM ai_security.ods_jituan_bs_bus;
```

说明：当前样例 CSV 只包含 `number_plate/bus_brand/total_weight/bus_length/battery_capacity/bus_age`，若公司字段暂未导出，代码会保留空列并写 warning。

### 5.4 `_get_behavior_features()`

```sql
SELECT
    ppartition,
    obuid,
    COLUMNS('^report_type.*_count$')
FROM ai_security.abs_driver_behavior_sum;
```

### 5.5 `_get_fault_features()`

```sql
SELECT
    ppartition,
    obuid,
    fault_type_name
FROM ai_security.ads_fault_analysis;
```

### 5.6 `_get_aircond_features()`

```sql
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

### 5.7 `_get_charge_features()`

```sql
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

### 5.8 `_get_repair_features()`

```sql
SELECT
    f_buslisence,
    f_indatetime
FROM ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project;
```

### 5.9 `_get_trip_context_features()` 站点数

```sql
SELECT
    drive_date,
    bus_id,
    SUM(station_count) AS total_station_count
FROM (
    SELECT
        toDate(t.ppartition) AS drive_date,
        t.bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
    FROM ai_security.ads_triplog_energy t
    LEFT JOIN (
        SELECT line_code, motorcade_name, MIN(sort) AS min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
    ) s1
        ON toString(t.route_id) = s1.line_code
       AND t.from_station = s1.motorcade_name
    LEFT JOIN (
        SELECT line_code, motorcade_name, MIN(sort) AS min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
    ) s2
        ON toString(t.route_id) = s2.line_code
       AND t.to_station = s2.motorcade_name
) sub
GROUP BY
    drive_date,
    bus_id;
```

### 5.10 `_get_trip_context_features()` 转弯点数

```sql
SELECT
    drive_date,
    bus_id,
    SUM(turn_count) AS total_turn_count
FROM (
    SELECT
        toDate(t.ppartition) AS drive_date,
        t.bus_id,
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
) sub
GROUP BY
    drive_date,
    bus_id;
```

### 5.11 `评分代码获取权重 SQL`

```sql
SELECT DISTINCT
    '3' AS quota_level,
    quota_id2 AS parent_id,
    quota_name2 AS parent_name,
    quota_id3 AS quota_id,
    quota_name1 || '_' || quota_name2 || '_' || quota_name3 AS quota_name,
    CASE
        WHEN (quota_name2 = '驾驶不良行为' OR quota_name2 = '车辆维修') AND quota_name3 <> '维修工单数'
            THEN quota_name1 || '_' || quota_name2 || '_' || quota_name3 || '_次数'
        ELSE quota_name1 || '_' || quota_name2 || '_' || quota_name3
    END AS feature,
    quota_name3 AS feature_name,
    CASE WHEN weight_rate1 = 0 THEN calculate_weight_rate1 ELSE weight_rate1 END AS weight_rate1,
    CASE WHEN weight_rate2 = 0 THEN calculate_weight_rate2 ELSE weight_rate2 END AS weight_rate2,
    CASE WHEN weight_rate3 = 0 THEN calculate_weight_rate3 ELSE weight_rate3 END AS weight,
    CASE WHEN weight_rate3 = 0 THEN calculate_weight_rate3 ELSE weight_rate3 END AS weight_rate3,
    start_time
FROM ai_security.obs_quota_weight_configuration
WHERE profile_type = '车辆画像'
  AND deleted != '1'
  AND calculate_weight_rate3 <> 0
  AND start_time IN (
      SELECT max(start_time)
      FROM ai_security.obs_quota_weight_configuration
      WHERE profile_type = '车辆画像'
        AND deleted != '1'
        AND calculate_weight_rate3 <> 0
  );
```

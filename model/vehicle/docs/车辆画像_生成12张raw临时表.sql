/* ============================================================
   车辆画像风险模型：全字段 raw 临时表生成脚本

   下载表清单：
   01 tmp_vrp_01_energy_route_day      能耗主样本表
   02 tmp_vrp_02_static_bus            车辆静态表
   03 tmp_vrp_03_fault_day             故障表
   04 tmp_vrp_04_can_day               CAN表
   05 tmp_vrp_05_behavior_day          驾驶行为表
   06 tmp_vrp_06_charge_day            充电表
   07 tmp_vrp_07_aircond_day           空调表
   08 tmp_vrp_08_route_trip_day        车辆线路班次表
   09 tmp_vrp_09_route_station_static  线路站点静态表
   10 tmp_vrp_10_route_black_static    线路黑点/转弯静态表
   11 tmp_vrp_11_passenger_day         客流表
   12 tmp_vrp_12_repair_day            维修表

   设计原则：
   1. SQL 只做最简单的 raw 日聚合临时表。
   2. SQL 不做最终模型字段、不做标签、不做 LOO、不做 rolling、不做缺失填充、不做归一化。
   3. 统一时间配置写在 ai_security.tmp_vrp_00_params。
   4. 每张表都可以单独下载到 data/ 文件夹。

   修改时间：只需要修改 tmp_vrp_00_params 里的两个日期。
   source_start_date 建议 = 训练/评分开始日 - 30 天
   source_end_date   建议 = 评分结束日 + 7 天
   ============================================================ */

SET max_execution_time = 0;
SET receive_timeout = 3600;
SET send_timeout = 3600;
SET connect_timeout = 60;

/* ============================================================
   0. 统一参数表
   ============================================================ */

DROP TABLE IF EXISTS ai_security.tmp_vrp_00_params;

CREATE TABLE ai_security.tmp_vrp_00_params
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate('2025-12-02') AS source_start_date,
    toDate('2026-05-07') AS source_end_date;

/* ============================================================
   0.1 清理旧临时表
   ============================================================ */

DROP TABLE IF EXISTS ai_security.tmp_vrp_01_energy_route_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_02_static_bus;
DROP TABLE IF EXISTS ai_security.tmp_vrp_03_fault_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_04_can_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_05_behavior_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_06_charge_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_07_aircond_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_08_route_trip_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_09_route_station_static;
DROP TABLE IF EXISTS ai_security.tmp_vrp_10_route_black_static;
DROP TABLE IF EXISTS ai_security.tmp_vrp_11_passenger_day;
DROP TABLE IF EXISTS ai_security.tmp_vrp_12_repair_day;

/* ============================================================
   01. 能耗主样本表
   粒度：stat_date + bus_id + route_id
   下载：data/tmp_vrp_01_energy_route_day.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_01_energy_route_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,

    any(toString(ppartition)) AS raw_ppartition,
    any(toString(obuid)) AS obuid,

    toString(bus_id) AS bus_id,
    any(toString(bus_code)) AS bus_code,
    any(replaceRegexpAll(trimBoth(toString(number_plate)), '\\s+', '')) AS number_plate,

    any(toString(organ_id)) AS organ_id,
    any(toString(organ_name)) AS organ_name,

    toString(route_id) AS route_id,
    any(toString(route_name)) AS route_name,
    
    anyIf(
        trimBoth(toString(bus_type)),
        trimBoth(toString(bus_type)) != ''
    ) AS static_bus_type,

    sum(toFloat64OrZero(toString(run_mileage))) AS src_run_mileage,
    sum(toFloat64OrZero(toString(energy))) AS src_energy,
    avg(toFloat64OrNull(toString(mileage_energy))) AS src_mileage_energy,
    avg(toFloat64OrNull(toString(mileage_energy2))) AS src_mileage_energy2,
    sum(toFloat64OrZero(toString(total_second))) AS src_total_second

FROM canbus.ads_bus_energy_day_stat

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND bus_id IS NOT NULL
  AND toString(bus_id) != ''
  AND route_id IS NOT NULL
  AND toString(route_id) != ''

GROUP BY
    stat_date,
    bus_id,
    route_id;

/* ============================================================
   02. 车辆静态表
   粒度：bus_id
   下载：data/tmp_vrp_02_static_bus.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_02_static_bus
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toString(bus_id) AS bus_id,

    any(toString(bus_brand)) AS static_bus_brand,
    any(toFloat64OrNull(replaceAll(toString(total_weight), ',', ''))) AS static_total_weight,

    any(
        if(
            toFloat64OrNull(replaceAll(toString(bus_length), ',', '')) > 100,
            toFloat64OrNull(replaceAll(toString(bus_length), ',', '')) / 1000.0,
            toFloat64OrNull(replaceAll(toString(bus_length), ',', ''))
        )
    ) AS static_bus_length,

    any(toFloat64OrNull(replaceAll(toString(battery_capacity), ',', ''))) AS static_battery_capacity,
    any(toFloat64OrNull(toString(bus_age))) AS static_bus_age

FROM canbus.ods_jituan_bs_bus

WHERE bus_id IS NOT NULL
  AND toString(bus_id) != ''

GROUP BY
    bus_id;

/* ============================================================
   03. 故障表
   粒度：stat_date + bus_id
   下载：data/tmp_vrp_03_fault_day.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_03_fault_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    toString(bus_id) AS bus_id,

    count() AS fault_total_count,
    count() AS fault_total_count_raw,

    countIf(toString(fault_type_name) LIKE '%ABS%') AS fault_abs_dashboard_count,
    countIf(toString(fault_type_name) LIKE '%动力电池%') AS fault_power_battery_count,
    countIf(toString(fault_type_name) LIKE '%空调%') AS fault_aircond_mode_count,
    countIf(toString(fault_type_name) LIKE '%电压差%') AS fault_cell_voltage_diff_count,
    countIf(toString(fault_type_name) LIKE '%左电机%') AS fault_left_motor_count,
    countIf(toString(fault_type_name) LIKE '%右电机%') AS fault_right_motor_count,
    countIf(toString(fault_type_name) LIKE '%整车控制器%') AS fault_battery_vcu_count,
    countIf(toString(fault_type_name) LIKE '%轮胎温度%') AS fault_tire_temp_count,
    countIf(toString(fault_type_name) LIKE '%轮胎压力%') AS fault_tire_pressure_count,
    countIf(toString(fault_type_name) LIKE '%润滑%') AS fault_lubrication_count,
    countIf(toString(fault_type_name) LIKE '%打气泵%') AS fault_controller_air_pump_count,
    countIf(toString(fault_type_name) LIKE '%助力转向泵%') AS fault_controller_steering_pump_count,
    countIf(toString(fault_type_name) LIKE '%DCDC%') AS fault_controller_dcdc_count,
    countIf(toString(fault_type_name) LIKE '%绝缘%') AS fault_insulation_count

FROM canbus.ads_fault_analysis

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND bus_id IS NOT NULL
  AND toString(bus_id) != ''

GROUP BY
    stat_date,
    bus_id;

/* ============================================================
   04. CAN表
   粒度：stat_date + number_plate
   下载：data/tmp_vrp_04_can_day.csv
   Python 后续用 stat_date + number_plate 映射 bus_id。
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_04_can_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    replaceRegexpAll(trimBoth(toString(number_plate)), '\\s+', '') AS number_plate,

    max(toFloat64OrNull(toString(D30_max))) AS can_D30_max,
    min(toFloat64OrNull(toString(D31_min))) AS can_D31_min,
    max(toFloat64OrNull(toString(D34_max))) AS can_D34_max,
    min(toFloat64OrNull(toString(D35_min))) AS can_D35_min,
    max(toFloat64OrNull(toString(D29_max))) AS can_D29_max,
    min(toFloat64OrNull(toString(D29_min))) AS can_D29_min,

    any(toFloat64OrNull(toString(standard_voltage))) AS can_standard_voltage,
    any(toFloat64OrNull(toString(standard_current))) AS can_standard_current

FROM canbus.ads_can_day_bus_agg

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND number_plate IS NOT NULL
  AND toString(number_plate) != ''

GROUP BY
    stat_date,
    number_plate;

/* ============================================================
   05. 驾驶行为表
   粒度：stat_date + obuid
   下载：data/tmp_vrp_05_behavior_day.csv
   Python 后续用 stat_date + obuid 映射 bus_id。
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_05_behavior_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    toString(obuid) AS obuid,

    uniqExact(toString(operator_code)) AS operator_code_count,
    uniqExact(toString(obuid)) AS behavior_obuid_count,
    count() AS raw_behavior_row_count,

    sum(toFloat64OrZero(toString(report_type1_count))) AS report_type1_count,
    sum(toFloat64OrZero(toString(report_type2_count))) AS report_type2_count,
    sum(toFloat64OrZero(toString(report_type3_count))) AS report_type3_count,
    sum(toFloat64OrZero(toString(report_type4_count))) AS report_type4_count,
    sum(toFloat64OrZero(toString(report_type5_count))) AS report_type5_count,
    sum(toFloat64OrZero(toString(report_type6_count))) AS report_type6_count,
    sum(toFloat64OrZero(toString(report_type7_count))) AS report_type7_count,
    sum(toFloat64OrZero(toString(report_type8_count))) AS report_type8_count,
    sum(toFloat64OrZero(toString(report_type9_count))) AS report_type9_count,
    sum(toFloat64OrZero(toString(report_type10_count))) AS report_type10_count,
    sum(toFloat64OrZero(toString(report_type11_count))) AS report_type11_count,
    sum(toFloat64OrZero(toString(report_type12_count))) AS report_type12_count,
    sum(toFloat64OrZero(toString(report_type13_count))) AS report_type13_count,
    sum(toFloat64OrZero(toString(report_type14_count))) AS report_type14_count,
    sum(toFloat64OrZero(toString(report_type15_count))) AS report_type15_count,
    sum(toFloat64OrZero(toString(report_type16_count))) AS report_type16_count,
    sum(toFloat64OrZero(toString(report_type17_count))) AS report_type17_count,
    sum(toFloat64OrZero(toString(report_type18_count))) AS report_type18_count,
    sum(toFloat64OrZero(toString(report_type19_count))) AS report_type19_count,
    sum(toFloat64OrZero(toString(report_type20_count))) AS report_type20_count,
    sum(toFloat64OrZero(toString(report_type21_count))) AS report_type21_count,
    sum(toFloat64OrZero(toString(report_type22_count))) AS report_type22_count,
    sum(toFloat64OrZero(toString(report_type23_count))) AS report_type23_count,
    sum(toFloat64OrZero(toString(report_type24_count))) AS report_type24_count,
    sum(toFloat64OrZero(toString(report_type25_count))) AS report_type25_count,
    sum(toFloat64OrZero(toString(report_type26_count))) AS report_type26_count,
    sum(toFloat64OrZero(toString(report_type27_count))) AS report_type27_count,
    sum(toFloat64OrZero(toString(report_type28_count))) AS report_type28_count,
    sum(toFloat64OrZero(toString(report_type29_count))) AS report_type29_count,
    sum(toFloat64OrZero(toString(report_type30_count))) AS report_type30_count,
    sum(toFloat64OrZero(toString(report_type33_count))) AS report_type33_count,
    sum(toFloat64OrZero(toString(report_type34_count))) AS report_type34_count,
    sum(toFloat64OrZero(toString(report_type36_count))) AS report_type36_count,
    sum(toFloat64OrZero(toString(report_type37_count))) AS report_type37_count

FROM ai_security.abs_driver_behavior_sum

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND obuid IS NOT NULL
  AND toString(obuid) != ''

GROUP BY
    stat_date,
    obuid;

/* ============================================================
   06. 充电表
   粒度：stat_date + bus_id
   下载：data/tmp_vrp_06_charge_day.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_06_charge_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    toString(bus_id) AS bus_id,

    sum(toFloat64OrZero(toString(day_charge_count))) AS day_charge_count,
    sum(toFloat64OrZero(toString(night_charge_count))) AS night_charge_count,
    sum(toFloat64OrZero(toString(day_charge_soc))) AS day_charge_soc,
    sum(toFloat64OrZero(toString(night_charge_soc))) AS night_charge_soc,
    sum(toFloat64OrZero(toString(use_soc))) AS use_soc,
    sum(toFloat64OrZero(toString(run_mileage))) AS charge_run_mileage

FROM canbus.ads_day_energy_analysis

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND bus_id IS NOT NULL
  AND toString(bus_id) != ''

GROUP BY
    stat_date,
    bus_id;

/* ============================================================
   07. 空调表
   粒度：stat_date + bus_id
   下载：data/tmp_vrp_07_aircond_day.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_07_aircond_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    toString(bus_id) AS bus_id,

    sum(toFloat64OrZero(toString(open_time))) AS aircond_open_time_minutes,
    count() AS aircond_record_count

FROM canbus.ads_air_conditioner_use

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND bus_id IS NOT NULL
  AND toString(bus_id) != ''

GROUP BY
    stat_date,
    bus_id;

/* ============================================================
   08. 车辆线路班次表
   粒度：stat_date + bus_id + route_id
   下载：data/tmp_vrp_08_route_trip_day.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_08_route_trip_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
    toString(bus_id) AS bus_id,
    toString(route_id) AS route_id,

    count() AS route_trip_count

FROM canbus.ads_triplog_energy

WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
  AND bus_id IS NOT NULL
  AND toString(bus_id) != ''
  AND route_id IS NOT NULL
  AND toString(route_id) != ''

GROUP BY
    stat_date,
    bus_id,
    route_id;

/* ============================================================
   09. 线路站点静态表
   粒度：route_id
   下载：data/tmp_vrp_09_route_station_static.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_09_route_station_static
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toString(route_id) AS route_id,

    countDistinct(
        replaceRegexpAll(trimBoth(toString(route_station_name)), '\\s+', '')
    ) AS route_station_count

FROM canbus.ods_jituan_bs_route_sta

WHERE route_id IS NOT NULL
  AND toString(route_id) != ''
  AND route_station_name IS NOT NULL
  AND toString(route_station_name) != ''

GROUP BY
    route_id;

/* ============================================================
   10. 线路黑点/转弯静态表
   粒度：route_id
   下载：data/tmp_vrp_10_route_black_static.csv
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_10_route_black_static
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    route_id,

    avg(direction_black_count) AS route_black_count,
    sum(direction_turn_count) AS route_turn_count

FROM
(
    SELECT
        splitByChar('#', toString(route_ids))[1] AS route_id,
        toString(route_ids) AS route_ids_key,

        count() AS direction_black_count,
        countIf(toString(event_type) IN ('2', '3')) AS direction_turn_count

    FROM canbus.ads_event_black_spot

    WHERE route_ids IS NOT NULL
      AND toString(route_ids) != ''

    GROUP BY
        route_id,
        route_ids_key
) t

GROUP BY
    route_id;

/* ============================================================
   11. 客流表
   粒度：stat_date + number_plate
   下载：data/tmp_vrp_11_passenger_day.csv
   Python 后续用 stat_date + number_plate 映射 bus_id。
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_11_passenger_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(parseDateTimeBestEffort(toString(operate_date))) AS stat_date,
    replaceRegexpAll(trimBoth(toString(car_license)), '\\s+', '') AS number_plate,

    sum(toFloat64OrZero(toString(passenger_total))) AS passenger_total

FROM ai_security.ads_driver_passengerflux_daily

WHERE operate_date IS NOT NULL
  AND car_license IS NOT NULL
  AND toString(car_license) != ''
  AND toDate(parseDateTimeBestEffort(toString(operate_date)))
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)

GROUP BY
    stat_date,
    number_plate;

/* ============================================================
   12. 维修表
   粒度：stat_date + number_plate
   下载：data/tmp_vrp_12_repair_day.csv
   Python 后续用 stat_date + number_plate 映射 bus_id。
   ============================================================ */

CREATE TABLE ai_security.tmp_vrp_12_repair_day
ENGINE = MergeTree
ORDER BY tuple()
AS
SELECT
    toDate(f_indatetime) AS stat_date,
    replaceRegexpAll(trimBoth(toString(f_buslisence)), '\\s+', '') AS number_plate,

    uniqExact(toString(f_projectno)) AS repair_order_count

FROM ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project

WHERE f_indatetime IS NOT NULL
  AND f_buslisence IS NOT NULL
  AND toString(f_buslisence) != ''
  AND toDate(f_indatetime)
      BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
          AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)

GROUP BY
    stat_date,
    number_plate;

/* ============================================================
   13. 结果检查
   ============================================================ */

SELECT
    'tmp_vrp_01_energy_route_day' AS table_name,
    count() AS row_count,
    min(stat_date) AS min_date,
    max(stat_date) AS max_date
FROM ai_security.tmp_vrp_01_energy_route_day

UNION ALL
SELECT
    'tmp_vrp_02_static_bus',
    count(),
    NULL,
    NULL
FROM ai_security.tmp_vrp_02_static_bus

UNION ALL
SELECT
    'tmp_vrp_03_fault_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_03_fault_day

UNION ALL
SELECT
    'tmp_vrp_04_can_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_04_can_day

UNION ALL
SELECT
    'tmp_vrp_05_behavior_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_05_behavior_day

UNION ALL
SELECT
    'tmp_vrp_06_charge_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_06_charge_day

UNION ALL
SELECT
    'tmp_vrp_07_aircond_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_07_aircond_day

UNION ALL
SELECT
    'tmp_vrp_08_route_trip_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_08_route_trip_day

UNION ALL
SELECT
    'tmp_vrp_09_route_station_static',
    count(),
    NULL,
    NULL
FROM ai_security.tmp_vrp_09_route_station_static

UNION ALL
SELECT
    'tmp_vrp_10_route_black_static',
    count(),
    NULL,
    NULL
FROM ai_security.tmp_vrp_10_route_black_static

UNION ALL
SELECT
    'tmp_vrp_11_passenger_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_11_passenger_day

UNION ALL
SELECT
    'tmp_vrp_12_repair_day',
    count(),
    min(stat_date),
    max(stat_date)
FROM ai_security.tmp_vrp_12_repair_day;

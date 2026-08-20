/* ============================================================
   车辆画像风险模型：tmp_vrp_00_feature_source raw 宽表生成脚本（修复列别名版）

   修复点：
   - ClickHouse 在 CTAS 中使用 base.stat_date 这类带表别名表达式时，
     可能把输出列名保存成 `base.stat_date`，导致后续检查语句 min(stat_date) 报 Unknown identifier。
   - 本版对 SELECT 中所有输出字段都显式 AS 别名，保证 tmp_vrp_00_feature_source 中字段名为 stat_date、bus_id 等干净列名。

   输入依赖：
   ai_security.tmp_vrp_01_energy_route_day
   ai_security.tmp_vrp_02_static_bus
   ai_security.tmp_vrp_03_fault_day
   ai_security.tmp_vrp_04_can_day
   ai_security.tmp_vrp_05_behavior_day
   ai_security.tmp_vrp_06_charge_day
   ai_security.tmp_vrp_07_aircond_day
   ai_security.tmp_vrp_08_route_trip_day
   ai_security.tmp_vrp_09_route_station_static
   ai_security.tmp_vrp_10_route_black_static
   ai_security.tmp_vrp_11_passenger_day
   ai_security.tmp_vrp_12_repair_day

   输出：
   ai_security.tmp_vrp_00_feature_source

   说明：
   1. tmp_vrp_00_feature_source 只是 raw wide 下载表，不是模型特征表。
   2. 本脚本只做简单 LEFT JOIN 和 route 环境 raw 汇总。
   3. 不做中文字段、不做标签、不做 LOO、不做 rolling、不做缺失填充、不做归一化。
   4. Python 后续继续负责全部模型逻辑。
   ============================================================ */

SET max_execution_time = 0;
SET receive_timeout = 3600;
SET send_timeout = 3600;
SET connect_timeout = 60;

DROP TABLE IF EXISTS ai_security.tmp_vrp_00_feature_source;

CREATE TABLE ai_security.tmp_vrp_00_feature_source
ENGINE = MergeTree
ORDER BY tuple()
AS
WITH
    route_env_day AS
    (
        SELECT
            t.stat_date AS stat_date,
            t.bus_id AS bus_id,

            sum(ifNull(s.route_station_count, 0) * t.route_trip_count) AS denom_station_count,
            sum(ifNull(b.route_turn_count, 0) * t.route_trip_count) AS denom_turn_count,
            avg(ifNull(b.route_black_count, 0)) AS route_black_count,
            sum(t.route_trip_count) AS route_trip_count,
            uniqExact(t.route_id) AS route_cnt,

            countIf(s.route_station_count IS NULL) AS station_missing_route_cnt,
            countIf(b.route_black_count IS NULL) AS black_missing_route_cnt

        FROM ai_security.tmp_vrp_08_route_trip_day t
        LEFT JOIN ai_security.tmp_vrp_09_route_station_static s
            ON t.route_id = s.route_id
        LEFT JOIN ai_security.tmp_vrp_10_route_black_static b
            ON t.route_id = b.route_id
        GROUP BY
            t.stat_date,
            t.bus_id
    )

SELECT
    base.stat_date AS stat_date,
    base.raw_ppartition AS raw_ppartition,
    base.obuid AS obuid,
    base.bus_id AS bus_id,
    base.bus_code AS bus_code,
    base.number_plate AS number_plate,
    base.organ_id AS organ_id,
    base.organ_name AS organ_name,
    base.route_id AS route_id,
    base.route_name AS route_name,

    base.src_run_mileage AS src_run_mileage,
    base.src_energy AS src_energy,
    base.src_mileage_energy AS src_mileage_energy,
    base.src_mileage_energy2 AS src_mileage_energy2,
    base.src_total_second AS src_total_second,

    static_bus.static_bus_brand AS static_bus_brand,
    static_bus.static_total_weight AS static_total_weight,
    static_bus.static_bus_length AS static_bus_length,
    static_bus.static_battery_capacity AS static_battery_capacity,
--    static_bus.static_bus_type AS static_bus_type,
    base.static_bus_type AS static_bus_type,
    static_bus.static_bus_age AS static_bus_age,

    can.can_D30_max AS can_D30_max,
    can.can_D31_min AS can_D31_min,
    can.can_D34_max AS can_D34_max,
    can.can_D35_min AS can_D35_min,
    can.can_D29_max AS can_D29_max,
    can.can_D29_min AS can_D29_min,
    can.can_standard_voltage AS can_standard_voltage,
    can.can_standard_current AS can_standard_current,

    fault.fault_total_count AS fault_total_count,
    fault.fault_total_count_raw AS fault_total_count_raw,
    fault.fault_abs_dashboard_count AS fault_abs_dashboard_count,
    fault.fault_power_battery_count AS fault_power_battery_count,
    fault.fault_aircond_mode_count AS fault_aircond_mode_count,
    fault.fault_cell_voltage_diff_count AS fault_cell_voltage_diff_count,
    fault.fault_left_motor_count AS fault_left_motor_count,
    fault.fault_right_motor_count AS fault_right_motor_count,
    fault.fault_battery_vcu_count AS fault_battery_vcu_count,
    fault.fault_tire_temp_count AS fault_tire_temp_count,
    fault.fault_tire_pressure_count AS fault_tire_pressure_count,
    fault.fault_lubrication_count AS fault_lubrication_count,
    fault.fault_controller_air_pump_count AS fault_controller_air_pump_count,
    fault.fault_controller_steering_pump_count AS fault_controller_steering_pump_count,
    fault.fault_controller_dcdc_count AS fault_controller_dcdc_count,
    fault.fault_insulation_count AS fault_insulation_count,

    air.aircond_open_time_minutes AS aircond_open_time_minutes,
    air.aircond_record_count AS aircond_record_count,

    charge.day_charge_count AS day_charge_count,
    charge.night_charge_count AS night_charge_count,
    charge.day_charge_soc AS day_charge_soc,
    charge.night_charge_soc AS night_charge_soc,
    charge.use_soc AS use_soc,
    charge.charge_run_mileage AS charge_run_mileage,

    env.denom_station_count AS denom_station_count,
    env.denom_turn_count AS denom_turn_count,
    env.route_black_count AS route_black_count,
    env.route_trip_count AS route_trip_count,
    env.route_cnt AS route_cnt,
    env.station_missing_route_cnt AS station_missing_route_cnt,
    env.black_missing_route_cnt AS black_missing_route_cnt,

    passenger.passenger_total AS passenger_total,

    behavior.operator_code_count AS operator_code_count,
    behavior.behavior_obuid_count AS behavior_obuid_count,
    behavior.raw_behavior_row_count AS raw_behavior_row_count,
    behavior.report_type1_count AS report_type1_count,
    behavior.report_type2_count AS report_type2_count,
    behavior.report_type3_count AS report_type3_count,
    behavior.report_type4_count AS report_type4_count,
    behavior.report_type5_count AS report_type5_count,
    behavior.report_type6_count AS report_type6_count,
    behavior.report_type7_count AS report_type7_count,
    behavior.report_type8_count AS report_type8_count,
    behavior.report_type9_count AS report_type9_count,
    behavior.report_type10_count AS report_type10_count,
    behavior.report_type11_count AS report_type11_count,
    behavior.report_type12_count AS report_type12_count,
    behavior.report_type13_count AS report_type13_count,
    behavior.report_type14_count AS report_type14_count,
    behavior.report_type15_count AS report_type15_count,
    behavior.report_type16_count AS report_type16_count,
    behavior.report_type17_count AS report_type17_count,
    behavior.report_type18_count AS report_type18_count,
    behavior.report_type19_count AS report_type19_count,
    behavior.report_type20_count AS report_type20_count,
    behavior.report_type21_count AS report_type21_count,
    behavior.report_type22_count AS report_type22_count,
    behavior.report_type23_count AS report_type23_count,
    behavior.report_type24_count AS report_type24_count,
    behavior.report_type25_count AS report_type25_count,
    behavior.report_type26_count AS report_type26_count,
    behavior.report_type27_count AS report_type27_count,
    behavior.report_type28_count AS report_type28_count,
    behavior.report_type29_count AS report_type29_count,
    behavior.report_type30_count AS report_type30_count,
    behavior.report_type33_count AS report_type33_count,
    behavior.report_type34_count AS report_type34_count,
    behavior.report_type36_count AS report_type36_count,
    behavior.report_type37_count AS report_type37_count,

    repair.repair_order_count AS repair_order_count

FROM ai_security.tmp_vrp_01_energy_route_day base
LEFT JOIN ai_security.tmp_vrp_02_static_bus static_bus
    ON base.bus_id = static_bus.bus_id
LEFT JOIN ai_security.tmp_vrp_03_fault_day fault
    ON base.stat_date = fault.stat_date
   AND base.bus_id = fault.bus_id
LEFT JOIN ai_security.tmp_vrp_04_can_day can
    ON base.stat_date = can.stat_date
   AND base.number_plate = can.number_plate
LEFT JOIN ai_security.tmp_vrp_05_behavior_day behavior
    ON base.stat_date = behavior.stat_date
   AND base.obuid = behavior.obuid
LEFT JOIN ai_security.tmp_vrp_06_charge_day charge
    ON base.stat_date = charge.stat_date
   AND base.bus_id = charge.bus_id
LEFT JOIN ai_security.tmp_vrp_07_aircond_day air
    ON base.stat_date = air.stat_date
   AND base.bus_id = air.bus_id
LEFT JOIN route_env_day env
    ON base.stat_date = env.stat_date
   AND base.bus_id = env.bus_id
LEFT JOIN ai_security.tmp_vrp_11_passenger_day passenger
    ON base.stat_date = passenger.stat_date
   AND base.number_plate = passenger.number_plate
LEFT JOIN ai_security.tmp_vrp_12_repair_day repair
    ON base.stat_date = repair.stat_date
   AND base.number_plate = repair.number_plate
SETTINGS join_use_nulls = 1;

/* ============================================================
   结构检查：确认列名已经是 stat_date，而不是 base.stat_date
   ============================================================ */
DESCRIBE TABLE ai_security.tmp_vrp_00_feature_source;

/* ============================================================
   结果检查
   ============================================================ */
SELECT
    'tmp_vrp_00_feature_source' AS table_name,
    count() AS row_count,
    min(stat_date) AS min_date,
    max(stat_date) AS max_date,
    countIf(static_bus_type IS NOT NULL AND static_bus_type != '') AS bus_type_not_null,
    countIf(fault_total_count IS NOT NULL) AS fault_not_null,
    countIf(can_D30_max IS NOT NULL OR can_D31_min IS NOT NULL) AS can_not_null,
    countIf(passenger_total IS NOT NULL) AS passenger_not_null,
    countIf(repair_order_count IS NOT NULL) AS repair_not_null
FROM ai_security.tmp_vrp_00_feature_source;

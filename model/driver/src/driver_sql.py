from datetime import datetime, timedelta


def predict_1h_sql(start_date:str,end_date:str)->str:
    start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
    str_yymmdd = start_date.strftime('%Y%m%d')
    sql=f"""
        /**************************** 1. 基础片段：取所有驾驶员（昨天数据）****************************/
        WITH all_drivers AS (
            SELECT DISTINCT 
                ojbe.employee_id AS drv_id ,
                ojbe.employee_name AS drv_name ,
                ojbe.organ_id as organ_id,
                f.organ_name as organ_name,
                gg.route_name 
                FROM canbus.ods_jituan_bs_employee ojbe  
                GLOBAL inner join canbus.ods_jituan_bs_organ f
                on ojbe.organ_id=f.organ_id 
                GLOBAL inner join canbus.ods_jituan_bs_route gg 
                on ojbe.route_id=gg.route_id
        ),
        
        -- 昨天的日期窗口
        yesterday_window AS (
            SELECT
                drv_name,
                drv_id,
                toDateTime('{start_date}') AS start_date,
                toDateTime('{start_date}') + INTERVAL 1 HOUR - INTERVAL 1 SECOND AS end_date
            FROM all_drivers
        ),
        
        /**************************** 2. 基础行为片段（原表） ****************************/
        yesterday_30m_bhv AS (
            SELECT
                e.employee_name AS driver_name,
                e.employee_id as driver_id,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
            GLOBAL LEFT JOIN (select * from canbus.ods_communication_driver_behavior where ppartition='{str_yymmdd}') b
              ON e.qualification_no = b.operator_code
            WHERE b.report_time BETWEEN r.start_date AND r.end_date
            GROUP BY e.employee_id, 
                     e.employee_name,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END
        ),
        
        all_30m_bhv_with_traffic AS (
            SELECT * FROM yesterday_30m_bhv
        ),
        
        
        /**************************** 4. 宽表输出 ****************************/
        driver_list AS (
            SELECT drv_name AS driver_name,
            drv_id as driver_id,
            organ_id
        FROM all_drivers
        )
        
        SELECT
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name, 
            
            -- 原37列基础行为
            SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END) AS ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END) AS upslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END) AS downslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END) AS bad_turn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END) AS stop_ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END) AS no_n_on_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END) AS global_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END) AS decel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END) AS accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END) AS before_move_safe_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END) AS section_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END) AS right_turn_no_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END) AS left_turn_no_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END) AS flat_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END) AS door_op_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END) AS sudden_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END) AS sudden_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END) AS refuse_ride_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END) AS stall_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END) AS neutral_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END) AS start_accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END) AS junction_reaccel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END) AS junction_heavy_gas_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END) AS junction_spd_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END) AS door_open_before_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END) AS illegal_brake_on_entry_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END) AS illegal_main_power_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END) AS illegal_hand_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END) AS illegal_ac_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END) AS illegal_door_switch_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END) AS start_with_open_door_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END) AS skip_station_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt
            
        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_employee e 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_organ o 
            ON d.organ_id = o.organ_id
        --GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1)
        
        GROUP BY 
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name
            
        ORDER BY d.driver_name;
                """
    return sql

def train_tmp_driver_1h_sql(start_date:str,end_date:str):
    sql=f"""
        WITH 
                driver_with_routeid AS ( 
                        SELECT DISTINCT 
                        ojbe.employee_id AS driver_id ,
                        ojbe.employee_name AS driver_name ,
                        ojbe.organ_id as organ_id,
                        f.organ_name as organ_name,
                        gg.route_name 
                        FROM canbus.ods_jituan_bs_employee ojbe  
                        GLOBAL inner join canbus.ods_jituan_bs_organ f
                        on ojbe.organ_id=f.organ_id 
                        GLOBAL inner join canbus.ods_jituan_bs_route gg 
                        on ojbe.route_id=gg.route_id
                        ),
                
                accident_info AS (
                    SELECT t.driver_id AS driver_id, 
                           t.driver_name AS driver_name,
                           toDateTime(t.accident_date) AS accident_date
                    FROM (
                        SELECT c.driver_id AS driver_id, c.driver_name AS driver_name, toDateTime(ac.accident_date) AS accident_date
                        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle ac
                        GLOBAL JOIN driver_with_routeid c
                        ON substring(c.driver_id, position(c.driver_id, '-') + 1) = substring(ac.employee_code, position(ac.employee_code, '-') + 1)
                           OR (ac.driver_name = c.driver_name
                               AND ac.line_name = c.route_name
                               AND c.organ_name = CASE WHEN ac.org_name IN ('佛广集团','增从片区','马会巴士')
                                                       THEN ac.motorcade
                                                       ELSE concat(ac.org_name, '-', ac.motorcade) END)
                        WHERE ac.accident_liability = '048005'
                          AND toDate(ac.accident_date) >= toDate('2025-01-01')
                          AND ac.dept_name NOT IN ('佛广集团','一汽公司','粤港澳公司')
                        GROUP BY c.driver_id, c.driver_name, toDateTime(ac.accident_date)
                    ) t
                ),
                
                no_accident_drivers AS (
                    SELECT driver_id, driver_name
                    FROM driver_with_routeid
                    WHERE driver_id GLOBAL NOT IN (SELECT driver_id FROM accident_info)
                ),
                
                accident_daily AS (
                    SELECT DISTINCT
                        driver_id,
                        driver_name,
                        accident_date AS label_date
                    FROM accident_info
                ),
                
                rand_daily AS (
                    SELECT
                        driver_id,
                        driver_name,
                        rand_date AS label_date
                    FROM (
                        SELECT
                            nd.driver_id,
                            nd.driver_name,
                            dr.min_date + rand() %% greatest(1, toUInt64(dr.max_date - dr.min_date)) AS rand_date
                        FROM no_accident_drivers nd
                        GLOBAL JOIN (
                            SELECT
                                e.employee_id AS driver_id,
                                MIN(b.report_time) AS min_date,
                                MAX(b.report_time) AS max_date
                            FROM ai_security.ods_communication_driver_behavior_month b
                            GLOBAL JOIN canbus.ods_jituan_bs_employee e ON b.operator_code = e.qualification_no
                            WHERE toDate(b.report_time)  >= toDate('2026-01-01')
                            GROUP BY e.employee_id
                        ) dr ON nd.driver_id = dr.driver_id
                    )
                )
                
                SELECT 
                    driver_id,
                    driver_name,
                    label_date,
                    1 AS has_accident_label
                FROM accident_daily
                UNION ALL
                SELECT 
                    driver_id,
                    driver_name,
                    label_date,
                    0 AS has_accident_label
                FROM rand_daily;
    """
    return sql

def train_tmp_driver_action_count_1h_sql(start_date:str,end_date:str):
    sql=f"""
    WITH 
        all_daily AS (
            SELECT * FROM ai_security.tmp_driver_1h
        ),
        
        accident_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                WHERE toDateTime(b.report_time) BETWEEN toDateTime(w.label_date) - INTERVAL 1 HOUR AND toDateTime(w.label_date)
                  AND w.has_accident_label = 1
                  AND toDate(b.report_time) >= toDate('2025-12-08')
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END
                    
                    UNION ALL
                
        
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
                WHERE toDateTime(b.rcrd_time) BETWEEN toDateTime(w.label_date) - INTERVAL 1 HOUR AND toDateTime(w.label_date)
                  AND w.has_accident_label = 1
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name,w.label_date, b.drv_sct_bhv
            ) t
            GROUP BY driver_id, driver_name,label_date, drv_sct_bhv
        ),
        
        random_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                WHERE toDateTime(b.report_time) BETWEEN toDateTime(w.label_date) - INTERVAL 1 HOUR AND toDateTime(w.label_date)
                  AND w.has_accident_label = 0
                  AND toDate(b.report_time)  >= toDate('2025-12-08' )
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END
                    
                    UNION ALL
                    
                    SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
                WHERE toDateTime(b.rcrd_time) BETWEEN toDateTime(w.label_date) - INTERVAL 1 HOUR AND toDateTime(w.label_date)
                  AND w.has_accident_label = 0
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name, w.label_date,b.drv_sct_bhv
            ) t
            GROUP BY driver_id, driver_name,label_date, drv_sct_bhv
        )
        
        SELECT driver_id,driver_name,label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM accident_daily_bhv
        UNION ALL
        SELECT driver_id,driver_name,label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM random_daily_bhv
    """
    return sql

def train_1h_sql(start_date:str,end_date:str)->str:
    sql=f"""
        SELECT
            w.driver_id,
            w.driver_name,
            -- 行为特征（当天次数）
            SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END) AS ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END) AS upslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END) AS downslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END) AS bad_turn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END) AS stop_ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END) AS no_n_on_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END) AS global_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END) AS decel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END) AS accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END) AS before_move_safe_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END) AS section_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END) AS right_turn_no_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END) AS left_turn_no_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END) AS flat_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END) AS door_op_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END) AS sudden_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END) AS sudden_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END) AS refuse_ride_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END) AS stall_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END) AS neutral_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END) AS start_accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END) AS junction_reaccel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END) AS junction_heavy_gas_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END) AS junction_spd_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END) AS door_open_before_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END) AS illegal_brake_on_entry_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END) AS illegal_main_power_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END) AS illegal_hand_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END) AS illegal_ac_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END) AS illegal_door_switch_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END) AS start_with_open_door_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END) AS skip_station_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
            -- 标签
            w.has_accident_label
        FROM ai_security.tmp_driver_1h w
        LEFT JOIN canbus.ods_jituan_bs_employee e 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
        LEFT JOIN ai_security.tmp_driver_action_count_1h b 
            ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1) AND w.label_date = b.label_date  
        GROUP BY 
            w.driver_id,
            w.driver_name,
            --w.label_date,
            w.has_accident_label
        ORDER BY w.driver_name
    """
    return sql

def predict_1d_sql(start_date:str,end_date:str)->str:
    sql=f"""
            /**************************** 1. 基础片段：取所有驾驶员（昨天数据）****************************/
        WITH all_drivers AS (
            SELECT DISTINCT 
                ojbe.employee_id AS drv_id ,
                ojbe.employee_name AS drv_name ,
                ojbe.organ_id as organ_id,
                f.organ_name as organ_name,
                gg.route_name 
                FROM canbus.ods_jituan_bs_employee ojbe  
                GLOBAL inner join canbus.ods_jituan_bs_organ f
                on ojbe.organ_id=f.organ_id 
                GLOBAL inner join canbus.ods_jituan_bs_route gg 
                on ojbe.route_id=gg.route_id
        ),
        
        -- 昨天的日期窗口
        yesterday_window AS (
            SELECT
                drv_name,
                drv_id,
                toDate('{start_date}') AS start_date,
                toDate('{end_date}') + INTERVAL 1 DAY - INTERVAL 1 SECOND AS end_date
            FROM all_drivers
        ),
        
        /**************************** 2. 基础行为片段（原表） ****************************/
        yesterday_30m_bhv AS (
            SELECT
                e.employee_name AS driver_name,
                e.employee_id as driver_id,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
            GLOBAL LEFT JOIN ai_security.ods_communication_driver_behavior_month b
              ON e.qualification_no = b.operator_code
            WHERE b.report_time BETWEEN r.start_date AND r.end_date
            GROUP BY e.employee_id, 
                     e.employee_name,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END
        ),
        
        /**************************** 2.1 ADAS行为片段 ****************************/
        yesterday_adas_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
            WHERE e.happentime BETWEEN r.start_date AND r.end_date
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),
        
        /**************************** 2.2 aebs行为片段 ****************************/
        yesterday_aebs_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            WHERE toDate(e.warnTime) BETWEEN r.start_date AND r.end_date
              AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END
        ),
        
        all_30m_bhv AS (
            SELECT * FROM yesterday_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_adas_bhv
            UNION ALL
            SELECT * FROM yesterday_aebs_bhv
        ),
        
        /**************************** 2.2 交通违法片段 ****************************/
        yesterday_traffic_illegal AS (
            SELECT
                t.driver_name,
                t.employee_code as driver_id,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            WHERE t.illegal_date = toDate(r.start_date)
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
            GROUP BY t.employee_code, 
                     t.driver_name,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        ),
        
        all_30m_bhv_with_traffic AS (
            SELECT * FROM all_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_traffic_illegal
        ),
        
        /************************ 3. 健康指标（昨天）************************/
        
        health_daily AS (
            SELECT
                h.driver_code AS driver_id,
                toDate(h.happen_time) AS date_key,
                argMax(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END, happen_time) AS heart_rate_avg,
                argMax(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END, happen_time) AS alcohol_avg,
                argMax(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END, happen_time) AS sbp_avg,
                argMax(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END, happen_time) AS dbp_avg,
                argMax(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END, happen_time) AS pulse_avg,
                argMax(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END, happen_time) AS spo2_avg,
                argMax(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END, happen_time) AS temp_avg
            FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.driver_code, position(h.driver_code, '-') + 1)
            WHERE toDate(h.happen_time) = toDate('{start_date}')  -- 取昨天
                AND h.vname IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
            GROUP BY h.driver_code, toDate(h.happen_time)
        ),
        
        
        /************************ 3.1 工时与里程指标（昨天）************************/
        workhour_daily AS (
            SELECT
                h.employee_id AS driver_id,
                h.employee_name AS driver_name,
                toDate(h.ppartition) ,
                SUM(toFloat64OrNull(h.safty_mileage)) AS safty_mileage,
                SUM(toFloat64OrNull(h.work_hour)) AS daily_work_hour
            FROM canbus.ads_driver_workhour h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.employee_id, position(h.employee_id, '-') + 1)
            WHERE toDate(parseDateTimeBestEffort(h.ppartition)) = toDate('{start_date}')
            GROUP BY h.employee_id, h.employee_name, toDate(h.ppartition)
        ),
            
        
        pass_station_list AS(
            SELECT 
            drive_date,
            employee_id ,
            driver_name,
            toFloat64(sum(station_count)) AS total_station_count,
            count(*) AS trip_count
            FROM (
                SELECT 
                    toDate(t.ppartition) AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.bus_id,
                    t.route_id,
                    t.from_station,
                    t.to_station,
                    abs(s2.min_sort - s1.min_sort) + 1 AS station_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN (
                    -- 站点去重：同线路同站名取最小站序
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
                GLOBAL LEFT JOIN (
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
                WHERE s1.min_sort IS NOT NULL 
                  AND s2.min_sort IS NOT NULL
                  AND toDate(t.ppartition) = toDate('{start_date}')
            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),
        
        pass_turn_list AS(
            SELECT 
                drive_date,
                employee_id ,
                driver_name,
                toFloat64(sum(turn_count)) AS total_turn_count
            FROM (
                
                SELECT
                    toDate(t.ppartition) AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.route_id,       
                    COUNT(b.event_type) AS turn_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
                ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
                    AND b.event_type IN (2, 3)
                WHERE toDate(t.ppartition) = toDate('{start_date}')
                GROUP BY drive_date, employee_id, driver_name, t.route_id
            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),
        
        mental_list AS (
                SELECT 
                m.driver_name,
                case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
                m.heart_level_label AS heart_level_label, 
                m.follow_year_month,n.drv_id,  
                m.line_name 
                FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
                GLOBAL inner join all_drivers n on m.driver_name=n.drv_name  
                and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
                WHERE m.follow_year_month = formatDateTime(toDate('{start_date}'), '%%Y-%%m') 
                ),
        
        
        /**************************** 4. 宽表输出 ****************************/
        driver_list AS (
            SELECT drv_name AS driver_name,
            drv_id as driver_id,
            organ_id
        FROM all_drivers
        ),
        
        ---历史事故---
        driver_accident AS (
            SELECT 
                org_code,
                org_name,
                CASE 
                    WHEN POSITION('-' IN line_code) > 0 
                    THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
                    ELSE line_code END AS line_code,
                line_name,
                driver_name,
                yearly,
                accident_num 
            FROM  ai_security.ads_driver_accident_yearly
        ), 
         
         
        s_result AS (
            SELECT a.*,b.employee_name,b.organ_id,b.organ_name  
            FROM driver_accident a 
            GLOBAL LEFT OUTER JOIN (
                SELECT a.*,b.organ_name  
                FROM ai_security.ods_jituan_bs_employee a 
                GLOBAL INNER JOIN  ai_security.ods_jituan_bs_organ b 
                ON a.organ_id=b.organ_id ) b 
            ON a.driver_name=b.employee_name 
            WHERE b.organ_name LIKE CONCAT('%%',a.org_name,'%%') 
        ),
        
        
        -- 历史事故统计
        accident_yearly AS (
            SELECT 
                d.driver_name,
                d.driver_id,
                a.organ_id,
                a.line_code,
                COALESCE(SUM(a.accident_num), 0) AS total_accidents
            FROM driver_list d
            GLOBAL LEFT JOIN s_result a
                ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
                AND a.yearly IN (2023, 2024)
            GROUP BY d.driver_name,d.driver_id,a.organ_id,a.line_code
        ),
        
        avg_mileage AS (
            SELECT AVG(safty_mileage) AS avg_val
            FROM workhour_daily
            WHERE safty_mileage > 0   -- 排除0和NULL
        ),
        
        avg_pass_station AS (
            SELECT AVG(total_station_count) AS avg_val
            FROM pass_station_list
            WHERE total_station_count > 0   -- 排除0和NULL
        ),
        
        avg_pass_turn AS (
            SELECT AVG(total_turn_count) AS avg_val
            FROM pass_turn_list
            WHERE total_turn_count > 0   -- 排除0和NULL
        )
        
        SELECT
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name, 
            
            -- 员工基础信息（4列）
            e.sex AS gender,
            e.age,
            e.education_level,
            dateDiff('year', e.entry_time, now()) AS driving_years,
            e.route_id,
            
            -- 工时与里程指标（3列）
            w.safty_mileage,
            --w.cumulative_safty_mileage,
            w.daily_work_hour,
            w.daily_work_hour as work_hour,
            y.total_accidents,
            
            -- 原37列基础行为
            SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS upslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS downslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS bad_turn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stop_ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS no_n_on_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS global_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS decel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS before_move_safe_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS section_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS right_turn_no_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS left_turn_no_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS flat_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS door_op_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS refuse_ride_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stall_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS neutral_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0),am.avg_val) AS junction_reaccel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_heavy_gas_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_spd_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS door_open_before_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_brake_on_entry_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_main_power_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_hand_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_ac_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_door_switch_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_with_open_door_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS skip_station_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
            
            -- 9列ADAS行为
            SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distance_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS lane_keep_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distraction_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS pedestrian_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS collision_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
            
            -- 3列失能行为
            SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
            
            -- 3列交通违法
            SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
            
            -- 7列健康指标
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,
            
            -- 1列心理指标
            m2.heart_level_label
            
        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_employee e 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_organ o 
            ON d.organ_id = o.organ_id
        GLOBAL LEFT JOIN workhour_daily w 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(w.driver_id, position(w.driver_id, '-') + 1)
        --GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1)
        GLOBAL LEFT JOIN health_daily h 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(h.driver_id, position(h.driver_id, '-') + 1)
        GLOBAL LEFT JOIN pass_station_list p 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p.employee_id, position(p.employee_id, '-') + 1)
        GLOBAL LEFT JOIN pass_turn_list p2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p2.employee_id, position(p2.employee_id, '-') + 1)
        GLOBAL LEFT JOIN mental_list m2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(m2.drv_id, position(m2.drv_id, '-') + 1)
        GLOBAL LEFT JOIN (select driver_id,driver_name,sum(total_accidents) as total_accidents from accident_yearly group by driver_id,driver_name) y
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(y.driver_id, position(y.driver_id, '-') + 1)
        GLOBAL CROSS JOIN avg_mileage am
        GLOBAL CROSS JOIN avg_pass_station aps
        GLOBAL CROSS JOIN avg_pass_turn apt
        
        GROUP BY 
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name,
            e.sex, 
            e.age, 
            e.education_level, 
            e.route_id,
            driving_years,
            --w.cumulative_safty_mileage,
            w.safty_mileage,
            w.daily_work_hour,
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,
            m2.heart_level_label,
            --m.mode_value,
            p.total_station_count,
            p2.total_turn_count,
            y.total_accidents,
            am.avg_val,
            apt.avg_val,
            aps.avg_val
            
        ORDER BY d.driver_name;

    """
    return sql


def predict_1d_sql_new(start_date: str, end_date: str) -> str:
    sql = f"""
            /**************************** 1. 基础片段：取所有驾驶员（昨天数据）****************************/
        WITH all_drivers AS (
            SELECT DISTINCT 
                ojbe.employee_id AS drv_id ,
                ojbe.employee_name AS drv_name ,
                ojbe.organ_id as organ_id,
                f.organ_name as organ_name,
                gg.route_name 
                FROM canbus.ods_jituan_bs_employee ojbe  
                GLOBAL inner join canbus.ods_jituan_bs_organ f
                on ojbe.organ_id=f.organ_id 
                GLOBAL inner join canbus.ods_jituan_bs_route gg 
                on ojbe.route_id=gg.route_id
        ),

        -- 一周日期窗口
        yesterday_window AS (
            SELECT
                drv_name,
                drv_id,
                (toDate('{start_date}')- INTERVAL 14 DAY) AS start_date,
                (toDate('{start_date}') - INTERVAL 7 DAY) AS end_date
            FROM all_drivers
        ),

        /**************************** 2. 基础行为片段（原表） ****************************/
        yesterday_30m_bhv AS (
            SELECT
                e.employee_name AS driver_name,
                e.employee_id as driver_id,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
            GLOBAL LEFT JOIN ai_security.ods_communication_driver_behavior_month b
              ON e.qualification_no = b.operator_code
            WHERE b.report_time BETWEEN r.start_date AND r.end_date
            GROUP BY e.employee_id, 
                     e.employee_name,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END
        ),

        /**************************** 2.1 ADAS行为片段 ****************************/
        yesterday_adas_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
            WHERE e.happentime BETWEEN r.start_date AND r.end_date
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),

        /**************************** 2.2 aebs行为片段 ****************************/
        yesterday_aebs_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            WHERE toDate(e.warnTime) BETWEEN r.start_date AND r.end_date
              AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END
        ),

        all_30m_bhv AS (
            SELECT * FROM yesterday_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_adas_bhv
            UNION ALL
            SELECT * FROM yesterday_aebs_bhv
        ),

        /**************************** 2.2 交通违法片段 ****************************/
        yesterday_traffic_illegal AS (
            SELECT
                t.driver_name,
                t.employee_code as driver_id,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
           -- WHERE t.illegal_date = toDate(r.start_date)
            where t.illegal_date BETWEEN r.start_date AND r.end_date
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
            GROUP BY t.employee_code, 
                     t.driver_name,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        ),

        all_30m_bhv_with_traffic AS (
            SELECT * FROM all_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_traffic_illegal
        ),

        /************************ 3. 健康指标（昨天）************************/

        health_daily AS (
            SELECT
                h.driver_code AS driver_id,
                toDate('{start_date}') AS date_key,
                ifnull(avg(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END), 0) AS heart_rate_avg,
                ifnull(avg(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END), 0) AS alcohol_avg,
                ifnull(avg(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END), 0) AS sbp_avg,
                ifnull(avg(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END), 0) AS dbp_avg,
                ifnull(avg(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END), 0) AS pulse_avg,
                ifnull(avg(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END), 0) AS spo2_avg,
                ifnull(avg(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END), 0) AS temp_avg
            FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.driver_code, position(h.driver_code, '-') + 1)
           -- WHERE toDate(h.happen_time) = toDate('{start_date}')  -- 取昨天
             where toDate(h.happen_time) BETWEEN  (toDate('{start_date}')- INTERVAL 14 DAY) AND  (toDate('{start_date}')- INTERVAL 7 DAY)
                AND h.vname IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
            GROUP BY h.driver_code 
            --, toDate(h.happen_time)
        ),


        /************************ 3.1 工时与里程指标（昨天）************************/
        workhour_daily AS (
            SELECT
                h.employee_id AS driver_id,
                h.employee_name AS driver_name,
                toDate('{start_date}') as ppartition,
                SUM(toFloat64OrNull(h.safty_mileage)) AS safty_mileage,
                SUM(toFloat64OrNull(h.work_hour)) AS daily_work_hour
            FROM canbus.ads_driver_workhour h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.employee_id, position(h.employee_id, '-') + 1)
            -- WHERE toDate(parseDateTimeBestEffort(h.ppartition)) = toDate('{start_date}')
            where toDate(parseDateTimeBestEffort(h.ppartition))  BETWEEN  (toDate('{start_date}')- INTERVAL 14 DAY) AND  (toDate('{start_date}')- INTERVAL 7 DAY)
            GROUP BY h.employee_id, h.employee_name
            -- , toDate(h.ppartition)
        ),


        pass_station_list AS(
            SELECT 
            drive_date,
            employee_id ,
            driver_name,
            toFloat64(sum(station_count)) AS total_station_count,
            count(*) AS trip_count
            FROM (
                SELECT 
                    toDate('{start_date}') AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.bus_id,
                    t.route_id,
                    t.from_station,
                    t.to_station,
                    abs(s2.min_sort - s1.min_sort) + 1 AS station_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN (
                    -- 站点去重：同线路同站名取最小站序
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
                GLOBAL LEFT JOIN (
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
                WHERE s1.min_sort IS NOT NULL 
                  AND s2.min_sort IS NOT NULL
                 -- AND toDate(t.ppartition) = toDate('{start_date}')
                  AND toDate(t.ppartition)  BETWEEN  (toDate('{start_date}')- INTERVAL 14 DAY) AND  (toDate('{start_date}')- INTERVAL 7 DAY)

            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),

        pass_turn_list AS(
            SELECT 
                drive_date,
                employee_id ,
                driver_name,
                toFloat64(sum(turn_count)) AS total_turn_count
            FROM (

                SELECT
                    toDate('{start_date}') AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.route_id,       
                    COUNT(b.event_type) AS turn_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
                ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
                    AND b.event_type IN (2, 3)
                -- WHERE toDate(t.ppartition) = toDate('{start_date}')
                where toDate(t.ppartition)  BETWEEN  (toDate('{start_date}')- INTERVAL 14 DAY) AND  (toDate('{start_date}')- INTERVAL 7 DAY)
                GROUP BY drive_date, employee_id, driver_name, t.route_id
            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),

        mental_list AS (
                SELECT 
                m.driver_name,
                case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
                m.heart_level_label AS heart_level_label, 
                m.follow_year_month,n.drv_id,  
                m.line_name 
                FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
                GLOBAL inner join all_drivers n on m.driver_name=n.drv_name  
                and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
                WHERE m.follow_year_month = formatDateTime(toDate('{start_date}'), '%%Y-%%m') 
                ),


        /**************************** 4. 宽表输出 ****************************/
        driver_list AS (
            SELECT drv_name AS driver_name,
            drv_id as driver_id,
            organ_id
        FROM all_drivers
        ),

        ---历史事故---
        driver_accident AS (
            SELECT 
                org_code,
                org_name,
                CASE 
                    WHEN POSITION('-' IN line_code) > 0 
                    THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
                    ELSE line_code END AS line_code,
                line_name,
                driver_name,
                yearly,
                accident_num 
            FROM  ai_security.ads_driver_accident_yearly
        ), 


        s_result AS (
            SELECT a.*,b.employee_name,b.organ_id,b.organ_name  
            FROM driver_accident a 
            GLOBAL LEFT OUTER JOIN (
                SELECT a.*,b.organ_name  
                FROM ai_security.ods_jituan_bs_employee a 
                GLOBAL INNER JOIN  ai_security.ods_jituan_bs_organ b 
                ON a.organ_id=b.organ_id ) b 
            ON a.driver_name=b.employee_name 
            WHERE b.organ_name LIKE CONCAT('%%',a.org_name,'%%') 
        ),


        -- 历史事故统计
        accident_yearly AS (
            SELECT 
                d.driver_name,
                d.driver_id,
                a.organ_id,
                a.line_code,
                COALESCE(SUM(a.accident_num), 0) AS total_accidents
            FROM driver_list d
            GLOBAL LEFT JOIN s_result a
                ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
                AND a.yearly IN (2023, 2024)
            GROUP BY d.driver_name,d.driver_id,a.organ_id,a.line_code
        ),

        avg_mileage AS (
            SELECT AVG(safty_mileage) AS avg_val
            FROM workhour_daily
            WHERE safty_mileage > 0   -- 排除0和NULL
        ),

        avg_pass_station AS (
            SELECT AVG(total_station_count) AS avg_val
            FROM pass_station_list
            WHERE total_station_count > 0   -- 排除0和NULL
        ),

        avg_pass_turn AS (
            SELECT AVG(total_turn_count) AS avg_val
            FROM pass_turn_list
            WHERE total_turn_count > 0   -- 排除0和NULL
        )

        SELECT
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name, 

            -- 员工基础信息（4列）
            e.sex AS gender,
            e.age,
            e.education_level,
            dateDiff('year', e.entry_time, now()) AS driving_years,
            e.route_id,

            -- 工时与里程指标（3列）
            w.safty_mileage,
            --w.cumulative_safty_mileage,
            w.daily_work_hour,
            w.daily_work_hour as work_hour,
            y.total_accidents,

            -- 原37列基础行为
            SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS upslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS downslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS bad_turn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stop_ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS no_n_on_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS global_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS decel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS before_move_safe_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS section_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS right_turn_no_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS left_turn_no_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS flat_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS door_op_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS refuse_ride_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stall_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS neutral_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0),am.avg_val) AS junction_reaccel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_heavy_gas_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_spd_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS door_open_before_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_brake_on_entry_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_main_power_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_hand_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_ac_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_door_switch_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_with_open_door_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS skip_station_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,

            -- 9列ADAS行为
            SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distance_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS lane_keep_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distraction_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS pedestrian_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS collision_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,

            -- 3列失能行为
            SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,

            -- 3列交通违法
            SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,

            -- 7列健康指标
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,

            -- 1列心理指标
            m2.heart_level_label

        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_employee e 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_organ o 
            ON d.organ_id = o.organ_id
        GLOBAL LEFT JOIN workhour_daily w 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(w.driver_id, position(w.driver_id, '-') + 1)
        --GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1)
        GLOBAL LEFT JOIN health_daily h 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(h.driver_id, position(h.driver_id, '-') + 1)
        GLOBAL LEFT JOIN pass_station_list p 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p.employee_id, position(p.employee_id, '-') + 1)
        GLOBAL LEFT JOIN pass_turn_list p2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p2.employee_id, position(p2.employee_id, '-') + 1)
        GLOBAL LEFT JOIN mental_list m2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(m2.drv_id, position(m2.drv_id, '-') + 1)
        GLOBAL LEFT JOIN (select driver_id,driver_name,sum(total_accidents) as total_accidents from accident_yearly group by driver_id,driver_name) y
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(y.driver_id, position(y.driver_id, '-') + 1)
        GLOBAL CROSS JOIN avg_mileage am
        GLOBAL CROSS JOIN avg_pass_station aps
        GLOBAL CROSS JOIN avg_pass_turn apt

        GROUP BY 
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name,
            e.sex, 
            e.age, 
            e.education_level, 
            e.route_id,
            driving_years,
            --w.cumulative_safty_mileage,
            w.safty_mileage,
            w.daily_work_hour,
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,
            m2.heart_level_label,
            --m.mode_value,
            p.total_station_count,
            p2.total_turn_count,
            y.total_accidents,
            am.avg_val,
            apt.avg_val,
            aps.avg_val

        ORDER BY d.driver_name;

    """
    return sql

def train_tmp_driver_1d_sql(start_date:str,end_date:str)->str:
    sql=f"""
        WITH 
    driver_with_routeid AS ( 
            SELECT DISTINCT 
            ojbe.employee_id AS driver_id ,
            ojbe.employee_name AS driver_name ,
            ojbe.organ_id as organ_id,
            f.organ_name as organ_name,
            gg.route_name 
            FROM canbus.ods_jituan_bs_employee ojbe  
            GLOBAL inner join canbus.ods_jituan_bs_organ f
            on ojbe.organ_id=f.organ_id 
            GLOBAL inner join canbus.ods_jituan_bs_route gg 
            on ojbe.route_id=gg.route_id
            ),
    
    accident_info AS (
        SELECT t.driver_id AS driver_id, 
               t.driver_name AS driver_name,
               toDate(t.accident_date) AS accident_date
        FROM (
            SELECT c.driver_id AS driver_id, c.driver_name AS driver_name, toDate(ac.accident_date) AS accident_date
            FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle ac
            GLOBAL JOIN driver_with_routeid c
            ON substring(c.driver_id, position(c.driver_id, '-') + 1) = substring(ac.employee_code, position(ac.employee_code, '-') + 1)
               OR (ac.driver_name = c.driver_name
                   AND ac.line_name = c.route_name
                   AND c.organ_name = CASE WHEN ac.org_name IN ('佛广集团','增从片区','马会巴士')
                                           THEN ac.motorcade
                                           ELSE concat(ac.org_name, '-', ac.motorcade) END)
            WHERE ac.accident_liability = '048005'
              AND toDate(ac.accident_date) >= toDate('2025-01-01') 
              AND toDate(ac.accident_date) <= toDate('{end_date}')
              AND ac.dept_name NOT IN ('佛广集团','一汽公司','粤港澳公司')
            GROUP BY c.driver_id, c.driver_name, toDate(ac.accident_date)
        ) t
    ),
    no_accident_drivers AS (
        SELECT driver_id, driver_name
        FROM driver_with_routeid
        WHERE driver_id GLOBAL NOT IN (SELECT driver_id FROM accident_info)
    ),
    
    accident_daily AS (
        SELECT DISTINCT
            driver_id,
            driver_name,
            accident_date AS label_date
        FROM accident_info
    ),
    
    -- 随机日为标签日，特征日为前一天
    rand_daily AS (
        SELECT
            driver_id,
            driver_name,
            rand_date AS label_date
        FROM (
            SELECT
                nd.driver_id,
                nd.driver_name,
                dr.min_date + rand() %% greatest(1, toUInt64(dr.max_date - dr.min_date)) AS rand_date
            FROM no_accident_drivers nd
            GLOBAL JOIN (
                SELECT
                    e.employee_id AS driver_id,
                    MIN(toDate(b.report_time)) AS min_date,
                    MAX(toDate(b.report_time)) AS max_date
                FROM ai_security.ods_communication_driver_behavior_month b
                GLOBAL JOIN canbus.ods_jituan_bs_employee e ON b.operator_code = e.qualification_no
                WHERE toDate(b.report_time)  >= toDate('2025-01-01') 
                    AND toDate(b.report_time) <= toDate('{end_date}')
                GROUP BY e.employee_id
            ) dr ON nd.driver_id = dr.driver_id
        )
    )
    
    SELECT 
        ifnull(driver_id,'') as driver_id,
        ifnull(driver_name,'')  as driver_name,
        label_date,
        1 AS has_accident_label
    FROM accident_daily
    UNION ALL
    SELECT 
        ifnull(driver_id,'') as driver_id,
        ifnull(driver_name,'') as driver_name,
        label_date,
        0 AS has_accident_label
    FROM rand_daily;
        """
    return sql

def train_tmp_driver_action_count_1d_sql(start_date: str, end_date: str) -> str:
    sql = f"""
            WITH 
        all_daily AS (
            SELECT * FROM ai_security.tmp_driver_1d
        ),
        -- 事故组行为（当天）
        accident_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                WHERE toDate(b.report_time) = toDate(w.label_date)
                  AND w.has_accident_label = 1
                  AND toDate(b.report_time) >= toDate('2025-12-08')
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END

                    UNION ALL


                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
                WHERE toDate(b.rcrd_time) = toDate(w.label_date)
                  AND w.has_accident_label = 1
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name,w.label_date, b.drv_sct_bhv
            ) t
            GROUP BY driver_id, driver_name,label_date, drv_sct_bhv
        ),

        random_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                WHERE toDate(b.report_time) = toDate(w.label_date)
                  AND w.has_accident_label = 0
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END

                    UNION ALL

                    SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
                WHERE toDate(b.rcrd_time) = toDate(w.label_date)
                  AND w.has_accident_label = 0
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name, w.label_date,b.drv_sct_bhv
            ) t
            GROUP BY driver_id, driver_name,label_date, drv_sct_bhv
        ),

        accident_daily_adas AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
            WHERE toDate(e.happentime) = toDate(w.label_date)
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
              AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name, w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),

        random_daily_adas AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
            WHERE toDate(e.happentime) = toDate(w.label_date)
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
              AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),

        accident_daily_aebs AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            WHERE toDate(e.warnTime) =toDate(w.label_date)
            AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name,w.label_date, 
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),

        random_daily_aebs AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            WHERE toDate(e.warnTime) =toDate(w.label_date)
            AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date, 
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),

        accident_daily_traffic AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            WHERE toDate(t.illegal_date) = toDate(w.label_date)
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        ),

        random_daily_traffic AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            WHERE toDate(t.illegal_date) = toDate(w.label_date)
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        )

        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv ,cnt FROM accident_daily_bhv
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM random_daily_bhv
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM accident_daily_adas
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM random_daily_adas
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM accident_daily_aebs
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM random_daily_aebs
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM accident_daily_traffic
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv,cnt FROM random_daily_traffic
    """
    return sql

def train_tmp_driver_action_count_1d_sql_new(start_date:str,end_date:str)->str:
    sql=f"""
            WITH 
        all_daily AS (
            SELECT * FROM ai_security.tmp_driver_1d
        ),
        -- 事故组行为（一周）
        accident_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                -- WHERE toDate(b.report_time) = toDate(w.label_date)
                WHERE toDate(b.report_time) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
                  AND w.has_accident_label = 1
                  AND toDate(b.report_time) >= toDate('2025-12-08')
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END
                    
                    UNION ALL
                
        
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
              --   WHERE toDate(b.rcrd_time) = toDate(w.label_date)
                 WHERE toDate(b.rcrd_time) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
                  AND w.has_accident_label = 1
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name,b.drv_sct_bhv,w.label_date 
            ) t
            GROUP BY driver_id, driver_name,label_date, drv_sct_bhv
        ),
        
        random_daily_bhv AS (
            SELECT 
                driver_id,
                driver_name,
                label_date,
                drv_sct_bhv,
                SUM(cnt) AS cnt
            FROM (
                SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
                    ON e.qualification_no = b.operator_code
                -- WHERE toDate(b.report_time) = toDate(w.label_date)
                 WHERE toDate(b.report_time) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
                  AND w.has_accident_label = 0
                GROUP BY w.driver_id, w.driver_name, w.label_date,
                    CASE 
                        WHEN b.report_type = 6 THEN '起步加速评价'
                        WHEN b.report_type = 8 THEN '加速评价'
                        WHEN b.report_type = 7 THEN '减速评价'
                        WHEN b.report_type = 9 THEN '急刹车'
                        WHEN b.report_type = 15 THEN '路口再加速评价'
                        WHEN b.report_type = 14 THEN '路口速度评价'
                        WHEN b.report_type = 18 THEN '违规使用手刹'
                        WHEN b.report_type = 1 THEN '停站N档评价'
                        WHEN b.report_type = 16 THEN 'N档评价'
                        WHEN b.report_type = 22 THEN '不规范转弯'
                        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                        WHEN b.report_type = 12 THEN '门未关起步'
                        WHEN b.report_type = 5 THEN '空档滑行'
                        WHEN b.report_type = 4 THEN '熄火滑行'
                        WHEN b.report_type = 19 THEN '不文明鸣笛'
                        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                        WHEN b.report_type = 21 THEN '拒载'
                        WHEN b.report_type = 20 THEN '飞站'
                        WHEN b.report_type = 10 THEN '急停'
                        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                        WHEN b.report_type = 2 THEN '停车不挂N档'
                        WHEN b.report_type = 17 THEN '开关车门评价'
                        WHEN b.report_type = 23 THEN '动车前安全确认'
                        WHEN b.report_type = 24 THEN '违规使用空调'
                        WHEN b.report_type = 25 THEN '平路不规范'
                        WHEN b.report_type = 26 THEN '上坡不规范'
                        WHEN b.report_type = 27 THEN '下坡不规范'
                        WHEN b.report_type = 28 THEN '违规使用总电'
                        WHEN b.report_type = 29 THEN '路口大油门'
                        WHEN b.report_type = 30 THEN '进站违规制动'
                        WHEN b.report_type = 33 THEN '区间超速'
                        WHEN b.report_type = 34 THEN '全局超速'
                        WHEN b.report_type = 36 THEN '左转弯未刹车'
                        WHEN b.report_type = 37 THEN '右转弯未停车'
                    END
                    
                    UNION ALL
                    
                    SELECT
                    w.driver_id,
                    w.driver_name,
                    w.label_date,
                    b.drv_sct_bhv,   -- 直接使用表中已有的中文名称
                    COUNT(*) AS cnt
                FROM all_daily w
                GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
                GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
                    ON e.employee_name = b.drv_name   -- 按姓名关联
                -- WHERE toDate(b.rcrd_time) = toDate(w.label_date)
                 WHERE toDate(b.rcrd_time) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
                  AND w.has_accident_label = 0
                  AND toDate(b.rcrd_time)  < toDate('2025-12-08' )  
                GROUP BY w.driver_id, w.driver_name, w.label_date,b.drv_sct_bhv
            ) t
            GROUP BY driver_id, driver_name, drv_sct_bhv,label_date
        ),
        
        accident_daily_adas AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
         --   WHERE toDate(e.happentime) = toDate(w.label_date)
           WHERE toDate(e.happentime) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
              AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name, w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),
        
        random_daily_adas AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
           -- WHERE toDate(e.happentime) = toDate(w.label_date)
             WHERE toDate(e.happentime) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
              AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),
        
        accident_daily_aebs AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            -- WHERE toDate(e.warnTime) =toDate(w.label_date)
            WHERE toDate(e.warnTime) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
            AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name,w.label_date, 
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),
        
        random_daily_aebs AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            -- WHERE toDate(e.warnTime) =toDate(w.label_date)
            WHERE toDate(e.warnTime) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
            AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date,
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),
        
        accident_daily_traffic AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            -- WHERE toDate(t.illegal_date) = toDate(w.label_date)
            WHERE toDate(t.illegal_date) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              AND w.has_accident_label = 1
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        ),
        
        random_daily_traffic AS (
            SELECT
                w.driver_id,
                w.driver_name,
                w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM all_daily w
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            -- WHERE toDate(t.illegal_date) = toDate(w.label_date)
            WHERE toDate(t.illegal_date) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)

              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              AND w.has_accident_label = 0
            GROUP BY w.driver_id, w.driver_name,w.label_date,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        )
        
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv , ifNull(cnt, 0) AS cnt  FROM accident_daily_bhv
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM random_daily_bhv
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM accident_daily_adas
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM random_daily_adas
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM accident_daily_aebs
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM random_daily_aebs
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM accident_daily_traffic
        UNION ALL
        SELECT driver_id,driver_name,toDate(label_date) as label_date,ifnull(drv_sct_bhv,'' ) as drv_sct_bhv, ifNull(cnt, 0) AS cnt  FROM random_daily_traffic
    """
    return sql

def train_tmp_driver_health_1d_sql(start_date:str,end_date:str)->str:
    sql=f"""
        WITH all_daily AS (SELECT * FROM ai_security.tmp_driver_1d)
        SELECT
            h.driver_code AS driver_id,
            h.driver_name,
            w.label_date,
            ifnull(argMax(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS heart_rate_avg,
            ifnull(argMax(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS alcohol_avg,
            ifnull(argMax(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS sbp_avg,
            ifnull(argMax(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS dbp_avg,
            ifnull(argMax(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS pulse_avg,
            ifnull(argMax(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS spo2_avg,
            ifnull(argMax(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS temp_avg
        FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
        GLOBAL INNER JOIN all_daily w 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.driver_code, position(h.driver_code, '-') + 1)
        WHERE toDate(h.happen_time) = toDate(w.label_date)
          AND h.vname IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
        GROUP BY h.driver_code, h.driver_name, w.label_date
    """
    return sql

def train_tmp_driver_workhour_1d(start_date:str,end_date:str)->str:
    sql=f"""
        WITH all_daily AS (SELECT * FROM ai_security.tmp_driver_1d)
    SELECT
        h.employee_id AS driver_id,
        h.employee_name AS driver_name,
        w.label_date,
        ifnull(SUM(toFloat64OrNull(ifnull(h.safty_mileage,0))),0) AS daily_mileage,
        ifnull(SUM(toFloat64OrNull(ifnull(h.work_hour,0))),0) AS daily_work_hour
    FROM canbus.ads_driver_workhour h
    GLOBAL INNER JOIN all_daily w 
    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.employee_id, position(h.employee_id, '-') + 1)
    WHERE toDate(parseDateTimeBestEffort(h.ppartition)) = toDate(w.label_date)
    GROUP BY h.employee_id, h.employee_name, w.label_date
    """
    return sql

def train_tmp_driver_health_1d_sql_new(start_date:str,end_date:str)->str:
    sql=f"""
        WITH all_daily AS (SELECT * FROM ai_security.tmp_driver_1d)
        SELECT
            h.driver_code AS driver_id,
            h.driver_name,
            w.label_date,
--             ifnull(argMax(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS heart_rate_avg,
--             ifnull(argMax(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS alcohol_avg,
--             ifnull(argMax(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS sbp_avg,
--             ifnull(argMax(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS dbp_avg,
--             ifnull(argMax(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS pulse_avg,
--             ifnull(argMax(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS spo2_avg,
--             ifnull(argMax(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END, happen_time),0) AS temp_avg
        -- 改为 avg 计算平均值
            ifnull(avg(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END), 0) AS heart_rate_avg,
            ifnull(avg(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END), 0) AS alcohol_avg,
            ifnull(avg(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END), 0) AS sbp_avg,
            ifnull(avg(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END), 0) AS dbp_avg,
            ifnull(avg(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END), 0) AS pulse_avg,
            ifnull(avg(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END), 0) AS spo2_avg,
            ifnull(avg(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END), 0) AS temp_avg
        FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
        GLOBAL INNER JOIN all_daily w 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.driver_code, position(h.driver_code, '-') + 1)
        -- WHERE toDate(h.happen_time) = toDate(w.label_date)
         WHERE toDate(h.happen_time) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
          AND h.vname IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
        GROUP BY h.driver_code, h.driver_name,w.label_date
    """
    return sql

def train_tmp_driver_workhour_1d_new(start_date:str,end_date:str)->str:
    sql=f"""
        WITH all_daily AS (SELECT * FROM ai_security.tmp_driver_1d)
    SELECT
        h.employee_id AS driver_id,
        h.employee_name AS driver_name,
        w.label_date,
        ifnull(SUM(toFloat64OrNull(ifnull(h.safty_mileage,0))),0) AS daily_mileage,
        ifnull(SUM(toFloat64OrNull(ifnull(h.work_hour,0))),0) AS daily_work_hour
    FROM canbus.ads_driver_workhour h
    GLOBAL INNER JOIN all_daily w 
    ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.employee_id, position(h.employee_id, '-') + 1)
--     WHERE toDate(parseDateTimeBestEffort(h.ppartition)) = toDate(w.label_date)
     WHERE toDate(parseDateTimeBestEffort(h.ppartition)) BETWEEN (toDate(w.label_date) - INTERVAL 14 DAY) AND (toDate(w.label_date)- INTERVAL 7 DAY)
    GROUP BY h.employee_id, h.employee_name,w.label_date
    """
    return sql


def train_1d_sql(start_date: str, end_date: str) -> str:
    sql = f"""
    WITH 
    driver_with_routeid AS ( 
            SELECT DISTINCT 
            e.driver_id,
            e.driver_name,
            e.label_date,
            ojbe.organ_id as organ_id,
            f.organ_name as organ_name,
            gg.route_name 
            FROM ai_security.tmp_driver_1d e 
            GLOBAL JOIN canbus.ods_jituan_bs_employee ojbe 
            ON substring(e.driver_id, position(e.driver_id, '-') + 1) = substring(ojbe.employee_id, position(ojbe.employee_id, '-') + 1)
            GLOBAL inner join canbus.ods_jituan_bs_organ f
            on ojbe.organ_id=f.organ_id 
            GLOBAL inner join canbus.ods_jituan_bs_route gg 
            on ojbe.route_id=gg.route_id
            ),

    driver_accident AS (
            SELECT 
            org_code,
            org_name,
            CASE 
            WHEN POSITION('-' IN line_code) > 0 
            THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
            ELSE line_code END AS line_code,
            line_name,
            driver_name,
            yearly,
            accident_num 
            FROM ai_security.ads_driver_accident_yearly
            ), 

    s_result AS (
            SELECT a.*,b.employee_name,b.organ_id,b.organ_name 
            FROM driver_accident a 
            GLOBAL LEFT OUTER JOIN (
            SELECT a.*,b.organ_name 
            FROM canbus.ods_jituan_bs_employee a 
            GLOBAL INNER JOIN canbus.ods_jituan_bs_organ b 
            ON a.organ_id=b.organ_id ) b 
            ON a.driver_name=b.employee_name 
            WHERE b.organ_name LIKE CONCAT('%%',a.org_name,'%%') 
            ),

    accident_yearly AS (
        SELECT 
            d.driver_id,
            d.driver_name,
            COALESCE(SUM(a.accident_num), 0) AS total_accidents
        FROM driver_with_routeid d
        GLOBAL LEFT JOIN s_result a
            ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
            AND a.yearly IN (2023, 2024)
        GROUP BY d.driver_name,d.driver_id,a.organ_id,a.line_code
    ),

    pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        toFloat64(sum(station_count)) AS total_station_count,
        count(*) AS trip_count
        FROM (
            SELECT 
                toDate(t.ppartition) AS drive_date,
                t.employee_id AS employee_id,         
                t.employee_name AS driver_name, 
                t.bus_id,
                t.route_id,
                t.from_station,
                t.to_station,
                abs(s2.min_sort - s1.min_sort) + 1 AS station_count
            FROM canbus.ads_triplog_energy t
            GLOBAL LEFT JOIN (
                -- 站点去重：同线路同站名取最小站序
                SELECT line_code, motorcade_name, min(sort) as min_sort
                FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                GROUP BY line_code, motorcade_name
            ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
            GLOBAL LEFT JOIN (
                SELECT line_code, motorcade_name, min(sort) as min_sort
                FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                GROUP BY line_code, motorcade_name
            ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
            WHERE s1.min_sort IS NOT NULL 
              AND s2.min_sort IS NOT NULL
              AND (t.employee_id, toDate(t.ppartition)) GLOBAL IN (
                   SELECT driver_id, toDate(label_date) FROM ai_security.tmp_driver_1d)
        ) as sub
        GROUP BY 
            drive_date,
            employee_id,
            driver_name
    ),

    pass_turn_list AS(
        SELECT 
            drive_date,
            employee_id ,
            driver_name,
            toFloat64(sum(turn_count)) AS total_turn_count
        FROM (

            SELECT
                toDate(t.ppartition) AS drive_date,
                t.employee_id AS employee_id,         
                t.employee_name AS driver_name, 
                t.route_id,       
                COUNT(b.event_type) AS turn_count
            FROM ai_security.ads_triplog_energy t
            GLOBAL LEFT JOIN canbus.ads_event_black_spot b
            ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
                AND b.event_type IN (2, 3)
            WHERE (t.employee_id, toDate(t.ppartition)) GLOBAL IN (
                   SELECT driver_id, toDate(label_date) FROM ai_security.tmp_driver_1d)
            GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
            drive_date,
            employee_id,
            driver_name
    ),

    mental_list AS (
            SELECT 
            m.driver_name,
            case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
            m.heart_level_label AS heart_level_label, 
            m.follow_year_month,
            n.driver_id,
            m.line_name  
            FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
            GLOBAL inner join driver_with_routeid n on m.driver_name=n.driver_name and m.line_name=n.route_name
            and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
            WHERE m.follow_year_month = formatDateTime(toDate(n.label_date), '%%Y-%%m') 
            ),

    avg_mileage AS (
        SELECT AVG(daily_mileage) AS avg_val
        FROM ai_security.tmp_driver_workhour_1d
        WHERE daily_mileage > 0   -- 排除0和NULL
    ),

    avg_pass_station AS (
        SELECT AVG(total_station_count) AS avg_val
        FROM pass_station_list
        WHERE total_station_count > 0   -- 排除0和NULL
    ),

    avg_pass_turn AS (
        SELECT AVG(total_turn_count) AS avg_val
        FROM pass_turn_list
        WHERE total_turn_count > 0   -- 排除0和NULL
    )

    SELECT
        w.driver_id,
        w.driver_name,
        --w.label_date,
        e.sex AS gender,
        e.age,
        e.education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        wd.daily_mileage,
        wd.daily_work_hour,
        y.total_accidents,
        -- 行为特征（当天次数）
        -- 原37列基础行为
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0),am.avg_val) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,

        -- 9列ADAS行为
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,

        -- 3列失能行为
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,

        -- 3列交通违法
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        -- 健康
        h.heart_rate_avg,
        h.alcohol_avg,
        h.sbp_avg,
        h.dbp_avg,
        h.pulse_avg,
        h.spo2_avg,
        h.temp_avg,
        -- 心理指标
        m2.heart_level_label,
        -- 标签
        w.has_accident_label
    FROM ai_security.tmp_driver_1d w
    GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e ON w.driver_id = e.employee_id
    GLOBAL LEFT JOIN ai_security.tmp_driver_workhour_1d wd 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(wd.driver_id, position(wd.driver_id, '-') + 1) AND w.label_date = wd.label_date
    GLOBAL LEFT JOIN ai_security.tmp_driver_action_count_1d b 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1) AND w.label_date = b.label_date  
    GLOBAL LEFT JOIN ai_security.tmp_driver_health_1d h 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.driver_id, position(h.driver_id, '-') + 1) AND w.label_date = h.label_date
    GLOBAL LEFT JOIN mental_list m2
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(m2.driver_id, position(m2.driver_id, '-') + 1)
    GLOBAL LEFT JOIN accident_yearly y
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(y.driver_id, position(y.driver_id, '-') + 1)
    GLOBAL LEFT JOIN pass_station_list p 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(p.employee_id, position(p.employee_id, '-') + 1)
    GLOBAL LEFT JOIN pass_turn_list p2
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(p2.employee_id, position(p2.employee_id, '-') + 1)
    GLOBAL CROSS JOIN avg_mileage am
    GLOBAL CROSS JOIN avg_pass_station aps
    GLOBAL CROSS JOIN avg_pass_turn apt
    GROUP BY 
        w.driver_id,
        w.driver_name,
        --w.label_date,
        w.has_accident_label,
        e.sex, e.age, e.education_level, e.entry_time,
        wd.daily_mileage, wd.daily_work_hour,
        h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg,
        h.pulse_avg, h.spo2_avg, h.temp_avg,
        y.total_accidents,
        m2.heart_level_label,
        am.avg_val,
        p2.total_turn_count,
        p.total_station_count,
        apt.avg_val,
        aps.avg_val
    ORDER BY w.driver_name
    """
    return sql


def train_1d_sql_new(start_date: str, end_date: str) -> str:
    sql = f"""
    WITH 
    driver_with_routeid AS ( 
            SELECT DISTINCT 
            e.driver_id,
            e.driver_name,
            e.label_date,
            ojbe.organ_id as organ_id,
            f.organ_name as organ_name,
            gg.route_name 
            FROM ai_security.tmp_driver_1d e 
            GLOBAL JOIN canbus.ods_jituan_bs_employee ojbe 
            ON substring(e.driver_id, position(e.driver_id, '-') + 1) = substring(ojbe.employee_id, position(ojbe.employee_id, '-') + 1)
            GLOBAL inner join canbus.ods_jituan_bs_organ f
            on ojbe.organ_id=f.organ_id 
            GLOBAL inner join canbus.ods_jituan_bs_route gg 
            on ojbe.route_id=gg.route_id
            ),

    driver_accident AS (
            SELECT 
            org_code,
            org_name,
            CASE 
            WHEN POSITION('-' IN line_code) > 0 
            THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
            ELSE line_code END AS line_code,
            line_name,
            driver_name,
            yearly,
            accident_num 
            FROM ai_security.ads_driver_accident_yearly
            ), 

    s_result AS (
            SELECT a.*,b.employee_name,b.organ_id,b.organ_name 
            FROM driver_accident a 
            GLOBAL LEFT OUTER JOIN (
            SELECT a.*,b.organ_name 
            FROM canbus.ods_jituan_bs_employee a 
            GLOBAL INNER JOIN canbus.ods_jituan_bs_organ b 
            ON a.organ_id=b.organ_id ) b 
            ON a.driver_name=b.employee_name 
            WHERE b.organ_name LIKE CONCAT('%%',a.org_name,'%%') 
            ),

    accident_yearly AS (
        SELECT 
            d.driver_id,
            d.driver_name,
            COALESCE(SUM(a.accident_num), 0) AS total_accidents
        FROM driver_with_routeid d
        GLOBAL LEFT JOIN s_result a
            ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
            AND a.yearly IN (2023, 2024)
        GROUP BY d.driver_name,d.driver_id,a.organ_id,a.line_code
    ),

    pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        toFloat64(sum(station_count)) AS total_station_count,
        count(*) AS trip_count
        FROM (
            SELECT 
                toDate(tt.label_date) AS drive_date,
                t.employee_id AS employee_id,         
                t.employee_name AS driver_name, 
                t.bus_id,
                t.route_id,
                t.from_station,
                t.to_station,
                abs(s2.min_sort - s1.min_sort) + 1 AS station_count
            FROM canbus.ads_triplog_energy t
            GLOBAL LEFT JOIN (
                -- 站点去重：同线路同站名取最小站序
                SELECT line_code, motorcade_name, min(sort) as min_sort
                FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                GROUP BY line_code, motorcade_name
            ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
            GLOBAL LEFT JOIN (
                SELECT line_code, motorcade_name, min(sort) as min_sort
                FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                GROUP BY line_code, motorcade_name
            ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
            GLOBAL inner join ai_security.tmp_driver_1d tt 
            on t.employee_id=tt.driver_id 
            WHERE s1.min_sort IS NOT NULL 
            AND s2.min_sort IS NOT NULL
            and toDate(t.ppartition) BETWEEN (toDate(tt.label_date) - INTERVAL 14 DAY) AND (toDate(tt.label_date)- INTERVAL 7 DAY)
             -- AND (t.employee_id, toDate(t.ppartition)) GLOBAL IN (
                --   SELECT driver_id, toDate(label_date) FROM ai_security.tmp_driver_1d)
        ) as sub
        GROUP BY 
            drive_date,
            employee_id,
            driver_name
    ),
    black_spot as (
    	SELECT routeid,COUNT(event_type) as turn_count FROM (
            select  splitByChar('#', route_ids)[1] as routeid,event_type from canbus.ads_event_black_spot where event_type IN ('2', '3') ) AA 
            GROUP BY routeid ), 
    pass_turn_list AS(
        SELECT 
            drive_date,
            employee_id ,
            driver_name,
            toFloat64(sum(turn_count)/7) AS total_turn_count
        FROM (

            SELECT
                toDate(tt.label_date) AS drive_date,
                t.employee_id AS employee_id,         
                t.employee_name AS driver_name, 
                t.route_id,       
                b.turn_count AS turn_count
            FROM ai_security.ads_triplog_energy t
            GLOBAL LEFT JOIN black_spot b
            ON toString(t.route_id) = toString(b.routeid) 
            GLOBAL inner join ai_security.tmp_driver_1d tt 
            on t.employee_id=tt.driver_id 
            where toDate(t.ppartition) BETWEEN (toDate(tt.label_date) - INTERVAL 14 DAY) AND (toDate(tt.label_date)- INTERVAL 7 DAY)
         --   WHERE (t.employee_id, toDate(t.ppartition)) GLOBAL IN (
          --         SELECT driver_id, toDate(label_date) FROM ai_security.tmp_driver_1d)
           -- GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
            drive_date,
            employee_id,
            driver_name
    ),

    mental_list AS (
            SELECT 
            m.driver_name,
            case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
            m.heart_level_label AS heart_level_label, 
            m.follow_year_month,
            n.driver_id,
            m.line_name  
            FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
            GLOBAL inner join driver_with_routeid n on m.driver_name=n.driver_name and m.line_name=n.route_name
            and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
            WHERE m.follow_year_month = formatDateTime(toDate(n.label_date), '%%Y-%%m') 
            ),

    avg_mileage AS (
        SELECT AVG(daily_mileage) AS avg_val
        FROM ai_security.tmp_driver_workhour_1d
        WHERE daily_mileage > 0   -- 排除0和NULL
    ),

    avg_pass_station AS (
        SELECT AVG(total_station_count) AS avg_val
        FROM pass_station_list
        WHERE total_station_count > 0   -- 排除0和NULL
    ),

    avg_pass_turn AS (
        SELECT AVG(total_turn_count) AS avg_val
        FROM pass_turn_list
        WHERE total_turn_count > 0   -- 排除0和NULL
    )

    SELECT
        w.driver_id as driver_id,
        w.driver_name as driver_name,
        --w.label_date,
        e.sex AS gender,
        e.age as age,
        e.education_level as education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        wd.daily_mileage AS daily_mileage,
        wd.daily_work_hour as daily_work_hour,
        y.total_accidents as total_accidents,
        -- 行为特征（当天次数）
        -- 原37列基础行为
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0),am.avg_val) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,

        -- 9列ADAS行为
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(wd.daily_mileage, 0), am.avg_val) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,

        -- 3列失能行为
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,

        -- 3列交通违法
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        -- 健康
        h.heart_rate_avg as heart_rate_avg,
        h.alcohol_avg as alcohol_avg,
        h.sbp_avg as sbp_avg,
        h.dbp_avg as dbp_avg,
        h.pulse_avg as pulse_avg,
        h.spo2_avg as spo2_avg,
        h.temp_avg as temp_avg,
        -- 心理指标
        m2.heart_level_label as heart_level_label,
        -- 标签
        w.has_accident_label as has_accident_label 
    FROM ai_security.tmp_driver_1d w
    GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e ON w.driver_id = e.employee_id
    GLOBAL LEFT JOIN ai_security.tmp_driver_workhour_1d wd 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(wd.driver_id, position(wd.driver_id, '-') + 1) AND w.label_date = wd.label_date
    GLOBAL LEFT JOIN ai_security.tmp_driver_action_count_1d b 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1) AND w.label_date = b.label_date  
    GLOBAL LEFT JOIN ai_security.tmp_driver_health_1d h 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(h.driver_id, position(h.driver_id, '-') + 1) AND w.label_date = h.label_date
    GLOBAL LEFT JOIN mental_list m2
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(m2.driver_id, position(m2.driver_id, '-') + 1)
    GLOBAL LEFT JOIN accident_yearly y
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(y.driver_id, position(y.driver_id, '-') + 1)
    GLOBAL LEFT JOIN pass_station_list p 
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(p.employee_id, position(p.employee_id, '-') + 1)
    GLOBAL LEFT JOIN pass_turn_list p2
        ON substring(w.driver_id, position(w.driver_id, '-') + 1) = substring(p2.employee_id, position(p2.employee_id, '-') + 1)
    GLOBAL CROSS JOIN avg_mileage am
    GLOBAL CROSS JOIN avg_pass_station aps
    GLOBAL CROSS JOIN avg_pass_turn apt
    GROUP BY 
        w.driver_id,
        w.driver_name,
        --w.label_date,
        w.has_accident_label,
        e.sex, e.age, e.education_level, e.entry_time,
        wd.daily_mileage, wd.daily_work_hour,
        h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg,
        h.pulse_avg, h.spo2_avg, h.temp_avg,
        y.total_accidents,
        m2.heart_level_label,
        am.avg_val,
        p2.total_turn_count,
        p.total_station_count,
        apt.avg_val,
        aps.avg_val
    ORDER BY w.driver_name
    """
    return sql

def get_driver_two_week_profile(start_date_str:str):
    last_week_date=datetime.strptime(start_date_str,"%Y-%m-%d")-timedelta(days=7)
    last_week_date_str=last_week_date.strftime("%Y%m%d")
    curren_date_str=datetime.strptime(start_date_str, "%Y-%m-%d").strftime("%Y%m%d")
    sql=f"""
    --驾驶员分数表包含驾驶员id、姓名、时间、总分数,事故分数、线路排名、线路总人数
     WITH d_score AS (
        SELECT 
            a.driver_id as driver_id,
            a.driver_name as  driver_name,
            b.original_value  as score,
            a.score  as total_score,
            a.evalutaion_type as evalutaion_type,  
            a.organ_id as organ_id,
            a.organ_name as organ_name,a.ppartition as ppartition  
        FROM (select driver_id,driver_name,evalutaion_type,score,organ_id,organ_name,ppartition,id from ai_security.abs_driver_profile_main_new where ppartition >= '{last_week_date_str}' and ppartition<='{curren_date_str}') a 
        inner join (select main_id,original_value,quota_level from ai_security.abs_driver_quota_score_sub_new 
        where ppartition >= '{last_week_date_str}'  and ppartition<='{curren_date_str}' and quota_level='1' and quota_id like '%驾驶员画像-事故风险%' ) b on 
        a.id=b.main_id  
    ),
    b_route AS (
        SELECT 
            employee_id,
            route_id,
            organ_id  
        FROM canbus.ods_jituan_bs_employee 
    ),
    b_total as (select count(*) as num ,route_id FROM canbus.ods_jituan_bs_employee group by route_id),
    score_route AS (
        SELECT 
            a.driver_id,
            a.driver_name,
            a.evalutaion_type,
            a.total_score,
            a.score,
            b.route_id as route_id,
            a.organ_id AS organ_id,
            organ_name,
            c.num as route_total,
            ppartition
        FROM d_score a 
        INNER JOIN b_route b ON a.driver_id = b.employee_id 
        inner join b_total c on b.route_id=c.route_id 
    ),
    sort_rank AS (
        SELECT 
            driver_id,
            driver_name,
            total_score,
            score,
            evalutaion_type,
            route_id,
            organ_id,  
            organ_name,
            ppartition,
            ROW_NUMBER() OVER (PARTITION BY ppartition,route_id ORDER BY score DESC) AS group_sort_rank,
            route_total
        FROM score_route 
    )
    SELECT * 
    FROM sort_rank  order by ppartition,route_id,evalutaion_type,group_sort_rank   ;
    """
    return sql


import time
import uuid
from datetime import datetime, timedelta

import pandas as pd
# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client
from dateutil.parser import parser
from pandas import DataFrame

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger
from model.driver.schemas.driver_profile import AbsDriverProfileMain, AbsDriverQuotaScoreSub
from utils.compute import Compute
from utils.tools import get_next_month_day, get_last_month_day


#数据库操作
class Driver(ClickHouseManage):

    def __init__(self, db: Client):
        super(Driver, self).__init__(db, "", "","")

    async def gen_tmp_table(
            self,
            table_name:str = None,sql:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, table_name)
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert(table_name, datas, batch_size=m_size)
        return datas

    async def get_risk_value(self,score)-> str | None:
        manager = ClickHouseManage(self.db, "")
        sql=sql_config.get_risk_value()
        datas = await manager.get_data_sql_dict(sql)
        for data in datas:
            parts=data['item_value'].strip().split('-')
            result = [int(part) for part in parts]
            min_val, max_val = result
            is_in_range = min_val <= round(score) <= max_val
            if is_in_range:
                return data['item_text']
        return ""

    async def get_risk_value_hour(self,score)-> str | None:
        # manager = ClickHouseManage(self.db, "")
        # sql=sql_config.get_risk_value()
        # datas = await manager.get_data_sql_dict(sql)
        datas=[]
        risk_data={}
        risk_data['item_text']="关注型"
        risk_data['item_value']="80-89"
        datas.append(risk_data)
        risk_data = {}
        risk_data['item_text'] = "危险型"
        risk_data['item_value'] = "90-1000"
        datas.append(risk_data)
        risk_data = {}
        risk_data['item_text'] = "观察型"
        risk_data['item_value'] = "70-79"
        datas.append(risk_data)
        risk_data = {}
        risk_data['item_text'] = "安全型"
        risk_data['item_value'] = "0-69"
        datas.append(risk_data)

        for data in datas:
            parts=data['item_value'].strip().split('-')
            result = [int(part) for part in parts]
            min_val, max_val = result
            is_in_range = min_val <= round(score) <= max_val
            if is_in_range:
                return data['item_text']
        return ""

    async def get_energy_datas(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        print("开始读取全量驾驶行为统计数据...")
        start_time = time.time()
        sql = "select * from ai_security.v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week"
        datas = await manager.get_data_sql_dict(sql)
        end_time = time.time()
        print(f"耗时: {end_time - start_time:.2f} 秒")
        return datas
        # print("开始读取全量驾驶行为统计数据...")
        # start_time = time.time()
        # columns= [
        # 'ppartition', 'employee_number', 'employee_id', 'employee_name', 'obuid',
        # 'bus_code', 'number_plate', 'bus_length', 'total_weight', 'bus_age',
        # 'report_time', 'report_type1_count', 'report_type2_count', 'report_type3_count',
        # 'report_type4_count', 'report_type5_count', 'report_type6_count',
        # 'report_type7_count', 'report_type8_count', 'report_type9_count',
        # 'report_type10_count', 'report_type11_count', 'report_type12_count',
        # 'report_type13_count', 'report_type14_count', 'report_type15_count',
        # 'report_type16_count', 'report_type17_count', 'report_type18_count',
        # 'report_type19_count', 'report_type20_count', 'report_type21_count',
        # 'report_type22_count', 'report_type23_count', 'report_type24_count',
        # 'report_type25_count', 'report_type26_count', 'report_type27_count',
        # 'report_type28_count', 'report_type29_count', 'report_type30_count',
        # 'report_type31_count', 'report_type32_count', 'report_type33_count',
        # 'report_type34_count', 'report_type36_count', 'report_type37_count',
        # 'bus_type', 'total_energy_consumption', 'run_energy_consumption',
        # 'run_mileage', 'record_date', 'recharge_energy', 'route_name',
        # 'organ_id', 'organ_name', 'work_hour', 'safty_mileage', 'trip_mileage',
        # 'total_mileage', 'route_id']
        # df=await manager.fetch_data_streaming(sql,columns)
        # end_time = time.time()
        #
        # if not df.empty:
        #     print(f"数据读取成功!")
        #     print(f"总行数: {len(df)}")
        #     print(f"耗时: {end_time - start_time:.2f} 秒")
        #     print(f"列数: {len(df.columns)}")
        #     print("\n数据预览:")
        #     print(df.head())
        # else:
        #     print("数据读取失败!")
        # return df

    async def get_energy_sum_datas(
            self,
            start_date_str: str = None,
            end_date_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.driver_behavior_energy_report_sum(start_date_str,end_date_str).replace("\n","")
        # sql = "select * from ai_security.v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week_sum"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_energy_quota_name3_datas(
            self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere=""
        if _start_time is not None:
            strwhere=f" and '{_start_time}' between start_time and end_time "
        sql = f""" select * from ai_security.obs_quota_weight_configuration where profile_type='驾驶员画像' and quota_name1='能耗风险' and quota_name2='不良行为' and deleted!='1'
               and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id2='驾驶员画像-能耗风险-不良行为' and deleted!='1' {strwhere} ) """
        datas = await manager.get_data_sql_dict(sql)
        return datas


    async def get_energy_quota_name3_datas_calu(
            self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere=""
        if _start_time is not None:
            strwhere=f" and '{_start_time}' between start_time and end_time "
        sql=f""" select distinct '1' as quota_level, profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name, 
        case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration 
        where profile_type = '驾驶员画像' and quota_id1 = '{_id}' and 
        start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '{_id}' and deleted != '1' {strwhere})
        union all
        select distinct '2' as quota_level, quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name, 
        case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration 
        where profile_type = '驾驶员画像' and quota_id1 = '{_id}' and 
        start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '{_id}' and deleted != '1' {strwhere})
        union all
        select distinct '3' as quota_level, quota_id2 as parent_id, quota_id3 as quota_id, quota_name3 as quota_name, 
        case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration 
        where profile_type = '驾驶员画像' and quota_id1 = '{_id}' and 
        start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '{_id}' and deleted != '1' {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    #
    # async def get_accident_weights_datas_calu(
    #         self,
    #         _id: str = None,_start_time:str=None,
    # ) -> dict | None:
    #     manager = ClickHouseManage(self.db, "")
    #     strwhere = ""
    #     if _start_time is not None:
    #         strwhere = f" and '{_start_time}' between start_time and end_time "
    #     sql=f""" select * from ai_security.obs_quota_weight_configuration
    #         where profile_type = '驾驶员画像' and quota_id1 = '驾驶员画像-事故风险' and
    #         start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '驾驶员画像-事故风险' and deleted != '1' {strwhere})
    #         """
    #     sql=sql.replace("\n","")
    #     datas = await manager.get_data_sql_dict(sql)
    #     return datas

    async def get_attitude_weights(
            self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql=f""" select * from ai_security.obs_quota_weight_configuration 
            where profile_type = '驾驶员画像' and quota_id1 = '驾驶员画像-服务态度' and 
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '驾驶员画像-服务态度' and deleted != '1' {strwhere})
            """
        sql=sql.replace("\n","")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_safety_weights(
            self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql=f""" select * from ai_security.obs_quota_weight_configuration 
            where profile_type = '驾驶员画像' and quota_id1 = '驾驶员画像-安全评价' and 
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 = '驾驶员画像-安全评价' and deleted != '1' {strwhere})
            """
        sql=sql.replace("\n","")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    # async def get_driver_quota_name3_datas_calu(
    #         self,
    #         _id: str = None,_start_time:str=None,
    # ) -> dict | None:
    #     manager = ClickHouseManage(self.db, "")
    #     strwhere = ""
    #     if _start_time is not None:
    #         strwhere = f" and '{_start_time}' between start_time and end_time "
    #     sql=f""" select distinct '1' as quota_level, profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
    #     case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '驾驶员画像' and quota_id1 <> '驾驶员画像-能耗风险' and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 <> '驾驶员画像-能耗风险' and deleted != '1' {strwhere})
    #     union all
    #     select distinct '2' as quota_level, quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
    #     case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '驾驶员画像' and quota_id1 <> '驾驶员画像-能耗风险' and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 <> '驾驶员画像-能耗风险' and deleted != '1' {strwhere})
    #     union all
    #     select distinct '3' as quota_level, quota_id2 as parent_id, quota_id3 as quota_id, quota_name3 as quota_name,
    #     case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '驾驶员画像' and quota_id1 <> '驾驶员画像-能耗风险' and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id1 <> '驾驶员画像-能耗风险' and deleted != '1' {strwhere}) """
    #     datas = await manager.get_data_sql_dict(sql)
    #     return datas

    async def insert_driver_behavior_month(
            self,start_time:str = None,end_time:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        start_date = datetime.strptime(start_time, '%Y-%m-%d')
        start_date_str = start_date.strftime('%Y%m%d')
        await manager.delete_data_by_ppartition("ods_communication_driver_behavior_month",start_date_str )
        sql = sql_config.insert_driver_behavior_month(start_time,end_time).replace("\n","")
        # sql="insert into abs_driver_behavior_sum select * from v_driver_behavior_week_sum"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_behavior_week_datas(
            self,start_time:str = None,end_time:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.driver_behavior_week_query(start_time,end_time).replace("\n","")
        # sql="insert into abs_driver_behavior_sum select * from v_driver_behavior_week_sum"
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            await manager.delete_data_by_ppartition("abs_driver_behavior_sum",datas[0]['start_time'])
            result= await manager.batch_insert("abs_driver_behavior_sum", datas,m_size)
        return datas

    async def get_driver_behavior_data_month_init(
            self,start_time:str = None,end_time:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.driver_behavior_month_init_query(start_time,end_time).replace("\n","")
        # sql="insert into abs_driver_behavior_sum select * from v_driver_behavior_week_sum"
        # datas = await manager.get_data_sql_dict(sql)
        print(f"开始读取驾驶行为{start_time}数据初始化...")
        start_time = time.time()
        columns =['ppartition', 'report_type', 'report_sub_type', 'report_time',
        'obuid', 'operator_code', 'latitude', 'longitude', 'speed', 'direction', 'station_code', 'create_time', 'id']
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()

        if not df.empty:
            print(f"数据读取成功!")
            print(f"总行数: {len(df)}")
            print(f"耗时: {end_time - start_time:.2f} 秒")
            print(f"列数: {len(df.columns)}")
            print("\n数据预览:")
            print(df.head())
        else:
            print("数据读取失败!")

        datas=df.to_dict('records')
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            result= await manager.batch_insert("ods_communication_driver_behavior_month", datas,m_size)
        return datas


    async def get_drivers_datas(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # sql = "select * from ai_security.v_drivers_data"
        sql =sql_config.v_drivers_weights_data()
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_drivers_1hour_datas(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # sql = "select * from ai_security.v_drivers_data"
        sql =sql_config.v_drivers_weights_1hour_data()
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_drivers_day_datas(
            self,
            start_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql= sql_config.abs_driver_day_datas(start_time_str)
        # p_datas = await manager.get_data_sql_dict(sql)
        # sql = "select * from ai_security.v_driver_day_datas"
        print(f"开始读取驾驶画像{start_time_str}宽表数据...")
        start_time = time.time()
        columns = ['driver_name','driver_id','organ_id','organ_name',
                   'gender','age','education_level','driving_years',
                   'safty_mileage',
                   'work_hour',
                   'total_accidents',
                   'ndang_cnt',
                   'upslope_bad_cnt',
                   'downslope_bad_cnt',
                   'rude_horn_cnt',
                   'bad_turn_cnt',
                   'stop_ndang_cnt',
                   'no_n_on_stop_cnt',
                   'global_over_spd_cnt',
                   'decel_eval_cnt',
                   'accel_eval_cnt',
                   'before_move_safe_cnt',
                   'section_over_spd_cnt',
                   'right_turn_no_stop_cnt',
                   'left_turn_no_brake_cnt',
                   'flat_bad_cnt',
                   'door_op_eval_cnt',
                   'sudden_stop_cnt',
                   'sudden_brake_cnt',
                   'refuse_ride_cnt',
                   'stall_coast_cnt',
                   'neutral_coast_cnt',
                   'start_accel_eval_cnt',
                   'junction_reaccel_eval_cnt',
                   'junction_heavy_gas_cnt',
                   'junction_spd_eval_cnt',
                   'door_open_before_stop_cnt',
                   'illegal_brake_on_entry_cnt',
                   'illegal_main_power_cnt',
                   'illegal_hand_brake_cnt',
                   'illegal_ac_cnt',
                   'illegal_door_switch_cnt',
                   'start_with_open_door_cnt',
                   'skip_station_cnt',
                   'no_seat_belt_cnt',
                   'distance_warning_cnt',
                   'lane_keep_warning_cnt',
                   'fatigue_warning_cnt',
                   'distraction_cnt',
                   'pedestrian_warning_cnt',
                   'collision_warning_cnt',
                   'phone_call_cnt',
                   'hands_off_wheel_cnt',
                   'very_fatigue_warning_cnt',
                   'hold_steeringwheel_warning_cnt',
                   'driving_posture_warning_cnt',
                   'red_light_cnt',
                   'yellow_light_cnt',
                   'traffic_sign_violation_cnt',
                   'heart_rate',
                   'alcohol',
                   'sbp',
                   'dbp',
                   'pulse',
                   'spo2',
                   'temp',
                   'heart_level_label',
                   'route_id'
                   ]
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()

        if not df.empty:
            print(f"数据读取成功!")
            print(f"总行数: {len(df)}")
            print(f"耗时: {end_time - start_time:.2f} 秒")
            print(f"列数: {len(df.columns)}")
            print("\n数据预览:")
            print(df.head())
        else:
            print("数据读取失败!")

        # p_datas = await manager.get_data_sql_dict(sql)
        return df

    async def get_drivers_hour_datas(
            self,
            start_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql= sql_config.abs_driver_hour_datas(start_time_str)
        # sql = "select * from ai_security.v_driver_day_datas"
        print(f"开始读取驾驶画像{start_time_str}宽表数据...")
        start_time = time.time()
        columns = ['driver_name', 'driver_id', 'organ_id', 'organ_name',
                   'gender', 'age', 'education_level', 'driving_years',
                   'safty_mileage',
                   'work_hour',
                   'total_accidents',
                   'ndang_cnt',
                   'upslope_bad_cnt',
                   'downslope_bad_cnt',
                   'rude_horn_cnt',
                   'bad_turn_cnt',
                   'stop_ndang_cnt',
                   'no_n_on_stop_cnt',
                   'global_over_spd_cnt',
                   'decel_eval_cnt',
                   'accel_eval_cnt',
                   'before_move_safe_cnt',
                   'section_over_spd_cnt',
                   'right_turn_no_stop_cnt',
                   'left_turn_no_brake_cnt',
                   'flat_bad_cnt',
                   'door_op_eval_cnt',
                   'sudden_stop_cnt',
                   'sudden_brake_cnt',
                   'refuse_ride_cnt',
                   'stall_coast_cnt',
                   'neutral_coast_cnt',
                   'start_accel_eval_cnt',
                   'junction_reaccel_eval_cnt',
                   'junction_heavy_gas_cnt',
                   'junction_spd_eval_cnt',
                   'door_open_before_stop_cnt',
                   'illegal_brake_on_entry_cnt',
                   'illegal_main_power_cnt',
                   'illegal_hand_brake_cnt',
                   'illegal_ac_cnt',
                   'illegal_door_switch_cnt',
                   'start_with_open_door_cnt',
                   'skip_station_cnt',
                   'no_seat_belt_cnt',
                   'distance_warning_cnt',
                   'lane_keep_warning_cnt',
                   'fatigue_warning_cnt',
                   'distraction_cnt',
                   'pedestrian_warning_cnt',
                   'collision_warning_cnt',
                   'phone_call_cnt',
                   'hands_off_wheel_cnt',
                   'very_fatigue_warning_cnt',
                   'hold_steeringwheel_warning_cnt',
                   'driving_posture_warning_cnt',
                   'red_light_cnt',
                   'yellow_light_cnt',
                   'traffic_sign_violation_cnt',
                   'heart_rate',
                   'alcohol',
                   'sbp',
                   'dbp',
                   'pulse',
                   'spo2',
                   'temp',
                   'heart_level_label'
                   ]
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()

        if not df.empty:
            print(f"数据读取成功!")
            print(f"总行数: {len(df)}")
            print(f"耗时: {end_time - start_time:.2f} 秒")
            print(f"列数: {len(df.columns)}")
            print("\n数据预览:")
            print(df.head())
        else:
            print("数据读取失败!")

        # datas = await manager.get_data_sql_dict(sql)
        return df

    async def gen_abs_all_30m_bhv_with_traffic(
            self,
            start_time_str: str = None,end_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "abs_all_30m_bhv_with_traffic")
        sql = sql_config.abs_all_30m_bhv_with_traffic(start_time_str,end_time_str).replace("\n", "")
        result=await manager.delete_all_data()
        # datas = await manager.get_data_sql_dict(sql)
        columns=["ppartition","driver_name","drv_sct_bhv","cnt"]
        df =await manager.optimize_and_fetch(sql, columns)
        datas =df.to_dict('records')
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert("abs_all_30m_bhv_with_traffic", datas, batch_size=m_size)
        return datas

    async def gen_abs_all_1HOUR_bhv_with_traffic(
            self,
            start_time_str: str = None,end_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "abs_all_1HOUR_bhv_with_traffic")
        sql = sql_config.abs_all_1HOUR_bhv_with_traffic(start_time_str,end_time_str).replace("\n", "")
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert("abs_all_1HOUR_bhv_with_traffic", datas, batch_size=m_size)
        return datas

    async def gen_abs_rand_window(
            self,
            start_time_str: str = None,end_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "abs_rand_window")
        sql = sql_config.abs_rand_window(start_time_str,end_time_str).replace("\n", "")
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert("abs_rand_window", datas, batch_size=m_size)
        return datas

    async def gen_abs_health_wide(
            self,
            start_time_str: str = None,end_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "abs_health_wide")
        sql = sql_config.abs_health_wide(start_time_str,end_time_str).replace("\n", "")
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert("abs_health_wide", datas, batch_size=m_size)
        return datas

    async def gen_abs_workhour_wide(
            self,
            start_time_str: str = None,end_time_str: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "abs_workhour_wide")
        sql = sql_config.abs_workhour_wide(start_time_str,end_time_str).replace("\n", "")
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        m_size = len(datas)
        if m_size > 100000:
            m_size = 100000
        if m_size > 0:
            success = await manager.batch_insert("abs_workhour_wide", datas, batch_size=m_size)
        return datas

    async def save(self,main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_driver_profile_main",
                "list": main_datas
            },
            {
                "table": "abs_driver_quota_score_sub",
                "list": score_datas,
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                # if len(datas)>0:
                #     await manager.delete_data_by_ppartition(table,datas[0].get("ppartition"))
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000
                if m_size >0:
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def save_new(self,main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_driver_profile_main_new",
                "list": main_datas
            },
            {
                "table": "abs_driver_quota_score_sub_new",
                "list": score_datas,
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                if len(datas)>0:
                    await manager.delete_data_by_ppartition(table,datas[0].get("ppartition"))
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000
                if m_size >0:
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像保存 异常: {e}")
            await manager.rollback_transaction()
            return False



    async def save_hour(self,main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_driver_profile_hour_main",
                "list": main_datas
            },
            {
                "table": "abs_driver_quota_score_hour_sub",
                "list": score_datas,
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000
                if m_size >0:
                    await manager.delete_data_by_ppartition(table, datas[0].get("ppartition"))
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def save_weights(self, energy_weights_datas):
        insert_operations = [
            {
                "table": "obs_quota_weight_configuration",
                "list": energy_weights_datas
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def save_weights_new(self, energy_weights_datas):
        insert_operations = [
            {
                "table": "obs_quota_weight_configuration_new",
                "list": energy_weights_datas
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000

                sql = f"ALTER TABLE {table} DELETE WHERE profile_type = '驾驶员画像' AND start_time = '{datas[0]['start_time']}'"
                result = await manager.execute_query(sql)
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def save_warning(self,table_name, warning_datas,start_time:str=None):
        insert_operations = [
            {
                "table": table_name,
                "list": warning_datas
            }
        ]
        manager = ClickHouseManage(self.db, "")

        try:
            # 开启事务
            await manager.begin_transaction()

            # 执行所有插入操作
            all_success = True
            for operation in insert_operations:
                table = operation["table"]
                datas = operation["list"]
                if len(datas)>0:
                    if start_time is None:
                        await manager.delete_data_by_ppartition(table,datas[0].get("ppartition"))
                    else:
                        await manager.delete_data_by_ppartition(table, start_time)
                m_size = len(datas)
                if m_size > 100000:
                    m_size = 100000
                if m_size >0:
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("驾驶员画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像保存 异常: {e}")
            await manager.rollback_transaction()
            return False
    async def get_driver_accident_quota_datas(
            self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select * from ai_security.obs_quota_weight_configuration where quota_id1='{_id}' 
                and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
               where quota_id1='{_id}' and deleted!='1' {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    # async def get_driver_quota_name3_datas(
    #         self,
    #         _id: str = None,_start_time: str=None,
    # ) -> dict | None:
    #     manager = ClickHouseManage(self.db, "")
    #     strwhere = ""
    #     if _start_time is not None:
    #         strwhere = f" and '{_start_time}' between start_time and end_time "
    #     sql = f""" select * from ai_security.obs_quota_weight_configuration where quota_id2='{_id}' and deleted!='1'
    #     and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where quota_id2='{_id}' and deleted!='1' {strwhere}) """
    #     datas = await manager.get_data_sql_dict(sql)
    #     return datas

    async def get_abs_driver_profile_main( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,driver_id,organ_id,organ_name from ai_security.abs_driver_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_driver_profile_main_new( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,driver_id,organ_id,organ_name from ai_security.abs_driver_profile_main_new where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_driver_profile_hour_main(self,
                                          _id: str = None,
                                          ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # ppartition='{_id}' and
        sql = f"select id,driver_id,organ_id,organ_name from ai_security.abs_driver_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota1( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere=""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
            case when weight_rate1=0 then ROUND(CAST(calculate_weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate 
            from ai_security.obs_quota_weight_configuration where profile_type = '驾驶员画像' {sqlwhere} 
            and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration 
                where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota1_new( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere=""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
            case when weight_rate1=0 then ROUND(CAST(calculate_weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate 
            from ai_security.obs_quota_weight_configuration_new where profile_type = '驾驶员画像' {sqlwhere} 
            and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration_new 
                where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota2( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name, 
               case when weight_rate2=0 then ROUND(CAST(calculate_weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate 
               from ai_security.obs_quota_weight_configuration where profile_type = '驾驶员画像'  {sqlwhere} 
                and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration 
                where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere} )"""
        if _id is not None and _id!='':
            sql = sql + f" and quota_id1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota2_new( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name, 
               case when weight_rate2=0 then ROUND(CAST(calculate_weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate 
               from ai_security.obs_quota_weight_configuration_new where profile_type = '驾驶员画像'  {sqlwhere} 
                and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration_new 
                where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere} )"""
        if _id is not None and _id!='':
            sql = sql + f" and quota_id1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota3( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"

        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '3' as quota_level,quota_id2 as parent_id, quota_id3 as quota_id, quota_name3 as quota_name,
             case when weight_rate3=0 then ROUND(CAST(calculate_weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate from ai_security.obs_quota_weight_configuration 
             where profile_type = '驾驶员画像' {sqlwhere} 
             and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration 
            where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota3_new( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"

        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '3' as quota_level,quota_id2 as parent_id, quota_id3 as quota_id, quota_name3 as quota_name,
             case when weight_rate3=0 then ROUND(CAST(calculate_weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate from ai_security.obs_quota_weight_configuration_new 
             where profile_type = '驾驶员画像' {sqlwhere} 
             and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration_new 
            where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota4( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql =f""" select distinct '4' as quota_level,quota_id3 as parent_id, quota_id4 as quota_id, quota_name4 as quota_name,
                quota_name1 as quota_name1,quota_name2 as quota_name2,quota_name3 as quota_name3, 
               case when weight_rate4=0 then ROUND(CAST(calculate_weight_rate4 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate4 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate from ai_security.obs_quota_weight_configuration 
               where profile_type = '驾驶员画像' and quota_name4<>'-' and quota_name4<>'' {sqlwhere} 
             and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration 
            where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere})"""
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_quota4_new( self,
            _id: str = None,_start_time: str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if _id is not None and _id!='':
            sqlwhere = f" and quota_id1 = '{_id}'"
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql =f""" select distinct '4' as quota_level,quota_id3 as parent_id, quota_id4 as quota_id, quota_name4 as quota_name,
                quota_name1 as quota_name1,quota_name2 as quota_name2,quota_name3 as quota_name3, 
               case when weight_rate4=0 then ROUND(CAST(calculate_weight_rate4 AS DECIMAL(12, 6)) / 100.0, 6) else ROUND(CAST(weight_rate4 AS DECIMAL(12, 6)) / 100.0, 6) end as weight_rate from ai_security.obs_quota_weight_configuration_new
               where profile_type = '驾驶员画像' and quota_name4<>'-' and quota_name4<>'' {sqlwhere} 
             and toDate(start_time) GLOBAL in (select max(toDate(start_time)) from ai_security.obs_quota_weight_configuration_new 
            where profile_type='驾驶员画像' and deleted!='1' {sqlwhere} {strwhere})"""
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_attitude_weights(self,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" 
        select distinct '2' as quota_level, profile_type ||'-' || quota_name1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
        case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
         case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
        start_time
        from ai_security.obs_quota_weight_configuration where
        profile_type = '驾驶员画像' and quota_name1='服务态度' and deleted != '1' and start_time GLOBAL in (select max(start_time)
        from ai_security.obs_quota_weight_configuration where profile_type = '驾驶员画像' and quota_name1='服务态度' and deleted != '1' {strwhere} ) 
         """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_safety_weights(self,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" 
        select distinct '2' as quota_level, profile_type ||'-' || quota_name1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
        case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
         case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
        start_time
        from ai_security.obs_quota_weight_configuration where
        profile_type = '驾驶员画像' and quota_name1='安全评价' and deleted != '1' and start_time GLOBAL in (select max(start_time)
        from ai_security.obs_quota_weight_configuration where profile_type = '驾驶员画像' and quota_name1='安全评价' and deleted != '1' {strwhere}) 
         """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_scores(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # sql =f"""
        #     WITH m_score AS (
        #         SELECT main_id AS id,
        #                ROUND(SUM(score * weight_rate),4) AS score
        #         FROM ai_security.abs_driver_quota_score_sub
        #         WHERE ppartition = '{_start_time}'
        #           AND quota_level = '1'
        #         GROUP BY main_id
        #     ),
        #     m_type AS (
        #         SELECT dict_id,
        #                item_text,
        #                item_value,
        #                CAST(splitByString('-', item_value)[1] AS INT) AS minchar,
        #                CAST(splitByString('-', item_value)[2] AS INT) AS maxchar
        #         FROM ai_security.sys_dict_item sdi
        #         WHERE dict_id GLOBAL IN (
        #             SELECT id
        #             FROM ai_security.sys_dict sd
        #             WHERE sd.dict_code = 'risk_level'
        #         )
        #     ),
        #     b_route AS (
        #         SELECT
        #             employee_id,
        #             route_id,
        #             organ_id
        #         FROM canbus.ods_jituan_bs_employee
        #     ),
        #     b_total as (select count(*) as num ,route_id FROM canbus.ods_jituan_bs_employee group by route_id),
        #     sort_rank AS (
        #     SELECT
        #         driver_id,
        #         ROW_NUMBER() OVER (PARTITION BY ppartition,route_id ORDER BY score DESC) AS group_sort_rank,
        #         route_total
        #     FROM m_score
        #   )
        #     SELECT distinct
        #         a.ppartition as ppartition,
        #         a.id as id,
        #         a.driver_id as driver_id,
        #         a.driver_name as driver_name,
        #         a.organ_id as organ_id,
        #         a.organ_name as organ_name,
        #         a.calculate_date as calculate_date,
        #         c.item_text AS evalutaion_type,
        #         b.score as score,
        #         a.suggested_content as suggested_content,
        #         a.creator as creator,
        #         a.create_time as create_time,
        #         a.updater as updater,
        #         a.update_time as update_time
        #     FROM ai_security.abs_driver_profile_main a
        #     GLOBAL INNER JOIN m_score b ON a.id = b.id
        #     GLOBAL INNER JOIN m_type c ON 1 = 1
        #     GLOBAL INNER JOIN b_route b ON a.driver_id = b.employee_id
        #     GLOBAL inner join b_total c on b.route_id=c.route_id
        #     WHERE round(b.score) >= c.minchar AND round(b.score) <= c.maxchar;
        #     """
        sql=f"""
        WITH m_score AS (
               SELECT 
			    main_id AS id, 
			    ROUND(SUM(total_score), 4) AS score,
			    ROUND(SUM(acc_score_part), 4) AS acc_score       
			FROM (
			    SELECT 
			        main_id,
			        score * weight_rate AS total_score,
			        if(quota_id = '驾驶员画像-事故风险', score * weight_rate, 0) AS acc_score_part
			    FROM ai_security.abs_driver_quota_score_sub 
			    WHERE ppartition = '{_start_time}'
			      AND quota_level = '1'
			) t
			GROUP BY main_id
            ),
            m_type AS (
                SELECT dict_id, 
                       item_text, 
                       item_value,
                       CAST(splitByString('-', item_value)[1] AS INT) AS minchar,
                       CAST(splitByString('-', item_value)[2] AS INT) AS maxchar 
                FROM ai_security.sys_dict_item sdi 
                WHERE dict_id GLOBAL IN (
                    SELECT id 
                    FROM ai_security.sys_dict sd 
                    WHERE sd.dict_code = 'risk_level'
                )
            ),
            b_route AS (
                SELECT 
                    employee_id,
                    route_id,
                    organ_id  
                FROM canbus.ods_jituan_bs_employee 
            ),
            b_total as (select count(*) as num ,route_id FROM canbus.ods_jituan_bs_employee group by route_id),
            sort_rank AS (
            SELECT 
                a.id as id,b.driver_id as driver_id,c.route_id as route_id, 
                ROW_NUMBER() OVER (PARTITION BY c.route_id ORDER BY a.score desc ) AS group_sort_rank,
                ROW_NUMBER() OVER (PARTITION BY c.route_id ORDER BY a.acc_score desc ) AS group_acc_sort_rank,
                d.num as route_total
            FROM m_score a 
            
            GLOBAL inner join ai_security.abs_driver_profile_main b on a.id=b.id 
            GLOBAL inner join b_route c on b.driver_id=c.employee_id 
            GLOBAL inner join b_total d on c.route_id=d.route_id
          )
            SELECT distinct
                a.ppartition as ppartition,
                a.id as id,
                a.driver_id as driver_id,
                a.driver_name as driver_name,
                a.organ_id as organ_id,
                a.organ_name as organ_name,
                a.calculate_date as calculate_date,
                c.item_text AS evalutaion_type,
                b.score as score,
                a.suggested_content as suggested_content,
                a.creator as creator,
                a.create_time as create_time,
                a.updater as updater,
                a.update_time as update_time,
                d.group_sort_rank as route_rank,
                d.group_acc_sort_rank as route_acc_rank,
                d.route_total as route_total,
                case when d.route_total=0 then 0 else (d.group_sort_rank*100/d.route_total) end as route_rate   
            FROM ai_security.abs_driver_profile_main a
            GLOBAL INNER JOIN m_score b ON a.id = b.id
            GLOBAL INNER JOIN m_type c ON 1 = 1  
            GLOBAL INNER JOIN sort_rank d ON a.id = d.id 
            WHERE round(b.score) >= c.minchar AND round(b.score) <= c.maxchar
            order by route_id,group_sort_rank;
        """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_scores_new(self, _start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""
            WITH m_score AS (
                   SELECT 
    			    main_id AS id, 
    			    ROUND(SUM(total_score), 4) AS score,
    			    ROUND(SUM(acc_score_part), 4) AS acc_score       
    			FROM (
    			    SELECT 
    			        main_id,
    			        score * weight_rate AS total_score,
    			        if(quota_id = '驾驶员画像-事故风险', score * weight_rate, 0) AS acc_score_part
    			    FROM ai_security.abs_driver_quota_score_sub_new 
    			    WHERE ppartition = '{_start_time}'
    			      AND quota_level = '1'
    			) t
    			GROUP BY main_id
                ),
                m_type AS (
                    SELECT dict_id, 
                           item_text, 
                           item_value,
                           CAST(splitByString('-', item_value)[1] AS INT) AS minchar,
                           CAST(splitByString('-', item_value)[2] AS INT) AS maxchar 
                    FROM ai_security.sys_dict_item sdi 
                    WHERE dict_id GLOBAL IN (
                        SELECT id 
                        FROM ai_security.sys_dict sd 
                        WHERE sd.dict_code = 'risk_level'
                    )
                ),
                b_route AS (
                    SELECT 
                        employee_id,
                        route_id,
                        organ_id  
                    FROM canbus.ods_jituan_bs_employee 
                ),
                b_total as (select count(*) as num ,route_id FROM canbus.ods_jituan_bs_employee group by route_id),
                sort_rank AS (
                SELECT 
                    a.id as id,b.driver_id as driver_id,c.route_id as route_id, 
                    ROW_NUMBER() OVER (PARTITION BY c.route_id ORDER BY a.score desc ) AS group_sort_rank,
                    ROW_NUMBER() OVER (PARTITION BY c.route_id ORDER BY a.acc_score desc ) AS group_acc_sort_rank,
                    d.num as route_total
                FROM m_score a 
                GLOBAL inner join ai_security.abs_driver_profile_main_new b on a.id=b.id 
                GLOBAL inner join b_route c on b.driver_id=c.employee_id 
                GLOBAL inner join b_total d on c.route_id=d.route_id
              )
                SELECT distinct
                    a.ppartition as ppartition,
                    a.id as id,
                    a.driver_id as driver_id,
                    a.driver_name as driver_name,
                    a.organ_id as organ_id,
                    a.organ_name as organ_name,
                    a.calculate_date as calculate_date,
                    c.item_text AS evalutaion_type,
                    b.score as score,
                    a.suggested_content as suggested_content,
                    a.creator as creator,
                    a.create_time as create_time,
                    a.updater as updater,
                    a.update_time as update_time,
                    d.group_sort_rank as route_rank,
                    d.group_acc_sort_rank as route_acc_rank,
                    d.route_total as route_total,
                    case when d.route_total=0 then 0 else (d.group_sort_rank*100/d.route_total) end as route_rate   
                FROM ai_security.abs_driver_profile_main_new a
                GLOBAL INNER JOIN m_score b ON a.id = b.id
                GLOBAL INNER JOIN m_type c ON 1 = 1  
                GLOBAL INNER JOIN sort_rank d ON a.id = d.id 
                WHERE round(b.score) >= c.minchar AND round(b.score) <= c.maxchar
                order by route_id,group_sort_rank;
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas


    async def get_driver_report(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        sql =f"""
            select driver_id,driver_name,ppartition from ai_security.abs_driver_profile_main where ppartition='{_start_time}' order by score desc limit 2 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_drivers(self)-> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" select employee_id as driver_id ,employee_name as driver_name,a.organ_id as organ_id,b.organ_name as organ_name
            from canbus.ods_jituan_bs_employee a 
            GLOBAL inner join canbus.ods_jituan_bs_organ b on a.organ_id=b.organ_id where a.organ_id<>''"""
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_driver_profile_main_organ( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,driver_id,driver_name,organ_id,organ_name from ai_security.abs_driver_profile_main where  deleted!='1' and  organ_id =''"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_datas_streaming(
            self,
            _table_name: str = None, sqlwhere: str = None,columns:[] = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""select * from {_table_name}"""
        if sqlwhere is not None:
            sql = sql + f" where {sqlwhere}"
        print(f"开始读取{_table_name}数据...")
        columns= await manager.execute_query_and_column(sql+" LIMIT 0")
        start_time = time.time()
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()

        if not df.empty:
            print(f"数据读取成功!")
            print(f"总行数: {len(df)}")
            print(f"耗时: {end_time - start_time:.2f} 秒")
            print(f"列数: {len(df.columns)}")
            # print("\n数据预览:")
            # print(df.head())
        else:
            print("数据读取失败!")

        return df

    async def get_energy_datas_streaming(
            self,
            _start_time_str: str = None,_end_time_str: str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        print("开始读取全量驾驶行为统计数据...")
        start_time = time.time()
        # sql = "select * from ai_security.v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week"
        sql = sql_config.v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week(_start_time_str,_end_time_str)
        columns= await manager.execute_query_and_column(sql+" LIMIT 0")
        start_time = time.time()
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()
        print(f"耗时: {end_time - start_time:.2f} 秒")
        return df

    async def get_driver_attitude(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""  
            with cet as (select involve_employee_code,involve_employee_name,
            toDate(happen_time) as happen_date,line_code,line_name,
            sum(case when project_category='车辆技术' then 1 else 0 end) as skill_times,
            sum(case when project_category='安全管理' then 1 else 0 end) as secure_times,
            sum(case when project_category='服务质量' then 1 else 0 end) as service_times
            from ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_service_consultation
            where project_category GLOBAL in ('车辆技术','安全管理','服务质量') and involve_employee_name<>'' and toDate(happen_time) ='{_start_time}'
            group by involve_employee_code,involve_employee_name, toDate(happen_time),line_code,line_name)
            select a.employee_id as involve_employee_code,a.employee_name as involve_employee_name,'{_start_time}' as happen_date,
            COALESCE(b.line_code,a.route_id) as line_code,COALESCE(b.line_name,d.route_name) as line_name,b.skill_times as skill_times,
            b.secure_times as secure_times,b.service_times as service_times,a.organ_id as org_id,c.organ_name as org_name,c.org_code as org_code   
            from canbus.ods_jituan_bs_employee a GLOBAL left outer join cet b  on a.employee_id=b.involve_employee_code 
            GLOBAL inner join canbus.ods_jituan_bs_organ c on a.organ_id=c.organ_id 
            GLOBAL inner join canbus.ods_jituan_bs_route d on a.route_id=d.route_id 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    # 保存服务态度分数
    async def save_attitude_scores_data(self,_start_time, attitude_datas):
        manager = ClickHouseManage(self.db, "")
        _start_date = datetime.strptime(_start_time, '%Y-%m-%d')
        _end_date = _start_date
        ppartition = _start_date.strftime('%Y%m%d')
        driver_profile_main_datas = await Driver(self.db).get_abs_driver_profile_main(ppartition)
        driver_ids = []
        if driver_profile_main_datas:
            for d in driver_profile_main_datas:
                driver_ids.append(d['driver_id'])

        main_datas = []
        quota_scores = []
        for data in attitude_datas:
            if data['employee_code'] in driver_ids:
                x = driver_ids.index(data['employee_code'])
                main_id = driver_profile_main_datas[x]['id']
                profile_main = None
            else:
                main_id = str(uuid.uuid4())
                profile_main = AbsDriverProfileMain(
                    ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                    id=main_id,
                    driver_id=str(data['employee_code']),
                    driver_name=data['employee_name'],
                    organ_id=str(data['org_id']),
                    organ_name=data['org_name'],
                    calculate_date=_end_date,
                    evalutaion_type="",
                    score=0,
                    suggested_content="",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    route_rank=0,
                    route_acc_rank=0,
                    route_total=0,
                    route_rate=0.00
                )
            if main_id=='00063423-5293-4853-8bbe-83ab7098a127':
                print(main_id)

            quota_score = AbsDriverQuotaScoreSub(
                ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                id=str(uuid.uuid4()),
                main_id=main_id,
                quota_id="驾驶员画像-服务态度",
                quota_name="服务态度",
                score=round(data['total_weighted_score'],6),
                weight_rate=round(data['attitude_weight'],6),
                original_value=round(data['total_global_score'],6),
                risk_data="",
                quota_level="1",
                parent_id="驾驶员画像",
                creator="system",
                create_time=datetime.now(),
                updater="system",
                update_time=datetime.now(),
                deleted="0",
                start_time=_start_date,
                end_time=_end_date,
            )
            quota_scores.append(quota_score.to_dict())
            quota_score = AbsDriverQuotaScoreSub(
                ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                id=str(uuid.uuid4()),
                main_id=main_id,
                quota_id="驾驶员画像-服务态度-服务质量投诉次数",
                quota_name="服务质量投诉次数",
                score=round(data['raw_score_service'],6),
                weight_rate=round(data['global_weight_service'],6),
                original_value=round(data['global_service'],6),
                risk_data=str(data['service_times']),
                quota_level="2",
                parent_id="驾驶员画像-服务态度",
                creator="system",
                create_time=datetime.now(),
                updater="system",
                update_time=datetime.now(),
                deleted="0",
                start_time=_start_date,
                end_time=_end_date,
            )
            quota_scores.append(quota_score.to_dict())
            quota_score = AbsDriverQuotaScoreSub(
                ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                id=str(uuid.uuid4()),
                main_id=main_id,
                quota_id="驾驶员画像-服务态度-车辆技术投诉次数",
                quota_name="车辆技术投诉次数",
                score=round(data['raw_score_skill'],6),
                weight_rate=round(data['global_weight_skill'],6),
                original_value=round(data['global_skill'],6),  # 全局能耗分数
                risk_data=str(data['skill_times']),
                quota_level="2",
                parent_id="驾驶员画像-服务态度",
                creator="system",
                create_time=datetime.now(),
                updater="system",
                update_time=datetime.now(),
                deleted="0",
                start_time=_start_date,
                end_time=_end_date,
            )
            quota_scores.append(quota_score.to_dict())
            quota_score = AbsDriverQuotaScoreSub(
                ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                id=str(uuid.uuid4()),
                main_id=main_id,
                quota_id="驾驶员画像-服务态度-安全管理投诉次数",
                quota_name="安全管理投诉次数",
                score=round(data['raw_score_secure'],6),
                weight_rate=round(data['global_weight_secure'],6),
                original_value=round(data['global_secure'],6),  # 全局能耗分数
                risk_data=str(data['secure_times']),
                quota_level="2",
                parent_id="驾驶员画像-服务态度",
                creator="system",
                create_time=datetime.now(),
                updater="system",
                update_time=datetime.now(),
                deleted="0",
                start_time=_start_date,
                end_time=_end_date,
            )
            quota_scores.append(quota_score.to_dict())
            if profile_main is not None:
                main_datas.append(profile_main.to_dict())
        # 保存服务态度数据
        await Driver(self.db).save(main_datas, quota_scores)

    async def save_safety_scores_data(self,_start_time, safety_datas,safety_weights):
        manager = ClickHouseManage(self.db, "")
        _start_date = datetime.strptime(_start_time, '%Y-%m-%d')
        _end_date = _start_date
        ppartition = _start_date.strftime('%Y%m%d')
        driver_profile_main_datas = await Driver(self.db).get_abs_driver_profile_main(ppartition)
        driver_ids = []
        if driver_profile_main_datas:
            for d in driver_profile_main_datas:
                driver_ids.append(d['driver_id'])

        main_datas = []
        quota_scores = []
        for data in safety_datas:
            if data['employee_id'] in driver_ids:
                x = driver_ids.index(data['employee_id'])
                main_id = driver_profile_main_datas[x]['id']
                profile_main = None
            else:
                main_id = str(uuid.uuid4())
                profile_main = AbsDriverProfileMain(
                    ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                    id=main_id,
                    driver_id=data['employee_id'],
                    driver_name=data['employee_name'],
                    organ_id=data['org_id'],
                    organ_name=data['org_name'],
                    calculate_date=_end_date,
                    evalutaion_type="",
                    score=0,
                    suggested_content="",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    route_rank=0,
                    route_acc_rank=0,
                    route_total=0,
                    route_rate=0.00
                )
            quota_score = AbsDriverQuotaScoreSub(
                ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                id=str(uuid.uuid4()),
                main_id=main_id,
                quota_id="驾驶员画像-安全评价",
                quota_name="安全评价",
                score=data['weighted_total_score'],
                weight_rate=data['global_weight'],
                original_value=data['global_total_score'],
                risk_data='',
                quota_level="1",
                parent_id="驾驶员画像",
                creator="system",
                create_time=datetime.now(),
                updater="system",
                update_time=datetime.now(),
                deleted="0",
                start_time=_start_date,
                end_time=_end_date,
            )
            quota_scores.append(quota_score.to_dict())
            for col in safety_weights.items():
                quota_score = AbsDriverQuotaScoreSub(
                    ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                    id=str(uuid.uuid4()),
                    main_id=main_id,
                    quota_id="驾驶员画像-安全评价-"+col[0],
                    quota_name=col[0],
                    score=data[col[0]+'_score'],
                    weight_rate=data[col[0]+'_global_weight'],
                    original_value=data[col[0]+'_global_score'],
                    risk_data=str(data[col[0]+'_rate']),
                    quota_level="2",
                    parent_id="驾驶员画像-安全评价",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    start_time=_start_date,
                    end_time=_end_date,
                )
                quota_scores.append(quota_score.to_dict())
            if profile_main is not None:
                main_datas.append(profile_main.to_dict())
                # 保存安全评价数据
        await Driver(self.db).save(main_datas, quota_scores)

    async def get_warning_driver_1d(self,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql=f"""    
        select a.ppartition as ppartition,toString(generateUUIDv4()) as id,a.id as main_id,
        'system' as creator,now() as create_time,'system' as updater,
        now() as update_time,'0' as deleted 
        from ai_security.abs_driver_profile_main a 
        where a.ppartition='{_start_time}' and a.evalutaion_type='危险型'
        """
        datas = await manager.get_data_sql_dict(sql)
        return datas

async def get_accident_weights(quota_level:str,_id:str,_start_time:str)-> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            if quota_level == "1":
                datas = await Driver(client).get_driver_quota1(_id,_start_time)
                return float(datas[0]['weight_rate'])
            if quota_level == "2":
                datas = await Driver(client).get_driver_quota2(_id,_start_time)
            if quota_level == "3":
                datas = await Driver(client).get_driver_quota3(_id,_start_time)
            if quota_level == "4":
                datas= await Driver(client).get_driver_quota4(_id,_start_time)
            # result = {}
            # for data in datas:
            #     result[data.get('quota_name')] =float(data['weight_rate'])
            return datas
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")


async def get_accident_weights_new(quota_level:str,_id:str,_start_time:str)-> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            if quota_level == "1":
                datas = await Driver(client).get_driver_quota1_new(_id,_start_time)
                return float(datas[0]['weight_rate'])
            if quota_level == "2":
                datas = await Driver(client).get_driver_quota2_new(_id,_start_time)
            if quota_level == "3":
                datas = await Driver(client).get_driver_quota3_new(_id,_start_time)
            if quota_level == "4":
                datas= await Driver(client).get_driver_quota4_new(_id,_start_time)
            # result = {}
            # for data in datas:
            #     result[data.get('quota_name')] =float(data['weight_rate'])
            return datas
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")


async def get_ads_driver_mileage_yearly () -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            all_fields=' ppartition,organ_name,driver_code,driver_name,total_mileage '
            df=await Driver(client).get_datas_streaming('ads_driver_mileage_yearly',None,all_fields)
            return df
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")

async def delete_driver_datas (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df = await Driver(client).delete_data_by_ppartition('abs_driver_profile_main', _start_time)
            df = await Driver(client).delete_data_by_ppartition('abs_driver_quota_score_sub',_start_time)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_driver_weights_datas (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            strwhere=f" profile_type='驾驶员画像' and toDate(start_time)='{_start_time}'"
            df=await Driver(client).delete_data_by_where('obs_quota_weight_configuration',strwhere)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_driver_main_datas (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df=await Driver(client).delete_data_by_ppartition('abs_driver_profile_main',_start_time)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_warning_driver_1d (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df=await Driver(client).delete_data_by_ppartition('abs_warning_driver_profile',_start_time)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_driver_main_datas_new (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df=await Driver(client).delete_data_by_ppartition('abs_driver_profile_main_new',_start_time)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")
#保存服务态度权重
async def save_attitude_weights_data(_start_time,category_weights):
    try:
        start_date_ = datetime.strptime(_start_time, '%Y-%m-%d')
        end_date = get_next_month_day(start_date_)
        end_date_ = end_date - timedelta(days=1)
        async with await connect_to_clickhouse() as client:
            _list = await Driver(client).get_attitude_weights("",get_last_month_day(start_date_).strftime('%Y-%m-%d'))
            for item in _list:
                item['id'] = str(uuid.uuid4())
                item['calculate_weight_rate1'] = 20
                item['calculate_weight_rate2'] = category_weights[item['quota_name2']]*100
                item['calculate_weight_rate3'] = 0
                item['quoa_unit3'] = "次数"
                item['start_time'] = start_date_
                item['end_time'] = end_date_
                item['creator'] = "system"
                item['create_time'] = datetime.now()
                item['updater'] = "system"
                item['update_time'] = datetime.now()

                # 保存权重
            await Driver(client).save_weights(_list)
            return _list
    except Exception as e:
        print(f"驾驶员服务态度保存权重执行出错: {e}")
    print("数据库连接已关闭")


#保存安全评价态度权重
async def save_safety_weights_data(_start_time,safety_weights):
    try:
        start_date_ = datetime.strptime(_start_time, '%Y-%m-%d')
        end_date = get_next_month_day(start_date_)
        end_date_ = end_date - timedelta(days=1)
        async with await connect_to_clickhouse() as client:
            _list = await Driver(client).get_safety_weights("",get_last_month_day(start_date_).strftime('%Y-%m-%d'))
            quota_name_list=[]
            _weights_list=[]
            for item in _list:
                quota_name_list.append(item['quota_name2'])
            for key,value in safety_weights.items():
                item={}
                if key in quota_name_list:
                    x = quota_name_list.index(key)
                    item = _list[x]
                else:
                    item['profile_type']='驾驶员画像'
                    item['quota_id1']='驾驶员画像-安全评价'
                    item['quota_name1']='安全评价'
                    item['weight_rate1']=0
                    item['quoa_desc1']=''
                    item['quoa_unit1']=''
                    item['quota_id2']='驾驶员画像-安全评价-'+ key
                    item['quota_name2']=key
                    item['weight_rate2']=0
                    item['quoa_desc2']=''
                    item['quoa_unit2']=''
                    item['quota_id3']=item['quota_id2']+'-'
                    item['quota_name3']='-'
                    item['weight_rate3']=0
                    item['quoa_desc3']=''
                    item['quota_id4']=item['quota_id3']+'----'
                    item['quota_name4']='-'
                    item['calculate_weight_rate4']=0
                    item['weight_rate4']=0
                    item['quoa_desc4']=''
                    item['quoa_unit4']=''
                item['id'] = str(uuid.uuid4())
                item['calculate_weight_rate1'] = 25
                # item['calculate_weight_rate2'] = safety_weights[item['quota_name2']]*100
                item['calculate_weight_rate2'] = value * 100
                item['calculate_weight_rate3'] = 0
                item['quoa_unit3'] = "次数"
                item['start_time'] = start_date_
                item['end_time'] = end_date_
                item['creator'] = "system"
                item['create_time'] = datetime.now()
                item['updater'] = "system"
                item['update_time'] = datetime.now()
                _weights_list.append(item)
                # 保存权重
            await Driver(client).save_weights(_weights_list)
            return _list
    except Exception as e:
        print(f"驾驶员安全评价保存权重执行出错: {e}")
    print("数据库连接已关闭")

async def read_raw_sql(query):
    try:
        async with await connect_to_clickhouse() as client:
            column_names, data = await Driver(client).execute_query_and_export(query)
            df = pd.DataFrame(data, columns=column_names)
            return df
    except Exception as e:
        print(f"驾驶员画像取数执行出错: {e}")
    print("数据库连接已关闭")

async def save_accident_weight(results,_start_time:str,_end_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(_start_time, '%Y-%m-%d')
            _end_date = get_next_month_day(start_date)  # + timedelta(days=30)
            quota_accident_quota_datas = await Driver(client).get_driver_accident_quota_datas("驾驶员画像-事故风险",get_last_month_day(start_date).strftime('%Y-%m-%d'))
            end_date = _end_date - timedelta(days=1)
            for d_quota_name3 in quota_accident_quota_datas:
                    d_quota_name3['id'] = str(uuid.uuid4())
                    d_quota_name3['calculate_weight_rate1'] = Compute.scientific_to_percentage(results['feat_weights_1'])
                    x = d_quota_name3.get('quota_name2')
                    converted_weight2 = Compute.safe_float_conversion(results['feat_weights_2'][x])
                    if converted_weight2 is not None:
                        calculate_weight2 = Compute.scientific_to_percentage(converted_weight2)
                    else:
                        calculate_weight2 = 0.00
                    d_quota_name3['calculate_weight_rate2'] = calculate_weight2
                    x = d_quota_name3.get('quota_name3')
                    if x in results['feat_weights_3']:
                        converted_weight3 = Compute.safe_float_conversion(results['feat_weights_3'][x])
                        if converted_weight3 is not None:
                            calculate_weight3 = Compute.scientific_to_percentage(converted_weight3)
                        else:
                            calculate_weight3 = 0.00
                        d_quota_name3['calculate_weight_rate3']=calculate_weight3
                    x = d_quota_name3.get('quota_name4')
                    if x!="-" and x!="" :
                        if x in results['feat_weights_4']:
                            converted_weight4 = Compute.safe_float_conversion(results['feat_weights_4'][x])
                            if converted_weight4 is not None:
                                calculate_weight4 = Compute.scientific_to_percentage(converted_weight4)
                            else:
                                calculate_weight4 = 0.00
                            d_quota_name3['calculate_weight_rate4'] = calculate_weight4
                    d_quota_name3['start_time'] = start_date #datetime.combine(datetime.now().date(), datetime.min.time())
                    d_quota_name3['end_time'] = end_date #datetime.combine(datetime.now().date() + timedelta(weeks=1),datetime.min.time())
                    d_quota_name3['creator'] = "system"
                    d_quota_name3['create_time'] = datetime.now()
                    d_quota_name3['updater'] = "system"
                    d_quota_name3['update_time'] = datetime.now()
            # 保存权重
            await Driver(client).save_weights(quota_accident_quota_datas)
    except Exception as e:
        print(f"保存驾驶员权重出错: {e}")
    print("数据库连接已关闭")

async def save_accident_1h_weight(results,_start_time:str,_end_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_time=datetime.strptime(_start_time, '%Y-%m-%d %H:%M:%S')
            quota_accident_quota_datas = await Driver(client).get_driver_accident_quota_datas("驾驶员画像-事故小时风险",get_last_month_day(start_time).strftime('%Y-%m-%d'))
            start_date=datetime.strptime(_start_time.split(' ')[0], '%Y-%m-%d')
            end_date = get_next_month_day(start_date)-timedelta(days=1)
            for d_quota_name3 in quota_accident_quota_datas:
                d_quota_name3['id'] = str(uuid.uuid4())
                d_quota_name3['calculate_weight_rate1'] = 100
                d_quota_name3['calculate_weight_rate2'] = 100
                x = d_quota_name3.get('quota_name3')
                if x in results['feat_weights']:
                    converted_weight3 = Compute.safe_float_conversion(results['feat_weights'][x])
                    if converted_weight3 is not None:
                        calculate_weight3 = Compute.scientific_to_percentage(converted_weight3)
                    else:
                        calculate_weight3 = 0.00
                    d_quota_name3['calculate_weight_rate3']=calculate_weight3
                d_quota_name3['calculate_weight_rate4'] = 0
                d_quota_name3['start_time'] = start_date #datetime.combine(datetime.now().date(), datetime.min.time())
                d_quota_name3['end_time'] = end_date #datetime.combine(datetime.now().date() + timedelta(weeks=1),datetime.min.time())
                d_quota_name3['creator'] = "system"
                d_quota_name3['create_time'] = datetime.now()
                d_quota_name3['updater'] = "system"
                d_quota_name3['update_time'] = datetime.now()
        # 保存权重
        await Driver(client).save_weights(quota_accident_quota_datas)
    except Exception as e:
        print(f"保存驾驶员权重出错: {e}")
    print("数据库连接已关闭")


async def save_accident_score(results,_start_time:str,_end_date:str,info,base_cols,behavior_cols,illegal_cols):
    try:
        async with await connect_to_clickhouse() as client:
            start_date_=datetime.strptime(_start_time, '%Y-%m-%d')
            start_date_str = start_date_.strftime('%Y%m%d')
            ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')
            driver_weights_quota4 = await Driver(client).get_driver_quota4('驾驶员画像-事故风险', _start_time)
            driver_profile_main_datas = await Driver(client).get_abs_driver_profile_main(ppartition)
            driver_ids = []
            if driver_profile_main_datas:
                for d in driver_profile_main_datas:
                    driver_ids.append(d['driver_id'])
            main_datas = []
            quota_scores = []
            profile_main = None
            for i in range(len(info)):
                # if info[i][1]!='04000869':
                #     continue
                if info[i][1] in driver_ids:
                    x = driver_ids.index(info[i][1])
                    main_id = driver_profile_main_datas[x]['id']
                    profile_main = None
                else:
                    main_id = str(uuid.uuid4())
                    if info[i][2] is None:
                        d_organ_id = ""
                    else:
                        d_organ_id = info[i][2]
                    if info[i][3] is None:
                        d_organ_name = ""
                    else:
                        d_organ_name = info[i][3]
                    profile_main = AbsDriverProfileMain(
                        ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=main_id,
                        driver_id=info[i][1],
                        driver_name=info[i][0],
                        organ_id=d_organ_id,
                        organ_name=d_organ_name,
                        calculate_date=_start_time,  # datetime.combine(datetime.now().date(), datetime.min.time()),
                        evalutaion_type="",
                        score=0,
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        route_rank=0,
                        route_acc_rank=0,
                        route_total=0,
                        route_rate=0.00
                    )
                quota_score_1 = AbsDriverQuotaScoreSub(
                    ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                    id=str(uuid.uuid4()),
                    main_id=main_id,
                    quota_id="驾驶员画像-事故风险",
                    quota_name="事故风险",
                    score=round(float(results['raw_scores_1'][i]), 6),
                    weight_rate=round(float(results['feat_weights_1']), 6),
                    original_value=round(float(results['final_scores_1'][i]), 6),
                    risk_data="",
                    quota_level="1",
                    parent_id="驾驶员画像",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    start_time=start_date_,
                    end_time=start_date_,
                )
                quota_scores.append(quota_score_1.to_dict())
                for x in ['其他风险', '健康风险', '违法违章', '不良行为']:
                    quota_score_2 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-事故风险-" + x,
                        quota_name=x,
                        score=round(float(results['raw_scores_2'][x][i]), 6),
                        weight_rate=round(
                            round(float(results['feat_weights_1']), 6) * round(float(results['feat_weights_2'][x]), 6),
                            6),
                        original_value=round(float(results['final_scores_2'][x][i]), 6),
                        risk_data="",
                        quota_level="2",
                        parent_id="驾驶员画像-事故风险",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_2.to_dict())
                    if x == '其他风险':
                        feat_cols = base_cols
                    elif x == '健康风险':
                        feat_cols = ['生理状态', '精神状态']
                    elif x == '不良行为':
                        feat_cols = behavior_cols
                    elif x == '违法违章':
                        feat_cols = illegal_cols
                    for j, feat in enumerate(feat_cols):
                        if feat in results['data']:
                            _risk_data = str(results['data'][feat][i])
                        else:
                            _risk_data = ""
                        quota_score_3 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故风险-" + x + "-" + feat,
                            quota_name=feat,
                            score=round(float(results['raw_scores_3'][feat][i]), 6),
                            # weight_rate=round(results['feat_weights'][j], 5),
                            # original_value=round(results['final_scores'][feat][i], 1),
                            weight_rate=round(
                                round(float(results['feat_weights_1']), 6) * round(float(results['feat_weights_2'][x]),
                                                                                   6) * round(
                                    float(results['feat_weights_3'][feat]), 6), 6),
                            original_value=round(float(results['final_scores_3'][feat][i]), 6),
                            risk_data=_risk_data,
                            quota_level="3",
                            parent_id="驾驶员画像-事故风险-" + x,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                for quota in driver_weights_quota4:
                    if quota['quota_name'] in results['final_scores_4']:
                        quota_score_4 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=quota['quota_id'],
                            quota_name=quota['quota_name'],
                            score=round(float(results['raw_scores_4'][quota['quota_name']][i]), 6),
                            weight_rate=round(round(float(results['feat_weights_1']), 6) * round(
                                float(results['feat_weights_2'][quota['quota_name2']]), 6) *
                                              round(float(results['feat_weights_3'][quota['quota_name3']]), 6) *
                                              round(float(results['feat_weights_4'][quota['quota_name']]), 6), 6),
                            original_value=round(float(results['final_scores_4'][quota['quota_name']][i]), 6),
                            risk_data=str(results['data'][quota['quota_name']][i]),
                            quota_level="4",
                            parent_id=quota['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_4.to_dict())
                if profile_main is not None:
                    main_datas.append(profile_main.to_dict())
                # 保存驾驶员事故风险数据
            await Driver(client).save(main_datas, quota_scores)
    except Exception as e:
        logger.exception(f"驾驶员画像事故风险分数主程序执行出错:{e}")
        print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")


async def save_accident_1h_score(results,_start_time:str,_end_date:str,info,behavior_cols):
    try:
        async with await connect_to_clickhouse() as client:
            start_date_ =datetime.strptime(_start_time, '%Y-%m-%d %H:%M:%S')
            end_date_ =datetime.strptime(_end_date, '%Y-%m-%d %H:%M:%S')
            start_date_str = start_date_.strftime('%Y%m%d%H')
            ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')
            driver_profile_hour_main_datas = await Driver(client).get_abs_driver_profile_hour_main(ppartition)
            driver_ids = []
            if driver_profile_hour_main_datas:
                for d in driver_profile_hour_main_datas:
                    driver_ids.append(d['driver_id'])
            main_datas = []
            quota_scores = []
            profile_main = None
            for i in range(len(info)):
                # if info[i][1]!='68002424':
                #     continue
                if info[i][1] in driver_ids:
                    x = driver_ids.index(info[i][1])
                    main_id = driver_profile_hour_main_datas[x]['id']
                    profile_main = None
                else:
                    main_id = str(uuid.uuid4())
                    if info[i][2] is None:
                        d_organ_id = ""
                    else:
                        d_organ_id = info[i][2]
                    if info[i][3] is None:
                        d_organ_name = ""
                    else:
                        d_organ_name = info[i][3]
                    profile_main = AbsDriverProfileMain(
                        ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=main_id,
                        driver_id=info[i][1],
                        driver_name=info[i][0],
                        organ_id=d_organ_id,
                        organ_name=d_organ_name,
                        calculate_date=start_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
                        evalutaion_type="",
                        score=0,
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        route_rank=0,
                        route_acc_rank=0,
                        route_total=0,
                        route_rate=0.00
                    )
                    feat_cols = behavior_cols
                    quota3_datas_scores = []
                    for j, feat in enumerate(feat_cols):
                        if feat in results['data']:
                            _risk_data = str(results['data'][feat][i])
                        else:
                            _risk_data = ""
                        if round(float(results['feat_weights'][feat])*10000) == 0:
                            _score = 0
                        else:
                            _score = round(float(results['final_scores'][feat][i]), 6)/round(float(results['feat_weights'][feat]), 4)

                        quota_score_3 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故小时风险-不良行为" + "-" + feat,
                            quota_name=feat,
                            # score=round(float(results['raw_scores'][feat][i]), 6),
                            score=round(_score, 6),
                            weight_rate=round(float(results['feat_weights'][feat]),4),
                            original_value=round(float(results['final_scores'][feat][i]), 6),
                            risk_data=_risk_data,
                            quota_level="3",
                            parent_id="驾驶员画像-事故小时风险-不良行为" ,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota3_datas_scores.append(quota_score_3.to_dict())
                        quota_scores.append(quota_score_3.to_dict())
                    if quota3_datas_scores:
                        df_quota3=DataFrame(quota3_datas_scores)
                        sum_score=round(sum(df_quota3['original_value']),6)
                        quota_score_1 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故小时风险",
                            quota_name="事故小时风险",
                            score=sum_score,
                            weight_rate=1,
                            original_value=sum_score,
                            risk_data="",
                            quota_level="1",
                            parent_id="驾驶员画像",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                        quota_score_1 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故小时风险-不良行为",
                            quota_name="不良行为",
                            score=sum_score,
                            weight_rate=1,
                            original_value=sum_score,
                            risk_data="",
                            quota_level="2",
                            parent_id="驾驶员画像-事故小时风险",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                        profile_main.score = sum_score
                        profile_main.evalutaion_type= await Driver(client).get_risk_value_hour(round(sum_score))
                if profile_main is not None:
                    main_datas.append(profile_main.to_dict())
                    # 保存驾驶员事故风险数据
            await Driver(client).save_hour(main_datas, quota_scores)
    except Exception as e:
        print(f"保存驾驶员权重出错: {e}")
    print("数据库连接已关闭")


async def save_accident_weight_new(results,_start_time:str,_end_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(_start_time, '%Y-%m-%d')
            _end_date = get_next_month_day(start_date)  # + timedelta(days=30)
            quota_accident_quota_datas = await Driver(client).get_driver_accident_quota_datas("驾驶员画像-事故风险",get_last_month_day(start_date).strftime('%Y-%m-%d'))
            end_date = _end_date - timedelta(days=1)
            for d_quota_name3 in quota_accident_quota_datas:
                    d_quota_name3['id'] = str(uuid.uuid4())
                    d_quota_name3['calculate_weight_rate1'] = Compute.scientific_to_percentage(results['feat_weights_1'])
                    x = d_quota_name3.get('quota_name2')
                    converted_weight2 = Compute.safe_float_conversion(results['feat_weights_2'][x])
                    if converted_weight2 is not None:
                        calculate_weight2 = Compute.scientific_to_percentage(converted_weight2)
                    else:
                        calculate_weight2 = 0.00
                    d_quota_name3['calculate_weight_rate2'] = calculate_weight2
                    x = d_quota_name3.get('quota_name3')
                    if x in results['feat_weights_3']:
                        converted_weight3 = Compute.safe_float_conversion(results['feat_weights_3'][x])
                        if converted_weight3 is not None:
                            calculate_weight3 = Compute.scientific_to_percentage(converted_weight3)
                        else:
                            calculate_weight3 = 0.00
                        d_quota_name3['calculate_weight_rate3']=calculate_weight3
                    x = d_quota_name3.get('quota_name4')
                    if x!="-" and x!="" :
                        if x in results['feat_weights_4']:
                            converted_weight4 = Compute.safe_float_conversion(results['feat_weights_4'][x])
                            if converted_weight4 is not None:
                                calculate_weight4 = Compute.scientific_to_percentage(converted_weight4)
                            else:
                                calculate_weight4 = 0.00
                            d_quota_name3['calculate_weight_rate4'] = calculate_weight4
                    d_quota_name3['start_time'] = start_date #datetime.combine(datetime.now().date(), datetime.min.time())
                    d_quota_name3['end_time'] = end_date #datetime.combine(datetime.now().date() + timedelta(weeks=1),datetime.min.time())
                    d_quota_name3['creator'] = "system"
                    d_quota_name3['create_time'] = datetime.now()
                    d_quota_name3['updater'] = "system"
                    d_quota_name3['update_time'] = datetime.now()
            # 保存权重
            await Driver(client).save_weights_new(quota_accident_quota_datas)
    except Exception as e:
        print(f"保存驾驶员权重出错: {e}")
    print("数据库连接已关闭")

async def save_accident_score_new(results,_start_time:str,_end_date:str,info,base_cols,behavior_cols,illegal_cols):
    try:
        async with await connect_to_clickhouse() as client:
            start_date_=datetime.strptime(_start_time, '%Y-%m-%d')
            s_end_date_=start_date_-timedelta(days=6)
            start_date_str = start_date_.strftime('%Y%m%d')
            end_date_str = s_end_date_.strftime('%Y%m%d')
            ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')
            driver_weights_quota4 = await Driver(client).get_driver_quota4_new('驾驶员画像-事故风险', _start_time)
            # driver_profile_main_datas = await Driver(client).get_abs_driver_profile_main_new(ppartition)
            driver_profile_main_datas=[]
            driver_ids = []
            if driver_profile_main_datas:
                for d in driver_profile_main_datas:
                    driver_ids.append(d['driver_id'])
            main_datas = []
            quota_scores = []
            profile_main = None
            for i in range(len(info)):
                # if info[i][1]!='04000869':
                #     continue
                if info[i][1] in driver_ids:
                    x = driver_ids.index(info[i][1])
                    main_id = driver_profile_main_datas[x]['id']
                    profile_main = None
                else:
                    main_id = str(uuid.uuid4())
                    if info[i][2] is None:
                        d_organ_id = ""
                    else:
                        d_organ_id = info[i][2]
                    if info[i][3] is None:
                        d_organ_name = ""
                    else:
                        d_organ_name = info[i][3]
                    profile_main = AbsDriverProfileMain(
                        ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=main_id,
                        driver_id=info[i][1],
                        driver_name=info[i][0],
                        organ_id=d_organ_id,
                        organ_name=d_organ_name,
                        calculate_date=start_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
                        evalutaion_type="",
                        score=0,
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        route_rank=0,
                        route_acc_rank=0,
                        route_total=0,
                        route_rate=0.00
                    )
                quota_score_1 = AbsDriverQuotaScoreSub(
                    ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                    id=str(uuid.uuid4()),
                    main_id=main_id,
                    quota_id="驾驶员画像-事故风险",
                    quota_name="事故风险",
                    score=round(float(results['raw_scores_1'][i]), 6),
                    weight_rate=round(float(results['feat_weights_1']), 6),
                    original_value=round(float(results['final_scores_1'][i]), 6),
                    risk_data="",
                    quota_level="1",
                    parent_id="驾驶员画像",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    start_time=s_end_date_,
                    end_time=start_date_,
                )
                quota_scores.append(quota_score_1.to_dict())
                for x in ['其他风险', '健康风险', '违法违章', '不良行为']:
                    quota_score_2 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-事故风险-" + x,
                        quota_name=x,
                        score=round(float(results['raw_scores_2'][x][i]), 6),
                        weight_rate=round(
                            round(float(results['feat_weights_1']), 6) * round(float(results['feat_weights_2'][x]), 6),
                            6),
                        original_value=round(float(results['final_scores_2'][x][i]), 6),
                        risk_data="",
                        quota_level="2",
                        parent_id="驾驶员画像-事故风险",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=s_end_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_2.to_dict())
                    if x == '其他风险':
                        feat_cols = base_cols
                    elif x == '健康风险':
                        feat_cols = ['生理状态', '精神状态']
                    elif x == '不良行为':
                        feat_cols = behavior_cols
                    elif x == '违法违章':
                        feat_cols = illegal_cols
                    for j, feat in enumerate(feat_cols):
                        if feat in results['data']:
                            _risk_data = str(results['data'][feat][i])
                        else:
                            _risk_data = ""
                        quota_score_3 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故风险-" + x + "-" + feat,
                            quota_name=feat,
                            score=round(float(results['raw_scores_3'][feat][i]), 6),
                            # weight_rate=round(results['feat_weights'][j], 5),
                            # original_value=round(results['final_scores'][feat][i], 1),
                            weight_rate=round(
                                round(float(results['feat_weights_1']), 6) * round(float(results['feat_weights_2'][x]),
                                                                                   6) * round(
                                    float(results['feat_weights_3'][feat]), 6), 6),
                            original_value=round(float(results['final_scores_3'][feat][i]), 6),
                            risk_data=_risk_data,
                            quota_level="3",
                            parent_id="驾驶员画像-事故风险-" + x,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=s_end_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                for quota in driver_weights_quota4:
                    if quota['quota_name'] in results['final_scores_4']:
                        quota_score_4 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=quota['quota_id'],
                            quota_name=quota['quota_name'],
                            score=round(float(results['raw_scores_4'][quota['quota_name']][i]), 6),
                            weight_rate=round(round(float(results['feat_weights_1']), 6) * round(
                                float(results['feat_weights_2'][quota['quota_name2']]), 6) *
                                              round(float(results['feat_weights_3'][quota['quota_name3']]), 6) *
                                              round(float(results['feat_weights_4'][quota['quota_name']]), 6), 6),
                            original_value=round(float(results['final_scores_4'][quota['quota_name']][i]), 6),
                            risk_data=str(results['data'][quota['quota_name']][i]),
                            quota_level="4",
                            parent_id=quota['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=s_end_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_4.to_dict())
                if profile_main is not None:
                    main_datas.append(profile_main.to_dict())
                # 保存驾驶员事故风险数据
            await Driver(client).save_new(main_datas, quota_scores)
    except Exception as e:
        logger.exception(f"驾驶员画像事故风险分数主程序执行出错:{e}")
        print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")

async def update_driver_scores_main_new(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            # date_range = pd.date_range(start="2026-01-01", end="2026-01-01")
            date_range = [_start_time]
            for date in date_range:
                start_date=datetime.strptime(date,"%Y-%m-%d")
                start_time = start_date.strftime('%Y-%m-%d')
                _ppartition=start_date.strftime('%Y%m%d')

                list = await Driver(client).get_driver_scores_new(_ppartition)
                await delete_driver_main_datas_new(_ppartition)
                await Driver(client).save_new(list, [])
                # manager = ClickHouseManage(client, "abs_driver_profile_main")
                # data={}
                # for item in list:
                #     data['evalutaion_type']=await crud.Driver(client).get_risk_value(item['score'])
                #     data['score'] = item['score']
                #     await manager.put_data(item['id'],data)

    except Exception as e:
        print(f"驾驶安全评价执行出错: {e}")
    print("数据库连接已关闭")

async def save_warning_driver_week(result):
    try:
        async with await connect_to_clickhouse() as client:
                await Driver(client).save_warning("abs_warning_driver_week_profile",result,result[0]['score_date'])
    except Exception as e:
        print(f"驾驶安全评价执行出错: {e}")
    print("数据库连接已关闭")



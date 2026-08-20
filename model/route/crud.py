import time

import pandas as pd
# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core import sql_config
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger


# 数据库增删改查
class Route(ClickHouseManage):

    def __init__(self, db: Client):
        super(Route, self).__init__(db, "", "", "")

    async def get_risk_value(self, score) -> str | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.get_risk_value()
        datas = await manager.get_data_sql_dict(sql)
        for data in datas:
            parts = data['item_value'].strip().split('-')
            result = [int(part) for part in parts]
            min_val, max_val = result
            is_in_range = min_val <= round(score) <= max_val
            if is_in_range:
                return data['item_text']
        return ""

    # 每天生成驾驶行为坐标集合
    async def get_black_datas(
            self,
            _id: str = None, start_date_: str = None, end_date_: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.driver_behavior_month_query(start_date_, end_date_, _id).replace("\n", "")
        # sql = "SELECT * FROM ai_security.v_driver_behavior_month_coordinate"
        # datas = await manager.get_data_sql_dict(sql)
        # result = await manager.batch_insert("abs_driver_behavior_route_coordinates", datas, 10000)
        # table = "ods_communication_driver_behavior"
        # condition = f""" ppartition BETWEEN '{start_date_}' AND '{end_date_}' and station_code!=''
        #             and (latitude BETWEEN '22.562803' AND '23.935966')
        #             and (longitude BETWEEN '112.953161' AND '114.054546')
        #             and report_type IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 36, 37)
        #             """

        print("开始读取驾驶行为经纬度数据...")
        start_time = time.time()

        columns = ['longitude', 'latitude', 'report_type', 'route_id', 'organ_id']
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

        return df

    async def get_weigths_datas(
            self,
            _id: str = None, start_date_: str = None, end_date_: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.driver_behavior_weight_month_query(start_date_, end_date_, _id).replace("\n", "")
        #     sql = f"""
        #         SELECT
        #     quota_name3 as behavior_type_name,
        #     calculate_weight_rate3 as weight_rate,
        #     CASE quota_name3
        #         WHEN '起步急加速' THEN 1
        #         WHEN '急加速' THEN 2
        #         WHEN '急减速' THEN 3
        #         WHEN '急刹车' THEN 4
        #         WHEN '斑马线不文明礼让' THEN 5
        #         WHEN '斑马线超速' THEN 6
        #         WHEN '违规使用手刹' THEN 7
        #         WHEN '停站N档违规' THEN 8
        #         WHEN '违规使用N档' THEN 9
        #         WHEN '不规范转弯' THEN 10
        #         WHEN '车辆未停稳开车门' THEN 11
        #         WHEN '车辆起步不关车门' THEN 12
        #         WHEN '空档滑行' THEN 13
        #         WHEN '熄火滑行' THEN 14
        #         WHEN '不文明鸣笛' THEN 15
        #         WHEN '安全带行为' THEN 16
        #         WHEN '不规范进站' THEN 17
        #         WHEN '不规范出站' THEN 18
        #         WHEN '急停' THEN 19
        #         WHEN '门开禁启开关' THEN 20
        #         WHEN '停车不挂N挡' THEN 21
        #         WHEN '不规范开关门' THEN 22
        #         WHEN '安全启动' THEN 23
        #         WHEN '违规使用空调' THEN 24
        #         WHEN '平路不规范行为' THEN 25
        #         WHEN '上坡不规范行为' THEN 26
        #         WHEN '下坡不规范行为' THEN 27
        #         WHEN '违规使用总电' THEN 28
        #         WHEN '路口大油门' THEN 29
        #         WHEN '进站违规制动' THEN 30
        #         WHEN '区间超速' THEN 33
        #         WHEN '全局超速' THEN 34
        #         WHEN '左转弯未刹车' THEN 36
        #         WHEN '右转弯未刹车' THEN 37
        #     END AS behavior_type_code
        # FROM
        #     ai_security.obs_quota_weight_configuration
        # WHERE
        #     profile_type = '驾驶员画像'
        #     AND quota_name1 = '事故风险'
        #     AND quota_name2 = '不良行为'
        #     AND creator = 'system'
        #     AND quota_name3 GLOBAL IN (
        #         '起步急加速',
        #         '急加速',
        #         '急减速',
        #         '急刹车',
        #         '斑马线不文明礼让',
        #         '斑马线超速',
        #         '违规使用手刹',
        #         '停站N档违规',
        #         '违规使用N档',
        #         '不规范转弯',
        #         '车辆未停稳开车门',
        #         '车辆起步不关车门',
        #         '空档滑行',
        #         '熄火滑行',
        #         '不文明鸣笛',
        #         '安全带行为',
        #         '不规范进站',
        #         '不规范出站',
        #         '急停',
        #         '门开禁启开关',
        #         '停车不挂N挡',
        #         '不规范开关门',
        #         '安全启动',
        #         '违规使用空调',
        #         '平路不规范行为',
        #         '上坡不规范行为',
        #         '下坡不规范行为',
        #         '违规使用总电',
        #         '路口大油门',
        #         '进站违规制动',
        #         '区间超速',
        #         '全局超速',
        #         '左转弯未刹车',
        #         '右转弯未刹车'
        #     )
        #     order by behavior_type_code;"""
        #     print(sql)
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_behavior_route_coordinates(self, _id: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.abs_driver_behavior_route_coordinates_query('2025-12-31').replace("\n", "")
        # sql = "SELECT * FROM ai_security.abs_driver_behavior_route_coordinates where  "
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_fault_analysis_week_df(self, _id: str = None,
                                         start_time_str: str = None, end_time_str: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""
         SELECT route_id, route_name,sum(fault_type_D301_count) AS fault_type_D301_count,sum(fault_type_D26_count) AS fault_type_D26_count,
         sum(fault_type_D87_count) AS fault_type_D87_count
        FROM 
        (
        SELECT
            c.route_id, c.route_name,c.bus_id,c.ppartition,formatDateTime(c.fault_date,'%Y-%m-%d') AS fault_date,
            sum(multiIf(c.fault_type = 'D301',1,0)) AS fault_type_D301_count,sum(multiIf(c.fault_type = 'D26',1,0)) AS fault_type_D26_count,
            sum(multiIf(c.fault_type = 'D87',1,0)) AS fault_type_D87_count
        FROM ai_security.ads_fault_analysis AS c 
        WHERE ppartition between '{start_time_str}' AND '{end_time_str}' 
        GROUP BY c.route_id, c.route_name, c.ppartition, c.bus_id, formatDateTime(c.fault_date, '%Y-%m-%d')
        )
        GROUP BY route_id,route_name 
        """
        sql = sql.replace("\n", "")
        column_names, data = await manager.execute_query_and_export(sql)
        df = pd.DataFrame(data, columns=column_names)
        return df

    async def save_black_points(self, black_point_datas):
        insert_operations = [
            {
                "table": "abs_black_spot_prediction",
                "list": black_point_datas
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
                logger.info("驾驶员画像-能耗风险权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("驾驶员画像-能耗风险权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像-能耗风险权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def get_ods_jituan_bs_route(self):
        manager = ClickHouseManage(self.db, "")
        sql = f"select route_id,route_name,organ_id,b.organ_name as organ_name from canbus.ods_jituan_bs_route a GLOBAL inner join canbus.ods_jituan_bs_organ b on a.organ_id=b.organ_id "
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_route_quota1(self,
                               _id: str = None, _start_time: str = None
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name, 
            case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
            start_time from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted!='1' 
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='线路画像' and deleted!='1' {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_route_quota2(self,
                               _id: str = None, _start_time: str = None
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
            case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
            case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
            start_time from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted!='1' 
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='线路画像' and deleted!='1' {strwhere}) """
        if _id is not None and _id != '':
            sql = sql + f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_route_quota3(self,
                               _id: str = None, _start_time: str = None
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id, quota_name3 as quota_name,
            case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
            case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
            case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight_rate3,
            start_time  from ai_security.obs_quota_weight_configuration where profile_type = '线路画像'  and deleted!='1' 
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='线路画像' and deleted!='1' {strwhere}) """
        if _id is not None and _id != '':
            sql = sql + f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_quota_name3_datas(
            self,
            _id: str = None, _start_time: str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""select * from ai_security.obs_quota_weight_configuration where profile_type='线路画像' and deleted!='1'
                and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
                where profile_type='线路画像' and deleted!='1' {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_route_profile_main(self,
                                         _id: str = None,
                                         ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # ppartition='{_id}' and
        sql = f"select id,route_id from ai_security.abs_route_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_triplog_energy_week(self,
                                      _id: str = None, start_time_str: str = None, end_time_str: str = None,
                                      ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""
            SELECT id, triplog_id, route_id, is_run,run_mileage, run_mileage_can
            FROM canbus.ads_triplog_energy
            WHERE ppartition between '{start_time_str}' and '{end_time_str}' 
            """
        sql = sql.replace("\n", "")
        column_names, data = await manager.execute_query_and_export(sql)
        df = pd.DataFrame(data, columns=column_names)
        return df

    async def get_event_black_spot_df(self,
                                      _id: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" SELECT * FROM ai_security.ads_event_black_spot """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_line_hidden_danger_count(self,
                                           _id: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" SELECT * FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_hidden_danger_point """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_line_accident_count(self,
                                      _id: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" SELECT * FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_route_card_type_df(self,
                                     _id: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" SELECT * FROM ai_security.ads_line_cardtype_flow_daily """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_driver_behavior_week_df(self,
                                          _id: str = None, start_date_str: str = None,
                                          end_date_str: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.ods_communication_driver_bus_behavior_route_week_sum(start_date_str, end_date_str)
        sql = sql.replace("\n", "")
        column_names, data = await manager.execute_query_and_export(sql)
        df = pd.DataFrame(data, columns=column_names)
        return df

    async def get_accident_data(self,
                                _id: str = None, start_date_str: str = None,
                                end_date_str: str = None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = sql_config.accident_3month_query(start_date_str, end_date_str, _id)
        sql = sql.replace("\n", "")
        # sql = f"""
        #     SELECT a.longitude,a.latitude,a.detail,b.route_id,b.organ_id
        #      FROM
        #      (select longitude,latitude,detail,obuid from canbus.ods_jituan_accident) a
        #         GLOBAL inner JOIN
        #         (select obuid,route_id,organ_id from canbus.ods_jituan_bs_bus) b
        #         ON a.obuid = b.obuid
        #     """
        column_names, data = await manager.execute_query_and_export(sql)
        df = pd.DataFrame(data, columns=column_names)
        return df

    # async def get_route_quota_name3_datas_calu(
    #         self,
    #         _id: str = None,_start_time: str = None,
    # ) -> dict | None:
    #     manager = ClickHouseManage(self.db, "")
    #     strwhere = ""
    #     if _start_time is not None:
    #         strwhere = f" and {_start_time} between start_time and end_time "
    #     sql = f""" select distinct '1' as quota_level, profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
    #     case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '线路画像'  and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted != '1' {strwhere})
    #     union all
    #     select distinct '2' as quota_level, quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
    #     case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '线路画像'  and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted != '1' {strwhere})
    #     union all
    #     select distinct '3' as quota_level, quota_id2 as parent_id, quota_id3 as quota_id, quota_name3 as quota_name,
    #     case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight_rate, start_time from ai_security.obs_quota_weight_configuration
    #     where profile_type = '线路画像'  and
    #     start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted != '1' {strwhere}) """
    #     datas = await manager.get_data_sql_dict(sql)
    #     return datas

    async def get_black_points_prediction(
            self,
            _id: str = None, start_time_str: str = None, end_time_str: str = None, _black_type: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"""
                SELECT id,longitude, latitude, report_type, route_id,accept_statu,now_size 
                FROM ai_security.abs_black_spot_prediction 
                where 1=1  
                """
        # WHERE calculate_date between '{start_time_str}' and '{end_time_str}'
        if start_time_str is not None and start_time_str != '' and end_time_str is not None and end_time_str != '':
            sql = sql + f""" and calculate_date between '{start_time_str}' and '{end_time_str}' """
        if _id is not None and _id != '':
            sql = sql + f""" and accept_statu='{_id}' """
        if _black_type is not None:
            sql = sql + f""" and black_type='{_black_type}' """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def save(self, main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_route_profile_main",
                "list": main_datas
            },
            {
                "table": "abs_route_quota_score_sub",
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
                if m_size > 0:
                    await manager.delete_data_by_ppartition(table, datas[0]['ppartition'])
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("线路画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("线路画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"线路画像保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def save_weights(self, weights_datas):
        insert_operations = [
            {
                "table": "obs_quota_weight_configuration",
                "list": weights_datas
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
                result = await manager.execute_query(
                    f"ALTER TABLE {table} DELETE where profile_type='线路画像' and start_time='{datas[0]['start_time']}'")
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("线路画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("线路画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"线路画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def get_route_report(self,_start_time,reccount) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        if reccount==0:
            reccount=300
        sql =f"""
            select id,route_id,route_name,ppartition from ai_security.abs_route_profile_main where ppartition='{_start_time}' and suggested_content='' order by score desc limit {reccount}
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def update_black_points(self, new_all_acc_black_df) -> dict | None:
        result={}
        manager = ClickHouseManage(self.db, "abs_black_spot_prediction")
        for data in new_all_acc_black_df:
            query = f"ALTER TABLE abs_black_spot_prediction UPDATE old_size={data['old_size']},now_size={data['now_size']} WHERE id = '{data['id']}'"
            result = await manager.execute_query(query)
        return result

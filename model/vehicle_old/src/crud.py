# import json
# import time
# import uuid
# from datetime import datetime, timedelta
# from typing import List, Dict
#
# import numpy as np
# import pandas as pd
# # @File           : crud.py
# # @IDE            : PyCharm
# # @desc           : 数据库 增删改查操作
#
#
# from clickhouse_driver import Client
#
# from core import sql_config
# from core.clickhouse_connect import connect_to_clickhouse
# from core.clickhouse_manage import ClickHouseManage
# from core.logger import logger
# from model.vehicle.src.schemas.vehicle_profile import AbsBusProfileMain, AbsBusQuotaScoreSub
# from utils.compute import Compute
# from utils.tools import get_next_month_day, get_last_month_day
#
#
# #数据库增删改查
# class Vehicle(ClickHouseManage):
#
#     def __init__(self, db: Client):
#         super(Vehicle, self).__init__(db, "", "","")
#
#     async def get_risk_value(self,score)-> str | None:
#         manager = ClickHouseManage(self.db, "")
#         sql=sql_config.get_risk_value()
#         datas = await manager.get_data_sql_dict(sql)
#         for data in datas:
#             parts=data['item_value'].strip().split('-')
#             result = [int(part) for part in parts]
#             min_val, max_val = result
#             is_in_range = min_val <= score < max_val
#             if is_in_range:
#                 return data['item_text']
#         return ""
#
#     async def get_quota_name3_datas(
#             self,
#             _id: str = None,task_type:str = None,_start_time:str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         sqlwhere=''
#         if task_type:
#             if task_type == 'energy':
#                 sqlwhere = f""" and quota_name1='能耗风险'"""
#             if task_type == 'fault':
#                 sqlwhere = f""" and quota_name1='故障风险'"""
#         strwhere = ""
#         if _start_time is not None:
#             strwhere = f" and '{_start_time}' between start_time and end_time "
#         sql = f"""select * from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1'
#                 and start_time in (select max(start_time) from ai_security.obs_quota_weight_configuration
#                 where profile_type='车辆画像' and deleted!='1' {strwhere}) {sqlwhere}"""
#
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#
#     async def get_ods_jituan_bs_bus(self):
#         manager = ClickHouseManage(self.db, "")
#         sql = f" select bus_id,number_plate as bus_name,organ_id,org_name from  canbus.ods_jituan_bs_bus "
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_bus_quota1( self,
#             _id: str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         sql = f"select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'"
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_bus_quota2( self,
#             _id: str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         sql = f"select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'"
#         if _id is not None and _id!='':
#             sql=sql+f" and quota_name1 = '{_id}'"
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_bus_quota3( self,
#             _id: str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         sql = f"select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id, quota_name3 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' "
#         if _id is not None and _id!='':
#             sql=sql+f" and quota_name1 = '{_id}'"
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_abs_bus_profile_main( self,
#             _id: str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         #ppartition='{_id}' and
#         sql = f"select id,bus_id from ai_security.abs_bus_profile_main where  deleted!='1' and ppartition='{_id}'"
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_all_datas( self,_table_name:str = None,
#                              sqlwhere:str = None
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         sql=f"select * from {_table_name}"
#         if sqlwhere is not None:
#             sql=sql+f" where {sqlwhere}"
#         column_names, data = await manager.execute_query_and_export(sql)
#         df = pd.DataFrame(data, columns=column_names)
#         return df
#
#     async def get_datas_streaming(
#             self,
#             _table_name: str = None, sqlwhere: str = None,all_fields:str = None,groupby:str = None,
#     ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         if all_fields :
#             sql = f"""select {all_fields} from {_table_name}"""
#             columns = await manager.execute_query_and_column(sql + " LIMIT 0")
#         else:
#             sql = f"""select * from {_table_name}"""
#             columns = await manager.execute_query_and_column(sql + " LIMIT 0")
#             all_fields = ",".join(columns)
#             sql = f""" select {all_fields} from {_table_name} """
#         print(f"开始读取{_table_name}数据...")
#         if sqlwhere is not None:
#             sql = sql + f" where {sqlwhere}"
#         start_time = time.time()
#         # print(f"{sql}")
#         df = await manager.optimize_and_fetch(sql, columns)
#         end_time = time.time()
#
#         if not df.empty:
#             print(f"数据读取成功!")
#             print(f"总行数: {len(df)}")
#             print(f"耗时: {end_time - start_time:.2f} 秒")
#             print(f"列数: {len(df.columns)}")
#             # print("\n数据预览:")
#             # # print(df.head())
#         else:
#             print("数据读取失败!")
#
#         return df
#
#     async def get_vehicle_quota1(self,
#                                _id: str = None,_start_time:str = None,
#                                ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         strwhere = ""
#         if _start_time is not None :
#             strwhere = f" and '{_start_time}' between start_time and end_time "
#         sql = f"""
#             select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
#             case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
#             start_time from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' and deleted!='1'  and calculate_weight_rate3<>0
#             and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1'  and calculate_weight_rate3<>0 {strwhere} ) """
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_vehicle_quota2(self,
#                                _id: str = None,_start_time:str = None,
#                                ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         strwhere = ""
#         if _start_time is not None:
#             strwhere = f" and '{_start_time}' between start_time and end_time "
#         sql = f"""
#             select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name, quota_name1 || '_' || quota_name2  as feature,
#             case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
#             case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
#             start_time from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' and deleted!='1' and calculate_weight_rate3<>0
#             and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1' and calculate_weight_rate3<>0 {strwhere}) """
#         if _id is not None and _id!='':
#             sql = sql + f" and quota_name1 = '{_id}'"
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def get_vehicle_quota3(self,
#                                model_name: str = None,_start_time:str = None,
#                                ) -> dict | None:
#         manager = ClickHouseManage(self.db, "")
#         if model_name is not None:
#             _strwhere= " and quota_name1='能耗风险' "
#         else:
#             _strwhere= ""
#         strwhere = ""
#         if _start_time is not None:
#             strwhere = f" and '{_start_time}' between start_time and end_time "
#         sql = f""" select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id,
#             quota_name1 || '_' || quota_name2 || '_' || quota_name3 as quota_name,
#             case when quota_name2='驾驶不良行为'  then quota_name1 || '_' || quota_name2 || '_' ||  quota_name3 || '_次数'
#             else quota_name1 || '_' || quota_name2 || '_' ||  quota_name3 end as feature,
#             quota_name3 as feature_name,
#             case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
#             case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
#             case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight,
#             case when weight_rate3 = 0 then calculate_weight_rate3 else weight_rate3 end as weight_rate3,
#             start_time  from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'  and deleted!='1' and calculate_weight_rate3<>0 {_strwhere}
#             and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1' and calculate_weight_rate3<>0 {_strwhere} {strwhere}) """
#         datas = await manager.get_data_sql_dict(sql)
#         return datas
#
#     async def save(self,main_datas, score_datas):
#         insert_operations = [
#             {
#                 "table": "abs_bus_profile_main",
#                 "list": main_datas
#             },
#             {
#                 "table": "abs_bus_quota_score_sub",
#                 "list": score_datas,
#             }
#         ]
#         manager = ClickHouseManage(self.db, "")
#
#         try:
#             # 开启事务
#             await manager.begin_transaction()
#
#             # 执行所有插入操作
#             all_success = True
#             for operation in insert_operations:
#                 table = operation["table"]
#                 datas = operation["list"]
#                 m_size = len(datas)
#                 if m_size > 100000:
#                     m_size = 100000
#                 if m_size >0:
#                     await manager.delete_data_by_ppartition(table, datas[0]['ppartition'])
#                     success = await manager.batch_insert(table, datas, batch_size=m_size)
#                     if not success:
#                         all_success = False
#                         break
#
#             # 根据结果提交或回滚
#             if all_success:
#                 await manager.commit_transaction()
#                 logger.info("车辆画像 所有表保存成功")
#                 return True
#             else:
#                 await manager.rollback_transaction()
#                 logger.error("车辆画像 部分保存失败，已回滚")
#                 return False
#
#         except Exception as e:
#             logger.error(f"车辆画像保存 异常: {e}")
#             await manager.rollback_transaction()
#             return False
#
#     async def save_weights(self, weights_datas):
#         insert_operations = [
#             {
#                 "table": "obs_quota_weight_configuration",
#                 "list": weights_datas
#             }
#         ]
#         manager = ClickHouseManage(self.db, "")
#
#         try:
#             # 开启事务
#             await manager.begin_transaction()
#
#             # 执行所有插入操作
#             all_success = True
#             for operation in insert_operations:
#                 table = operation["table"]
#                 datas = operation["list"]
#                 m_size = len(datas)
#                 if m_size > 100000:
#                     m_size = 100000
#                 sql=f"delete from {table} where profile_type='车辆画像' and start_time='{datas[0]['start_time']}'"
#                 result=await manager.execute_query(sql)
#                 success = await manager.batch_insert(table, datas, batch_size=m_size)
#                 if not success:
#                     all_success = False
#                     break
#
#             # 根据结果提交或回滚
#             if all_success:
#                 await manager.commit_transaction()
#                 logger.info("车辆画像权重 所有表保存成功")
#                 return True
#             else:
#                 await manager.rollback_transaction()
#                 logger.error("车辆画像权重 部分保存失败，已回滚")
#                 return False
#
#         except Exception as e:
#             logger.error(f"车辆画像权重保存 异常: {e}")
#             await manager.rollback_transaction()
#             return False
#
#
# async def read_raw_db(tablename,sqlwhere=None,all_fields=None,groupby=None):
#     try:
#         async with await connect_to_clickhouse() as client:
#             df = await Vehicle(client).get_datas_streaming(tablename,sqlwhere,all_fields,groupby)
#             return df
#     except Exception as e:
#         print(f"车辆画像取数执行出错: {e}")
#     print("数据库连接已关闭")
#
# async def read_raw_streaming(tablename,sqlwhere=None):
#     try:
#         async with await connect_to_clickhouse() as client:
#             df = await Vehicle(client).get_all_datas(tablename, sqlwhere)
#             return df
#     except Exception as e:
#         print(f"车辆画像取数执行出错: {e}")
#     print("数据库连接已关闭")
#
# async def read_raw_sql(query):
#     try:
#         async with await connect_to_clickhouse() as client:
#             column_names, data = await Vehicle(client).execute_query_and_export(query)
#             df = pd.DataFrame(data, columns=column_names)
#             return df
#     except Exception as e:
#         print(f"车辆画像取数执行出错: {e}")
#     print("数据库连接已关闭")
#
# async def save_weights_dict(start_date:str,end_date:str,local_weight_dict:List[Dict]):
#     # 使用异步上下文管理器方式
#     try:
#         async with await connect_to_clickhouse() as client:
#             start_date_=datetime.strptime(start_date,"%Y-%m-%d")
#             start_date_ = get_next_month_day(start_date_)
#             quota_name3_datas = await Vehicle(client).get_quota_name3_datas('','',start_date)
#             end_date_ = get_next_month_day(start_date_)-timedelta(days=1)
#             end_date_str = end_date_.strftime('%Y%m%d')
#             unit = "次数"
#             feature_names=[]
#             for n in local_weight_dict:
#                 feature_names.append(n['quota_id'])
#             for x in quota_name3_datas:
#                 quota_name = x['quota_id3']
#                 if quota_name in feature_names:
#                     n=feature_names.index(quota_name)
#                     x['id'] = str(uuid.uuid4())
#                     x['calculate_weight_rate1'] = local_weight_dict[n]["weight_rate1"]
#                     x['calculate_weight_rate2'] = local_weight_dict[n]["weight_rate2"]
#                     x['calculate_weight_rate3'] = local_weight_dict[n]["weight_rate3"]
#                     x['start_time'] = start_date_
#                     x['end_time'] = end_date_
#                     x['creator'] = "system"
#                     x['create_time'] = datetime.now()
#                     x['updater'] = "system"
#                     x['update_time'] = datetime.now()
#                 else:
#                     x['id'] = str(uuid.uuid4())
#                     x['calculate_weight_rate1'] = 0
#                     x['calculate_weight_rate2'] = 0
#                     x['calculate_weight_rate3'] = 0
#                     x['start_time'] = start_date_
#                     x['end_time'] = end_date_
#                     x['creator'] = "system"
#                     x['create_time'] = datetime.now()
#                     x['updater'] = "system"
#                     x['update_time'] = datetime.now()
#                     # 保存权重
#             await Vehicle(client).save_weights(quota_name3_datas)
#
#     except Exception as e:
#         logger.error("车辆画像-保存车辆权重执行出错", exc_info=True)
#         print(f"车辆画像-保存车辆权重执行出错: {e}")
#     print("数据库连接已关闭")
#
# async def save_scores(result, start_time, end_time):
#     # 使用异步上下文管理器方式
#     try:
#         async with (await connect_to_clickhouse() as client):
#             quota1_datas = await Vehicle(client).get_vehicle_quota1(None,start_time)
#             quota2_datas = await Vehicle(client).get_vehicle_quota2(None,start_time)
#             quota3_datas = await Vehicle(client).get_vehicle_quota3(None,start_time)
#             # 解析开始日期
#             start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
#             end_date_ = datetime.strptime(end_time, '%Y-%m-%d')
#             end_date_str = end_date_.strftime('%Y%m%d')
#             main_datas = []
#             quota_scores = []
#             profile_main = None
#             feature_names = []
#             for i,score in result['risk_df'].iterrows():
#                 # if score['车牌号']!='粤A33390D':
#                 #     continue
#                 main_id = str(uuid.uuid4())
#                 _evalutaion_type = await Vehicle(client).get_risk_value(round(score['总分']))
#                 # bus_names=['粤A04210D','粤A09148D','粤A27644D']
#                 # if score['车牌号'] in bus_names:
#                 #     print(_evalutaion_type)
#                 profile_main = AbsBusProfileMain(
#                     ppartition=end_date_str,
#                     id=main_id,
#                     bus_id=str(score['车辆自编号ID']),
#                     bus_name=score['车牌号'],
#                     organ_id=str(score['公司id']),
#                     organ_name=score['公司名称'],
#                     calculate_date=end_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
#                     evalutaion_type=_evalutaion_type,
#                     score=round(score['总分'],2),
#                     suggested_content="",
#                     creator="system",
#                     create_time=datetime.now(),
#                     updater="system",
#                     update_time=datetime.now(),
#                     deleted="0"
#                 )
#                 for m in quota1_datas:
#                     weight_rate1 = round(float(m['weight_rate1'] / 100),2)
#                     field_name = m['quota_name'].replace("故障风险", "车辆故障模型")
#                     field_name = field_name.replace("能耗风险", "车辆能耗模型")
#                     # _score=result['normalized_df'].iloc[i][field_name]
#                     # _score = result['converted_df'].iloc[i][field_name]
#                     _risk=result['original_df'].iloc[i][field_name]
#                     if round(weight_rate1, 2)==0:
#                         _score=0
#                     else :
#                         # _score= round(score[field_name]/weight_rate1, 6)
#                         _score = round(round(score[field_name], 6) / round(weight_rate1, 2), 2)
#                     quota_score_1 = AbsBusQuotaScoreSub(
#                         ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id=m['quota_id'],
#                         quota_name=m['quota_name'],
#                         score=_score,
#                         weight_rate=weight_rate1,
#                         original_value=round(score[field_name], 6),
#                         risk_data='',
#                         quota_level="1",
#                         parent_id="车辆画像",
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=end_date_,
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#                 for m in quota2_datas:
#                     weight_rate2 = round(float(m['weight_rate2'] / 100),2)
#                     weight_rate1 = round(float(m['weight_rate1'] / 100),2)
#                     field_name = m['feature'].replace("故障风险", "车辆故障模型")
#                     field_name = field_name.replace("能耗风险", "车辆能耗模型")
#                     # _score = result['normalized_df'].iloc[i][field_name]
#                     # _score = result['converted_df'].iloc[i][field_name]
#                     if round(weight_rate1 * weight_rate2,2) == 0:
#                         _score = 0
#                     else:
#                         _score=round(round(score[field_name], 6) / round(weight_rate1 * weight_rate2 , 2), 2)
#                     # if not np.isnan(result['normalized_df'].iloc[i][field_name]):
#                     #     _score = round(result['normalized_df'].iloc[i][field_name], 2)
#                     # else:
#                     #     _score = 0
#                     quota_score_1 = AbsBusQuotaScoreSub(
#                         ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id=m['quota_id'],
#                         quota_name=m['quota_name'],
#                         score=_score,
#                         weight_rate=round(weight_rate1 * weight_rate2,2),
#                         original_value=round(score[field_name], 6),
#                         risk_data="",
#                         quota_level="2",
#                         parent_id=m['parent_id'],
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=end_date_,
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#
#                 for x in quota3_datas:
#                     weight_rate3 = round(float(x['weight_rate3'] / 100),2)
#                     weight_rate2 = round(float(x['weight_rate2'] / 100),2)
#                     weight_rate1 = round(float(x['weight_rate1'] / 100),2)
#                     field_name = x['feature'].replace("故障风险", "车辆故障模型")
#                     field_name = field_name.replace("能耗风险", "车辆能耗模型")
#                     # if '维修工单数' in field_name:
#                     #     print(field_name)
#                     # _score = result['normalized_df'].iloc[i][field_name]
#                     # _score = result['converted_df'].iloc[i][field_name]
#                     # if pd.isna(_score):
#                     #     _score = 0
#                     # else:
#                     #     _score = round(_score, 6)
#                     if round(weight_rate1*weight_rate2*weight_rate3,2) == 0:
#                         _score = 0
#                     else:
#                         _score = round(round(score[field_name], 6) /round(weight_rate1*weight_rate2*weight_rate3,2), 2)
#                     _risk = result['original_df'].iloc[i][field_name]
#                     if pd.isna(_risk):
#                         _risk = 0
#                     else:
#                         _risk = round(_risk, 6)
#                     quota_score_3 = AbsBusQuotaScoreSub(
#                         ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id=x['quota_id'],
#                         quota_name=x['feature_name'],
#                         score=_score,
#                         weight_rate=round(weight_rate1*weight_rate2*weight_rate3,2),
#                         original_value=round(score[field_name], 6),
#                         risk_data=str(_risk),
#                         quota_level="3",
#                         parent_id=x['parent_id'],
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=end_date_,
#                     )
#                     quota_scores.append(quota_score_3.to_dict())
#                 if profile_main is not None:
#                     main_datas.append(profile_main.to_dict())
#             await Vehicle(client).save(main_datas, quota_scores)
#
#     except Exception as e:
#         logger.error("车辆画像主程序执行出错", exc_info=True)
#         print(f"车辆画像主程序执行出错: {e}")
#     print("数据库连接已关闭")
#
# # async def save_scores_bak(result, start_time, end_time):
# #     # 使用异步上下文管理器方式
# #     try:
# #         async with await connect_to_clickhouse() as client:
# #             quota1_datas = await Vehicle(client).get_vehicle_quota1()
# #             quota2_datas = await Vehicle(client).get_vehicle_quota2()
# #             quota3_datas = await Vehicle(client).get_vehicle_quota3()
# #             # 解析开始日期
# #             start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
# #             end_date_ = datetime.strptime(end_time, '%Y-%m-%d')
# #             end_date_str = end_date_.strftime('%Y%m%d')
# #             main_datas = []
# #             quota_scores = []
# #             profile_main = None
# #             feature_names = []
# #             for i,score in result['final_contrib_df'].iterrows():
# #                 # if i>0:
# #                 #     continue
# #                 main_id = str(uuid.uuid4())
# #                 _evalutaion_type = await Vehicle(client).get_risk_value(score['总分'])
# #                 profile_main = AbsBusProfileMain(
# #                     ppartition=end_date_str,
# #                     id=main_id,
# #                     bus_id=str(score['obuid']),
# #                     bus_name=score['车牌号'],
# #                     organ_id=str(score['公司id']),
# #                     organ_name=score['公司名称'],
# #                     calculate_date=end_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
# #                     evalutaion_type=_evalutaion_type,
# #                     score=round(score['总分']),
# #                     suggested_content="",
# #                     creator="system",
# #                     create_time=datetime.now(),
# #                     updater="system",
# #                     update_time=datetime.now(),
# #                     deleted="0"
# #                 )
# #                 for field in score.index:
# #                     if '模型' in field:
# #                         # print(field)
# #                         if not np.isnan(result['normalized_df'].iloc[i][field]):
# #                             _score = round(result['normalized_df'].iloc[i][field], 2)
# #                         else:
# #                             _score = 0
# #                         if not np.isnan(result['original_df'].iloc[i][field]):
# #                             _risk = round(result['original_df'].iloc[i][field], 2)
# #                         else:
# #                             _risk = 0
# #                         # weight_rate1 = float(m['weight_rate1'] / 100)
# #                         quota_id = field.replace("车辆故障模型", "故障风险")
# #                         quota_id = quota_id.replace("车辆能耗模型", "能耗风险")
# #                         quota_id = quota_id.replace("_次数", "")
# #                         quota_id = quota_id.replace("_", "-")
# #                         quota_name = quota_id
# #                         parent_id='车辆画像'
# #                         quota_level='1'
# #                         if quota_id.count('-')==1:
# #                             quota_level='2'
# #                             first_underscore = quota_id.find('_')
# #                             quota_name = quota_id[first_underscore + 1:]
# #                             parent_id =  quota_id[:first_underscore]
# #                         if quota_id.count('-')==2:
# #                             quota_level='3'
# #                             first_underscore = quota_id.find('_')
# #                             second_underscore = quota_id.find('_', first_underscore + 1)
# #                             quota_name = quota_id[second_underscore + 1:]
# #                             parent_id = quota_id[:second_underscore]
# #                         quota_score_1 = AbsBusQuotaScoreSub(
# #                             ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
# #                             id=str(uuid.uuid4()),
# #                             main_id=main_id,
# #                             quota_id='车辆画像'+'-'+quota_id,
# #                             quota_name=quota_name,
# #                             score=_score,
# #                             weight_rate=0,
# #                             original_value=round(score[field], 2),
# #                             risk_data=str(_risk),
# #                             quota_level=quota_level,
# #                             parent_id=parent_id,
# #                             creator="system",
# #                             create_time=datetime.now(),
# #                             updater="system",
# #                             update_time=datetime.now(),
# #                             deleted="0",
# #                             start_time=start_date_,
# #                             end_time=end_date_,
# #                         )
# #                         quota_scores.append(quota_score_1.to_dict())
# #                 # for m in quota2_datas:
# #                 #     weight_rate2 = float(m['weight_rate2'] / 100)
# #                 #     weight_rate1 = float(m['weight_rate1'] / 100)
# #                 #     field_name = m['feature'].replace("故障风险", "车辆故障模型")
# #                 #     field_name = field_name.replace("能耗风险", "车辆能耗模型")
# #                 #     if not np.isnan(result['normalized_df'].iloc[i][field_name]):
# #                 #         _score = round(result['normalized_df'].iloc[i][field_name], 2)
# #                 #     else:
# #                 #         _score = 0
# #                 #     quota_score_1 = AbsBusQuotaScoreSub(
# #                 #         ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
# #                 #         id=str(uuid.uuid4()),
# #                 #         main_id=main_id,
# #                 #         quota_id=m['quota_id'],
# #                 #         quota_name=m['quota_name'],
# #                 #         score=_score,
# #                 #         weight_rate=weight_rate1 * weight_rate2,
# #                 #         original_value=round(score[field_name], 2),
# #                 #         risk_data="",
# #                 #         quota_level="2",
# #                 #         parent_id=m['parent_id'],
# #                 #         creator="system",
# #                 #         create_time=datetime.now(),
# #                 #         updater="system",
# #                 #         update_time=datetime.now(),
# #                 #         deleted="0",
# #                 #         start_time=start_date_,
# #                 #         end_time=end_date_,
# #                 #     )
# #                 #     quota_scores.append(quota_score_1.to_dict())
# #                 #
# #                 # for x in quota3_datas:
# #                 #     weight_rate3 = float(x['weight_rate3'] / 100)
# #                 #     weight_rate2 = float(x['weight_rate2'] / 100)
# #                 #     weight_rate1 = float(x['weight_rate1'] / 100)
# #                 #     field_name = x['feature'].replace("故障风险", "车辆故障模型")
# #                 #     field_name = field_name.replace("能耗风险", "车辆能耗模型")
# #                 #     if not np.isnan(result['normalized_df'].iloc[i][field_name]):
# #                 #         _score = round(result['normalized_df'].iloc[i][field_name], 2)
# #                 #     else:
# #                 #         _score = 0
# #                 #     if not np.isnan(result['original_df'].iloc[i][field_name]):
# #                 #         _risk = round(result['original_df'].iloc[i][field_name], 2)
# #                 #     else:
# #                 #         _risk = 0
# #                 #     quota_score_3 = AbsBusQuotaScoreSub(
# #                 #         ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
# #                 #         id=str(uuid.uuid4()),
# #                 #         main_id=main_id,
# #                 #         quota_id=x['quota_id'],
# #                 #         quota_name=x['feature_name'],
# #                 #         score=_score,
# #                 #         weight_rate=weight_rate1*weight_rate2*weight_rate3,
# #                 #         original_value=round(score[field_name], 2),
# #                 #         risk_data=str(_risk),
# #                 #         quota_level="3",
# #                 #         parent_id=x['parent_id'],
# #                 #         creator="system",
# #                 #         create_time=datetime.now(),
# #                 #         updater="system",
# #                 #         update_time=datetime.now(),
# #                 #         deleted="0",
# #                 #         start_time=start_date_,
# #                 #         end_time=end_date_,
# #                 #     )
# #                 #     quota_scores.append(quota_score_3.to_dict())
# #                 if profile_main is not None:
# #                     main_datas.append(profile_main.to_dict())
# #             await Vehicle(client).save(main_datas, quota_scores)
# #
# #     except Exception as e:
# #         logger.error("车辆画像主程序执行出错", exc_info=True)
# #         print(f"车辆画像主程序执行出错: {e}")
# #     print("数据库连接已关闭")
#
# async def get_weights(start_date:str):
#     try:
#         async with await connect_to_clickhouse() as client:
#             quota3_datas = await Vehicle(client).get_vehicle_quota3(None,start_date)
#             return quota3_datas
#     except Exception as e:
#         logger.error("车辆画像主程序执行出错", exc_info=True)
#         print(f"车辆画像主程序执行出错: {e}")
#         return None
#     print("数据库连接已关闭")
#
#
#

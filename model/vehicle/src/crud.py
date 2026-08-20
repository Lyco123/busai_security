import json
import math
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict

import numpy as np
import pandas as pd
# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger
from model.vehicle.src.schemas.vehicle_profile import AbsBusProfileMain, AbsBusQuotaScoreSub
from utils.compute import Compute
from utils.tools import get_next_month_day, get_last_month_day


#数据库增删改查
class Vehicle(ClickHouseManage):

    def __init__(self, db: Client):
        super(Vehicle, self).__init__(db, "", "","")

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

    async def get_quota_name3_datas(
            self,
            _id: str = None,task_type:str = None,_start_time:str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sqlwhere=''
        if task_type:
            if task_type == 'energy':
                sqlwhere = f""" and quota_name1='能耗风险'"""
            if task_type == 'fault':
                sqlwhere = f""" and quota_name1='故障风险'"""
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""select * from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1'
                and start_time in (select max(start_time) from ai_security.obs_quota_weight_configuration 
                where profile_type='车辆画像' and deleted!='1' {strwhere}) {sqlwhere}"""

        datas = await manager.get_data_sql_dict(sql)
        return datas


    async def get_ods_jituan_bs_bus(self):
        manager = ClickHouseManage(self.db, "")
        sql = f" select bus_id,number_plate as bus_name,organ_id,org_name from  canbus.ods_jituan_bs_bus "
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_quota1( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_quota2( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'"
        if _id is not None and _id!='':
            sql=sql+f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_quota3( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f"select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id, quota_name3 as quota_name from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' "
        if _id is not None and _id!='':
            sql=sql+f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_bus_profile_main( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,bus_id from ai_security.abs_bus_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_all_datas( self,_table_name:str = None,
                             sqlwhere:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql=f"select * from {_table_name}"
        if sqlwhere is not None:
            sql=sql+f" where {sqlwhere}"
        column_names, data = await manager.execute_query_and_export(sql)
        df = pd.DataFrame(data, columns=column_names)
        return df

    async def get_datas_streaming(
            self,
            _table_name: str = None, sqlwhere: str = None,all_fields:str = None,groupby:str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if all_fields :
            sql = f"""select {all_fields} from {_table_name}"""
            columns = await manager.execute_query_and_column(sql + " LIMIT 0")
        else:
            sql = f"""select * from {_table_name}"""
            columns = await manager.execute_query_and_column(sql + " LIMIT 0")
            all_fields = ",".join(columns)
            sql = f""" select {all_fields} from {_table_name} """
        print(f"开始读取{_table_name}数据...")
        if sqlwhere is not None and sqlwhere!='':
            sql = sql + f" where {sqlwhere}"
        start_time = time.time()
        # print(f"{sql}")
        df = await manager.optimize_and_fetch(sql, columns)
        end_time = time.time()

        if not df.empty:
            print(f"数据读取成功!")
            print(f"总行数: {len(df)}")
            print(f"耗时: {end_time - start_time:.2f} 秒")
            print(f"列数: {len(df.columns)}")
            # print("\n数据预览:")
            # # print(df.head())
        else:
            print("数据读取失败!")

        return df

    async def get_vehicle_quota1(self,
                               _id: str = None,_start_time:str = None,
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None :
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name, 
            case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
            start_time from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' and deleted!='1'  and calculate_weight_rate3<>0 
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1'  and calculate_weight_rate3<>0 {strwhere} ) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_vehicle_quota2(self,
                               _id: str = None,_start_time:str = None,
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f"""
            select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name, quota_name1 || '_' || quota_name2  as feature,
            case when weight_rate1 = 0 then calculate_weight_rate1 else weight_rate1 end as weight_rate1,
            case when weight_rate2 = 0 then calculate_weight_rate2 else weight_rate2 end as weight_rate2,
            start_time from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像' and deleted!='1' and calculate_weight_rate3<>0 
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1' and calculate_weight_rate3<>0 {strwhere}) """
        if _id is not None and _id!='':
            sql = sql + f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_vehicle_quota3(self,
                               model_name: str = None,_start_time:str = None,
                               ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if model_name is not None:
            _strwhere= " and quota_name1='能耗风险' "
        else:
            _strwhere= ""
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id,  
            quota_name1 || '_' || quota_name2 || '_' || quota_name3 as quota_name,
            case when quota_name2='驾驶不良行为'  then quota_name1 || '_' || quota_name2 || '_' ||  quota_name3 || '_千公里次数'
            else quota_name1 || '_' || quota_name2 || '_' ||  quota_name3 end as feature,
            quota_name3 as feature_name,
            case when weight_rate1 = 0 then toFloat64OrNull(toString(calculate_weight_rate1)) else toFloat64OrNull(toString(weight_rate1)) end  as weight_rate1,
            case when weight_rate2 = 0 then toFloat64OrNull(toString(calculate_weight_rate2)) else toFloat64OrNull(toString(weight_rate2)) end  as weight_rate2,
            case when weight_rate3 = 0 then toFloat64OrNull(toString(calculate_weight_rate3)) else toFloat64OrNull(toString(weight_rate3)) end  as weight,
            case when weight_rate3 = 0 then toFloat64OrNull(toString(calculate_weight_rate3)) else toFloat64OrNull(toString(weight_rate3)) end  as weight_rate3,
            start_time  from ai_security.obs_quota_weight_configuration where profile_type = '车辆画像'  and deleted!='1' {_strwhere}
            and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type='车辆画像' and deleted!='1' {_strwhere} {strwhere}) """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def save(self,main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_bus_profile_main",
                "list": main_datas
            },
            {
                "table": "abs_bus_quota_score_sub",
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
                    await manager.delete_data_by_ppartition(table, datas[0]['ppartition'])
                    success = await manager.batch_insert(table, datas, batch_size=m_size)
                    if not success:
                        all_success = False
                        break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("车辆画像 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("车辆画像 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"车辆画像保存 异常: {e}")
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
                # sql=f"delete from {table} where profile_type='车辆画像' and start_time='{datas[0]['start_time']}'"

                sql = f"ALTER TABLE {table} DELETE WHERE profile_type = '车辆画像' AND start_time = '{datas[0]['start_time']}'"

                result=await manager.execute_query(sql)
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("车辆画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("车辆画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"车辆画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def gen_tmp_table(
            self,
            table_name:str = None,sql:str = None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, table_name)
        result=await manager.delete_all_data()
        datas = await manager.get_data_sql_dict(sql)
        if datas is not None and len(datas) > 0:
            m_size = len(datas)
            if m_size > 100000:
                m_size = 100000
            if m_size > 0:
                success = await manager.batch_insert(table_name, datas, batch_size=m_size)
        return datas

    async def get_vehicle_report(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        sql =f"""
            select bus_id,bus_name,ppartition from ai_security.abs_bus_profile_main where ppartition='{_start_time}' order by score desc limit 2 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas


async def read_raw_db(tablename,sqlwhere=None,all_fields=None,groupby=None):
    try:
        async with await connect_to_clickhouse() as client:
            df = await Vehicle(client).get_datas_streaming(tablename,sqlwhere,all_fields,groupby)
            return df
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")

async def read_raw_streaming(tablename,sqlwhere=None):
    try:
        async with await connect_to_clickhouse() as client:
            df = await Vehicle(client).get_all_datas(tablename, sqlwhere)
            return df
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")

async def read_raw_sql(query):
    try:
        async with await connect_to_clickhouse() as client:
            column_names, data = await Vehicle(client).execute_query_and_export(query)
            df = pd.DataFrame(data, columns=column_names)
            return df
    except Exception as e:
        print(f"车辆画像取数执行出错: {e}")
    print("数据库连接已关闭")

async def save_weights_dict(start_date:str,end_date:str,local_weight_dict:List[Dict]):
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:
            start_date_=datetime.strptime(start_date,"%Y-%m-%d")
            start_date_ = get_next_month_day(start_date_)
            quota_name3_datas = await Vehicle(client).get_quota_name3_datas('','',start_date)
            end_date_ = get_next_month_day(start_date_)-timedelta(days=1)
            end_date_str = end_date_.strftime('%Y%m%d')
            unit = "次数"
            feature_names=[]
            for n in quota_name3_datas:
                feature_names.append(n['quota_id3'])
            quota=[]
            for x in local_weight_dict:
                # '车辆画像-能耗风险-车辆属性-车辆品牌'
                dict={}
                if x['模型名称']=='车辆能耗模型':
                    quota_id1 = '车辆画像-能耗风险'
                    quota_name1='能耗风险'
                if x['模型名称']=='车辆故障模型':
                    quota_id1 = '车辆画像-故障风险'
                    quota_name1='故障风险'
                quota_id2=quota_id1+'-'+x['二级指标']
                quota_name2=x['二级指标']
                map=sql_config.vr_weight_lable_dict()
                parts=x['三级指标'].split('_')
                if (quota_name1+'_'+x['三级指标']) in map:
                    mparts=map[quota_name1+'_'+x['三级指标']].split('-')
                    quota_id3='车辆画像-'+map[quota_name1+'_'+x['三级指标']]
                    quota_name3 = mparts[2]
                else:
                    quota_id3 = quota_id1.replace('_', '-') + '-' + parts[0]+'-'+parts[1]
                    quota_name3=parts[1]
                if len(parts)>2:
                    quoa_unit3=parts[2]
                else:
                    quoa_unit3=''
                if quota_id3 in feature_names:
                    n=feature_names.index(quota_id3)
                    dict=quota_name3_datas[n]
                else:
                    dict={}
                    dict['quota_id1']=quota_id1
                    dict['quota_name1']=quota_name1
                    dict['weight_rate1']='0'
                    dict['quoa_desc1'] = ''
                    dict['quoa_unit1'] = ''
                    dict['quota_id2'] = quota_id2
                    dict['quota_name2'] = quota_name2
                    dict['weight_rate2'] = '0'
                    dict['quoa_desc2'] = ''
                    dict['quoa_unit2'] = ''
                    dict['quota_id3'] = quota_id3
                    dict['quota_name3'] = quota_name3
                    dict['weight_rate3'] = '0'
                    dict['quoa_desc3'] = ''
                    dict['quoa_unit3'] = quoa_unit3
                    dict['quota_id4'] = quota_id3+'-'
                    dict['quota_name4'] = '-'
                    dict['calculate_weight_rate4'] = '0'
                    dict['weight_rate4'] = '0'
                    dict['quoa_desc4'] = ''
                    dict['quoa_unit4'] = ''
                    dict['profile_type'] = '车辆画像'
                dict['id'] = str(uuid.uuid4())
                dict['calculate_weight_rate1'] = x["一级权重"]
                dict['calculate_weight_rate2'] = x["二级局部权重"]
                dict['calculate_weight_rate3'] = x["三级局部权重"]
                dict['start_time'] = start_date_
                dict['end_time'] = end_date_
                dict['creator'] = "system"
                dict['create_time'] = datetime.now()
                dict['updater'] = "system"
                dict['update_time'] = datetime.now()
                dict['deleted'] = '0'
                quota.append(dict)
                    # 保存权重
            await Vehicle(client).save_weights(quota)

    except Exception as e:
        logger.error("车辆画像-保存车辆权重执行出错", exc_info=True)
        print(f"车辆画像-保存车辆权重执行出错: {e}")
    print("数据库连接已关闭")

async def save_scores(result, start_time, end_time):
    # 使用异步上下文管理器方式
    try:
        async with (await connect_to_clickhouse() as client):
            quota1_datas = await Vehicle(client).get_vehicle_quota1(None,start_time)
            quota2_datas = await Vehicle(client).get_vehicle_quota2(None,start_time)
            quota3_datas = await Vehicle(client).get_vehicle_quota3(None,start_time)
            # 解析开始日期
            start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
            end_date_ = datetime.strptime(end_time, '%Y-%m-%d')
            end_date_str = end_date_.strftime('%Y%m%d')
            main_datas = []
            quota_scores = []
            profile_main = None
            feature_names = []
            original_dict = sql_config.vr_weight_lable_dict()
            reverse_dict = {v: k for k, v in original_dict.items()}

            for i,score in result['summary_scores'].iterrows():
                # if score['车牌号']!='粤A00014D':
                #     continue
                main_id = str(uuid.uuid4())
                if pd.isna(score['综合画像分']):
                    _score=0
                else:
                    _score=round(score['综合画像分'],2)
                _evalutaion_type = await Vehicle(client).get_risk_value(_score)
                profile_main = AbsBusProfileMain(
                    ppartition=end_date_str,
                    id=main_id,
                    bus_id=str(score['车辆ID']),
                    bus_name=score['车牌号'],
                    organ_id=str(score['公司ID']),
                    organ_name=score['公司名称'],
                    calculate_date=end_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
                    evalutaion_type=_evalutaion_type,
                    score=_score,
                    suggested_content="",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0"
                )
                for m in quota1_datas:
                    weight_rate1 = round(float(m['weight_rate1'] / 100),4)
                    field_name = m['quota_name'].replace("故障风险", "故障分")
                    field_name = field_name.replace("能耗风险", "能耗分")
                    # _risk=result['original_values'].iloc[i][field_name]
                    if pd.isna(score[field_name]):
                        _original_value = 0
                    else:
                        _original_value = round(score[field_name], 6)*round(weight_rate1, 4)
                        if round(weight_rate1, 2)==0:
                            _score=0
                        else:
                            _score = round(_original_value / round(weight_rate1, 4), 4)
                    quota_score_1 = AbsBusQuotaScoreSub(
                        ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id=m['quota_id'],
                        quota_name=m['quota_name'],
                        score=_score,
                        weight_rate=weight_rate1,
                        original_value=_original_value,
                        risk_data='',
                        quota_level="1",
                        parent_id="车辆画像",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=end_date_,
                    )
                    quota_scores.append(quota_score_1.to_dict())
                quota3_datas_scores=[]
                for x in quota3_datas:
                    weight_rate3 = round(float(x['weight_rate3'] / 100),4)
                    weight_rate2 = round(float(x['weight_rate2'] / 100),4)
                    weight_rate1 = round(float(x['weight_rate1'] / 100),4)
                    if x['quota_name'].replace("_","-") in reverse_dict:
                        field_name = reverse_dict[x['quota_name'].replace("_","-")]
                    else:
                        field_name = x['feature']

                    _risk = result['original_values'].iloc[i][field_name]
                    if pd.isna(_risk):
                        _risk = 0
                    else:
                        if isinstance(_risk, (int, float)):
                            _risk = round(_risk, 6)
                    _original_value=result['contribution_values'].iloc[i][field_name]
                    if pd.isna(_original_value):
                        _original_value = 0
                    else:
                        _original_value = round(_original_value, 6)*round(weight_rate1, 4)
                    if round(weight_rate1*weight_rate2*weight_rate3,4) == 0:
                        _score = 0
                    else:
                        if pd.isna(result['contribution_values'].iloc[i][field_name]):
                            _score = 0
                        else:
                            _score = round(_original_value / round(weight_rate1*weight_rate2*weight_rate3,4), 4)

                    quota_score_3 = AbsBusQuotaScoreSub(
                        ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id=x['quota_id'],
                        quota_name=x['feature_name'],
                        score=_score,
                        weight_rate=round(weight_rate1*weight_rate2*weight_rate3,4),
                        original_value=_original_value,
                        risk_data=str(_risk),
                        quota_level="3",
                        parent_id=x['parent_id'],
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=end_date_,
                    )
                    quota3_datas_scores.append(quota_score_3.to_dict())
                    quota_scores.append(quota_score_3.to_dict())

                if quota3_datas_scores:
                    df = pd.DataFrame(quota3_datas_scores)
                    agg_rules = {
                        'original_value': 'sum'
                    }
                    grouped_df = df.groupby("parent_id").agg(agg_rules).reset_index()
                    name_=[]
                    for j,g_df in grouped_df.iterrows():
                        name_.append(g_df['parent_id'])
                    for m in quota2_datas:
                        weight_rate2 = round(float(m['weight_rate2'] / 100), 4)
                        weight_rate1 = round(float(m['weight_rate1'] / 100), 4)
                        field_name = m['quota_id']
                        if field_name in name_:
                            n=name_.index(field_name)
                            original_value=round(grouped_df.iloc[n]['original_value'],6)
                            if round(weight_rate1 * weight_rate2, 4) == 0:
                                _score = 0
                            else:
                                _score = round(round(original_value, 6) / round(weight_rate1 * weight_rate2, 4), 4)
                        quota_score_1 = AbsBusQuotaScoreSub(
                            ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=m['quota_id'],
                            quota_name=m['quota_name'],
                            score=_score,
                            weight_rate=round(weight_rate1 * weight_rate2, 4),
                            original_value=original_value,
                            risk_data="",
                            quota_level="2",
                            parent_id=m['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                if profile_main is not None:
                    main_datas.append(profile_main.to_dict())
            await Vehicle(client).save(main_datas, quota_scores)

    except Exception as e:
        logger.error("车辆画像主程序执行出错", exc_info=True)
        print(f"车辆画像主程序执行出错: {e}")
    print("数据库连接已关闭")

async def get_weights(start_date:str,xgb_weight_table:pd.DataFrame):
    try:
        async with await connect_to_clickhouse() as client:
            quota3_datas = await Vehicle(client).get_vehicle_quota3(None,start_date)
            label_map=sql_config.vr_weight_lable_dict()
            weight_map = {item['feature'].replace("_千公里次数",""): item for item in quota3_datas}
            for i,v in xgb_weight_table.iterrows():
                quota_name=None
                if v['一级指标']=='车辆能耗模型':
                    quota_name='能耗风险'+'_'+v['三级指标']
                if v['一级指标']=='车辆故障模型':
                    quota_name = '故障风险' + '_' + v['三级指标']
                if quota_name in label_map:
                    quota_name=label_map[quota_name].replace("-","_")
                if quota_name in weight_map:
                    data = weight_map[quota_name]
                    # print(f"{quota_name}:{data}")
                    xgb_weight_table.loc[i, '一级权重']=data['weight_rate1']
                    xgb_weight_table.loc[i,'二级局部权重']=data['weight_rate2']
                    xgb_weight_table.loc[i,'三级局部权重']=data['weight_rate3']
                    xgb_weight_table.loc[i, '三级全局权重_cap后'] = data['weight_rate2']*data['weight_rate3']/100

            return xgb_weight_table
    except Exception as e:
        logger.error("车辆画像主程序执行出错", exc_info=True)
        print(f"车辆画像主程序执行出错: {e}")
        return None
    print("数据库连接已关闭")

async def save_models(model, month, date,model_name):
    try:
        async with await connect_to_clickhouse() as client:
            models={}
            models['ppartition']=month
            models['id']=str(uuid.uuid4())
            models['modeles_name']=model_name
            models['calculate_month']=month
            models['calculate_date']=date
            models['json']=json.dumps(model,indent=2, ensure_ascii=False)
            models['m_type']='model'
            models['remark']=""
            models['creator']="system"
            models['create_time']=datetime.now()
            models['update_time']=datetime.now()
            models['updater']="system"
            models['deleted']="0"
            await Vehicle(client).save(models,[])
    except Exception as e:
        logger.error("车辆画像模型存储主程序执行出错", exc_info=True)
        print(f"车辆画像模型存储主程序执行出错: {e}")
        return None
    print("数据库连接已关闭")







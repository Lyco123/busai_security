import time
import uuid
from datetime import datetime, timedelta

import pandas as pd
# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger
from model.station.schemas.bus_station_profile import AbsBusStationProfileMain, AbsBusStationQuotaScoreSub
from utils.tools import get_next_month_day, get_last_month_day


#数据库增删改查
class BusStation(ClickHouseManage):

    def __init__(self, db: Client):
        super(BusStation, self).__init__(db, "", "","")


    async def get_ods_jituan_bs_bus_park(self):
        manager = ClickHouseManage(self.db, "")
        sql = f" select id,station_name,org_id,org_name from  canbus.ods_jituan_bs_bus_park "
        datas = await manager.get_data_sql_dict(sql)
        return datas


    async def get_abs_station_profile_main( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,bus_station_id,organ_id,organ_name from ai_security.abs_bus_station_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_station_quota1( self,
            _id: str = None,_start_time:str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "

        if _id is not None and _id!='':
            _strwhere=f" and quota_name1 = '{_id}'"

        sql = f""" select distinct '1' as quota_level,profile_type as parent_id, quota_id1 as quota_id, quota_name1 as quota_name,
                      case when weight_rate1 = 0 then ROUND(CAST(calculate_weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6)  else ROUND(CAST(weight_rate1 AS DECIMAL(12, 6)) / 100.0, 6)  end as weight_rate 
                      from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere}
                      and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere} and deleted != '1' {strwhere})
                    """
        if _id is not None:
            sql = sql + f" and quota_name1 = '{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_station_quota2( self,
            _id: str = None,_start_time:str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "

        if _id is not None and _id!='':
            _strwhere=f" and quota_name1 = '{_id}'"

        sql = f""" select distinct '2' as quota_level,quota_id1 as parent_id, quota_id2 as quota_id, quota_name2 as quota_name,
              case when weight_rate2 = 0 then ROUND(CAST(calculate_weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6)  else ROUND(CAST(weight_rate2 AS DECIMAL(12, 6)) / 100.0, 6)  end as weight_rate 
              from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere}
              and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere} and deleted != '1' {strwhere})
            """

        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_station_quota3( self,
            _id: str = None,_start_time:str=None
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        if _id is not None and _id!='':
            _strwhere=f" and quota_name1 = '{_id}'"
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" select distinct '3' as quota_level,quota_id2 as parent_id, quota_name2 as parent_name, quota_id3 as quota_id, quota_name3 as quota_name,
                case when weight_rate3 = 0 then ROUND(CAST(calculate_weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6)  else ROUND(CAST(weight_rate3 AS DECIMAL(12, 6)) / 100.0, 6)  end as weight_rate  
               from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere} 
               and start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type = '站场画像' {_strwhere} and deleted != '1' {strwhere} ) 
               order by quota_id2,quota_name3
            """

        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_station_all_quota( self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql = f""" 
            select * from ai_security.obs_quota_weight_configuration where profile_type in ('站场画像') and quota_name1 = '{_id}' and  
            deleted != '1' and start_time in (select max(start_time) 
            from ai_security.obs_quota_weight_configuration where profile_type in ('站场画像')  and quota_name1 = '{_id}'  and deleted != '1' {strwhere} )
                """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def read_raw_sql(self,query):
        try:
            async with await connect_to_clickhouse() as client:
                column_names, data = await BusStation(client).execute_query_and_export(query)
                df = pd.DataFrame(data, columns=column_names)
                return df
        except Exception as e:
            print(f"车辆画像取数执行出错: {e}")
        print("数据库连接已关闭")

    async def read_raw_db(self,tablename, sqlwhere=None, all_fields=None, groupby=None):
        try:
            async with await connect_to_clickhouse() as client:
                df = await BusStation(client).get_datas_streaming(tablename, sqlwhere, all_fields, groupby)
                return df
        except Exception as e:
            print(f"车辆画像取数执行出错: {e}")
        print("数据库连接已关闭")

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

    async def get_abs_bus_station_profile_main( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,bus_station_id from ai_security.abs_bus_station_profile_main where  deleted!='1' and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

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
                    f"ALTER TABLE {table} DELETE where profile_type in ('站场画像') and start_time='{datas[0]['start_time']}' and quota_name1='{datas[0]['quota_name1']}'")
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("站场画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("站场画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"驾驶员画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

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


# 保存服务态度分数
    async def save_scores_data(self,_start_time, scores_datas,_quota1_datas,_quota2_datas,_quota3_datas,station_dict):
        _start_date_ = datetime.strptime(_start_time, '%Y-%m-%d')
        _start_date = get_last_month_day(_start_date_)+timedelta(days=1)
        _end_date = _start_date_
        ppartition = _end_date.strftime('%Y%m%d')

        station_main_datas = await BusStation(self.db).get_abs_station_profile_main(ppartition)
        station_ids = []
        if station_main_datas:
            for d in station_main_datas:
                station_ids.append(d['bus_station_id'])

        main_datas = []
        quota_scores = []
        for data in scores_datas:
            # if data['所属公司']=='四分公司':
            # print(f"{data['所属公司']}")
            if data['站场id'] in station_ids:
                x = station_ids.index(data['站场id'])
                main_id = station_main_datas[x]['id']
                profile_main = None
            else:
                main_id = str(uuid.uuid4())
                profile_main = AbsBusStationProfileMain(
                    ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                    id=main_id,
                    bus_station_id=data['站场id'],
                    bus_station_name=data['站场名称'],
                    organ_id=str(data['所属公司id']),
                    organ_name=data['所属公司'],
                    calculate_date=_end_date,
                    evalutaion_type='',
                    score=0,
                    suggested_content="",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0"
                )
            for quota1 in _quota1_datas:
                weight_rate1=quota1['weight_rate']
                quota_score = AbsBusStationQuotaScoreSub(
                    ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                    id=str(uuid.uuid4()),
                    main_id=main_id,
                    quota_id=quota1['quota_id'],
                    quota_name=quota1['quota_name'],
                    score=data['站场总分'],
                    weight_rate=weight_rate1,
                    original_value=data['站场总分']*weight_rate1,
                    risk_data='',
                    quota_level=quota1['quota_level'],
                    parent_id=quota1['parent_id'],
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    start_time=_start_date,
                    end_time=_end_date,
                    )
                quota_scores.append(quota_score.to_dict())
                for quota2 in _quota2_datas:
                    weight_rate2 = quota2['weight_rate']
                    score_name2 = quota2['quota_name'] + '_原始分数'  # 换算后数值
                    g_weight_rate2 = weight_rate1*weight_rate2 # 全局权重
                    original_name2 = quota2['quota_name'] + '_全局分数'  # 全局风险值
                    risk_name2 = quota2['quota_name'] + '_风险等级'  # 风险数据值-原始值
                    if score_name2 in data:
                        # 安全型就是2，关注型就是1，危险型是0
                        m_risk_data=data[risk_name2]
                        if(data[risk_name2])!='':
                            d_risk_data=str(data[risk_name2])
                            if d_risk_data=='1.0':
                                m_risk_data='关注型'
                            if d_risk_data=='2.0':
                                m_risk_data='安全型'
                            if d_risk_data=='0.0':
                                m_risk_data='危险型'
                        quota_score = AbsBusStationQuotaScoreSub(
                            ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=quota2['quota_id'],
                            quota_name=quota2['quota_name'],
                            score=data[score_name2],
                            weight_rate=g_weight_rate2,
                            original_value=data[original_name2],
                            risk_data=m_risk_data,
                            quota_level=quota2['quota_level'],
                            parent_id=quota2['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=_start_date,
                            end_time=_end_date,
                        )
                        quota_scores.append(quota_score.to_dict())
                for quota3 in _quota3_datas:
                    weight_rate3 = quota3['quota_name']+'_全局权重'
                    score_name3 = quota3['quota_name'] + '_百分制分数'  # 换算后数值
                    original_name3 = quota3['quota_name'] + '_全局分数'  # 全局风险值
                    # risk_name3 = quota2['quota_name'] + '_风险等级'  # 风险数据值-原始值
                    risk_name3_dict = station_dict[quota3['quota_name']]
                    # print(quota3['quota_name'])
                    if score_name3 in data:
                        m_risk_data=''
                        if data[quota3['quota_name']]!=None:
                            m_risk_data = data[quota3['quota_name']]
                            if (data[quota3['quota_name']]) != '':
                                d_risk_data = str(data[quota3['quota_name']])
                                m_risk_data = risk_name3_dict[d_risk_data]
                        quota_score = AbsBusStationQuotaScoreSub(
                            ppartition=ppartition,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=quota3['quota_id'],
                            quota_name=quota3['quota_name'],
                            score=data[score_name3],
                            weight_rate=data[weight_rate3],
                            original_value=data[original_name3],
                            risk_data=m_risk_data,
                            quota_level=quota3['quota_level'],
                            parent_id=quota3['parent_id'],
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
        await BusStation(self.db).save(main_datas, quota_scores)

    async def save(self,main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_bus_station_profile_main",
                "list": main_datas
            },
            {
                "table": "abs_bus_station_quota_score_sub",
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

    async def get_station_scores(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        # sql = f"""
        #      select main_id as id,cast(sum(score*weight_rate) as int) as score from ai_security.abs_driver_quota_score_sub
        #      where ppartition='{_start_time}' and quota_level='1'  group by main_id
        # """
        sql =f"""
            WITH m_score AS (
                SELECT main_id AS id,quota_name,
                       Round(SUM(score * weight_rate),2) AS score 
                FROM ai_security.abs_bus_station_quota_score_sub 
                WHERE ppartition = '{_start_time}'
                  AND quota_level = '1' 
                GROUP BY main_id,quota_name
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
            )
            SELECT distinct
                a.ppartition as ppartition,
                a.id as id,
                a.bus_station_id as bus_station_id,
                a.bus_station_name as bus_station_name,
                a.organ_id as organ_id,
                a.organ_name as organ_name,
                a.calculate_date as calculate_date,
                c.item_text AS evalutaion_type,
                b.score as score,
                a.suggested_content as suggested_content,
                a.creator as creator,
                a.create_time as create_time,
                a.updater as updater,
                a.update_time as update_time
            FROM (select aa.*,bb.station_properties from ai_security.abs_bus_station_profile_main aa 
            GLOBAL inner join ai_security.ods_jituan_bs_bus_park bb on aa.bus_station_id=bb.id) a
            GLOBAL INNER JOIN m_score b ON a.id = b.id and b.quota_name=a.station_properties
            GLOBAL INNER JOIN m_type c ON 1 = 1  
            WHERE round(b.score) >= c.minchar AND round(b.score) <= c.maxchar;
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_station_report(self, _start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        sql = f"""
            select bus_station_id,bus_station_name,ppartition from ai_security.abs_bus_station_profile_main where ppartition='{_start_time}' order by score desc limit 2 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

async def save_station_weights_data(_start_time,station_weights,weight_type):
    try:
        start_date_ = datetime.strptime(_start_time, '%Y-%m-%d')
        end_date = get_next_month_day(start_date_)
        end_date_ = end_date - timedelta(days=1)
        async with await connect_to_clickhouse() as client:
            _list = await BusStation(client).get_bus_station_all_quota(weight_type,get_last_month_day(start_date_).strftime('%Y-%m-%d'))
            for item in _list:
                item['id'] = str(uuid.uuid4())
                item['calculate_weight_rate1'] =station_weights['quota1'][item['quota_name1']]
                item['calculate_weight_rate2'] = station_weights['quota2'][item['quota_name2']]
                quota3_dict=station_weights['quota3'][item['quota_name2']]
                item['calculate_weight_rate3'] = quota3_dict[item['quota_name3']]
                item['start_time'] = start_date_
                item['end_time'] = end_date_
                item['creator'] = "system"
                item['create_time'] = datetime.now()
                item['updater'] = "system"
                item['update_time'] = datetime.now()

                # 保存权重
            await BusStation(client).save_weights(_list)
            return _list
    except Exception as e:
        print(f"站场保存权重执行出错: {e}")
    print("数据库连接已关闭")

async def delete_station_datas(_start_time: str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df = await BusStation(client).delete_data_by_ppartition('abs_bus_station_quota_score_sub', _start_time)
            return df
    except Exception as e:
        print(f"删除站场画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_station_main_datas (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            df=await BusStation(client).delete_data_by_ppartition('abs_bus_station_profile_main',_start_time)
            return df
    except Exception as e:
        print(f"删除站场画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def delete_station_weights_datas (_start_time:str) -> dict | None:
    try:
        async with await connect_to_clickhouse() as client:
            strwhere=f" profile_type='站场画像' and toDate(start_time)='{_start_time}'"
            df=await BusStation(client).delete_data_by_where('obs_quota_weight_configuration',strwhere)
            return df
    except Exception as e:
        print(f"删除驾驶员画像数据执行出错: {e}")
    print("数据库连接已关闭")

async def update_station_scores_main(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            # date_range = pd.date_range(start="2026-01-01", end="2026-01-01")
            date_range = [_start_time]
            for date in date_range:
                start_date=datetime.strptime(date,"%Y-%m-%d")
                start_time = start_date.strftime('%Y-%m-%d')
                _ppartition=start_date.strftime('%Y%m%d')

                list = await BusStation(client).get_station_scores(_ppartition)
                await delete_station_main_datas(_ppartition)
                await BusStation(client).save(list, [])
                # manager = ClickHouseManage(client, "abs_driver_profile_main")
                # data={}
                # for item in list:
                #     data['evalutaion_type']=await crud.Driver(client).get_risk_value(item['score'])
                #     data['score'] = item['score']
                #     await manager.put_data(item['id'],data)

    except Exception as e:
        print(f"驾驶安全评价执行出错: {e}")
    print("数据库连接已关闭")

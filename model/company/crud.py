import uuid
from datetime import datetime, timedelta

# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger
from utils.tools import get_next_month_day, get_last_month_day


#数据库操作
class Company(ClickHouseManage):

    def __init__(self, db: Client):
        super(Company, self).__init__(db, "", "","")

    async def get_risk_value(self,score)-> str | None:
        manager = ClickHouseManage(self.db, "")
        sql=sql_config.get_risk_value()
        datas = await manager.get_data_sql_dict(sql)
        for data in datas:
            parts=data['item_value'].strip().split('-')
            result = [int(part) for part in parts]
            min_val, max_val = result
            is_in_range = min_val <= round(score) <=max_val
            if is_in_range:
                return data['item_text']
        return ""

    async def get_companys(self)-> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = f""" select organ_id,organ_name from canbus.ods_jituan_bs_organ """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_abs_company_profile_main( self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        #ppartition='{_id}' and
        sql = f"select id,company_id,company_name,organ_id,organ_name from ai_security.abs_company_profile_main where  deleted!='1' and  and ppartition='{_id}'"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_drivers_avg_scores(self, sqlwhere: str = None,start_time_str:str=None,end_time_str:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        s_sql=f"""
            select a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,case when b.quota_level='1' then '2' else b.quota_level end quota_level,avg(b.score) as score 
            ,avg(b.weight_rate) as weight_rate,avg(b.original_value) as original_value,
            case when b.quota_name in ('性别','教育水平') then arrayElement(topK(1)(risk_data),1) else cast(avg(case when b.risk_data='' or b.risk_data='nan' then 0 else cast(b.risk_data as decimal(12,2)) end) as varchar(10)) end as risk_data,
            replaceRegexpAll(
                    replaceRegexpAll(b.quota_id, '驾驶员画像', '单位画像-驾驶员风险'), 
                    '不良行为-|健康风险-|其他风险-|违法违章-|生理状态-|精神状态-', ''  
                ) AS company_quota_id,
            replaceRegexpAll(
                replaceRegexpAll(b.parent_id , '驾驶员画像', '单位画像-驾驶员风险'), 
                '-不良行为|-健康风险|-其他风险|-违法违章|-生理状态|-精神状态', ''  
                ) AS company_parent_id
            from 
            (select * from ai_security.abs_driver_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_driver_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL not in ('不良行为','健康风险','其他风险','违法违章','生理状态','精神状态') 
            {sqlwhere} 
            group by a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,b.quota_level  
            order by a.organ_id,b.quota_id  
            """
        sql = s_sql + " union all "
        sql = sql + f""" with total_score as ({s_sql}),
                                   company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                                          FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                                          on aa.parent_id=bb.organ_id 
                                          WHERE aa.parent_id <> '')
                                   select bb.parent_id as organ_id ,bb.organ_name ,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level,avg(aa.score) score,avg(aa.weight_rate),avg(aa.original_value),
                                  case when aa.quota_name in ('性别','教育水平') then arrayElement(topK(1)(risk_data),1) else cast(avg(cast(risk_data as decimal(12,2))) as varchar(10)) end as risk_data,
                                    aa.company_quota_id,aa.company_parent_id
                                    from total_score aa GLOBAL inner join company_parent bb 
                                    on aa.organ_id=bb.organ_id 
                                    group by bb.parent_id,bb.organ_name,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level, aa.company_quota_id,aa.company_parent_id   """
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_route_company_avg_scores(self, strwhere: str = None,start_time_str:str=None,end_time_str:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        s_sql=f"""
           select a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,  case when b.quota_level='1' then '2' else b.quota_level end as quota_level ,avg(b.score) as score 
            ,avg(b.weight_rate) as weight_rate,avg(b.original_value) as original_value,
            avg(case when b.risk_data='' or b.risk_data='nan' then 0 else cast(b.risk_data as decimal(12,2)) end) as risk_data,
            replaceRegexpAll(
                    replaceRegexpAll(b.quota_id, '线路画像', '单位画像-线路风险'),  
                    '车辆故障总数-|驾驶不良行为-|人口密集区域-|线形路况-|线路黑点-', ''  
                ) AS company_quota_id,
            '单位画像-线路风险' AS company_parent_id
            from  (select * from ai_security.abs_route_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a 
            GLOBAL inner join ai_security.abs_route_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' 
            and quota_name GLOBAL not in ('车辆故障总数','驾驶不良行为','人口密集区域','线形路况','线路黑点')
            group by a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,b.quota_level  
            order by a.organ_id,b.quota_id  
            """
        sql = s_sql + " union all "
        sql = sql + f""" with total_score as ({s_sql}),
                                   company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                                          FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                                          on aa.parent_id=bb.organ_id 
                                          WHERE aa.parent_id <> '')
                                   select bb.parent_id as organ_id ,bb.organ_name ,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level,avg(aa.score) score,avg(aa.weight_rate),avg(aa.original_value),avg(cast(risk_data as decimal(12,2))) as risk_data, 
                                    aa.company_quota_id,aa.company_parent_id
                                    from total_score aa GLOBAL inner join company_parent bb 
                                    on aa.organ_id=bb.organ_id 
                                    group by bb.parent_id,bb.organ_name,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level, aa.company_quota_id,aa.company_parent_id   """

        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas


    async def get_route_avg_scores(self, strwhere: str = None,start_time_str:str=None,end_time_str:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        s_sql=f"""
           select a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id, case when b.quota_level='3' then '2' else b.quota_level end as quota_level ,avg(b.score) as score 
            ,avg(b.weight_rate) as weight_rate,avg(b.original_value) as original_value,
            avg(case when b.risk_data='' or b.risk_data='nan' then 0 else cast(b.risk_data as decimal(12,2)) end) as risk_data,
            replaceRegexpAll(
                    replaceRegexpAll(b.quota_id, '线路画像', '单位画像-线路风险'),  
                    '静态风险-|动态风险-|车辆故障总数-|驾驶不良行为-|人口密集区域-|线形路况-|线路黑点-', ''  
                ) AS company_quota_id,
            '单位画像-线路风险' AS company_parent_id
            from  (select * from ai_security.abs_route_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a 
            GLOBAL inner join ai_security.abs_route_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' 
            and quota_name GLOBAL not in ('动态风险','静态风险','车辆故障总数','驾驶不良行为','人口密集区域','线形路况','线路黑点')
            group by a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,b.quota_level  
            order by a.organ_id,b.quota_id  
            """
        sql = s_sql + " union all "
        sql = sql + f""" with total_score as ({s_sql}),
                                   company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                                          FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                                          on aa.parent_id=bb.organ_id 
                                          WHERE aa.parent_id <> '')
                                   select bb.parent_id as organ_id ,bb.organ_name ,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level,avg(aa.score) score,avg(aa.weight_rate),avg(aa.original_value),avg(cast(risk_data as decimal(12,2))) as risk_data, 
                                    aa.company_quota_id,aa.company_parent_id
                                    from total_score aa GLOBAL inner join company_parent bb 
                                    on aa.organ_id=bb.organ_id 
                                    group by bb.parent_id,bb.organ_name,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level, aa.company_quota_id,aa.company_parent_id   """

        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_avg_scores(self, strwhere: str = None,start_time_str:str=None,end_time_str:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        s_sql=f"""
            select a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id, case when b.quota_level='1' then '2' else b.quota_level end as quota_level ,avg(b.score) as score 
            ,avg(b.weight_rate) as weight_rate,avg(b.original_value) as original_value,
            case when b.quota_name in ('车辆品牌') then 
            arrayElement(topK(1)(risk_data),1) else 
            cast(avg(case when b.risk_data='' or b.risk_data='nan' then 0 else 
            toFloat64OrNull(ifnull(b.risk_data,0)) end) as varchar(10)) end as risk_data,
            replaceRegexpAll(
                    replaceRegexpAll(b.quota_id, '车辆画像', '单位画像-车辆风险'),  
                    '车辆设备-|车辆属性-|车辆维修-|车辆运营-|驾驶不良行为-|行驶路况-', ''  
                ) AS company_quota_id,
            replaceRegexpAll(
                replaceRegexpAll(b.parent_id , '车辆画像', '单位画像-车辆风险'),  
                '-车辆设备|-车辆属性|-车辆维修|-车辆运营|-驾驶不良行为|-行驶路况', ''  
                ) AS company_parent_id
            from  
             (select * from ai_security.abs_bus_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_bus_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and quota_name GLOBAL not in (
            '车辆设备','车辆属性','车辆维修','车辆运营','驾驶不良行为','行驶路况')
             {strwhere}
            group by a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,b.quota_level  
            order by a.organ_id,b.quota_id  
            """
        sql = s_sql + " union all "
        sql = sql + f""" with total_score as ({s_sql}),
                           company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                                  FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                                  on aa.parent_id=bb.organ_id 
                                  WHERE aa.parent_id <> '')
                           select bb.parent_id as organ_id ,bb.organ_name ,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level,avg(aa.score) score,avg(aa.weight_rate),avg(aa.original_value),
                           case when aa.quota_name in ('车辆品牌') then 
                            arrayElement(topK(1)(aa.risk_data),1) else 
                            cast(avg(toFloat64OrNull(ifnull(aa.risk_data,0))) as varchar(10)) end as risk_data,
                            aa.company_quota_id,aa.company_parent_id
                            from total_score aa GLOBAL inner join company_parent bb 
                            on aa.organ_id=bb.organ_id 
                            group by bb.parent_id,bb.organ_name,aa.quota_id,aa.quota_name,aa.parent_id,aa.quota_level, aa.company_quota_id,aa.company_parent_id   """

        sql=sql.replace("\n","")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_bus_station_avg_scores(self, strwhere: str = None,start_time_str:str=None,end_time_str:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        s_sql=f"""
            with score_detail as (select a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id, case when b.quota_level='1' then '2' else b.quota_level end as quota_level ,avg(b.score) as score 
            ,avg(b.weight_rate) as weight_rate,avg(b.original_value) as original_value,
            arrayElement(topK(1)(risk_data),1) as risk_data,
            replaceRegexpAll(
                    replaceRegexpAll(b.quota_id, '站场画像', '单位画像-站场风险'),  
                    '划定区域-|路边区域-', ''  
                ) AS company_quota_id,
            replaceRegexpAll(
                replaceRegexpAll(b.parent_id , '站场画像', '单位画像-站场风险'),  
                '-划定区域|-路边区域', ''  
                ) AS company_parent_id
            from  ai_security.abs_bus_station_profile_main a 
            GLOBAL inner join ai_security.abs_bus_station_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and quota_name GLOBAL not in (
            '划定区域','路边区域')  
            group by a.organ_id,a.organ_name,b.quota_id,b.quota_name,b.parent_id,b.quota_level  
            order by a.organ_id,b.quota_id )
            select organ_id,organ_name,quota_name,quota_level,avg(score) as score,avg(weight_rate) as weight_rate,avg(original_value) as original_value,arrayElement(topK(1)(risk_data),1) as risk_data,company_quota_id,company_parent_id  
            from score_detail group by organ_id,organ_name,quota_name,quota_level,company_quota_id,company_parent_id
            order by organ_id,company_quota_id  
            """
        sql = s_sql + " union all "
        sql = sql + f""" with total_score as ({s_sql}),
                           company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                                  FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                                  on aa.parent_id=bb.organ_id 
                                  WHERE aa.parent_id <> '')
                           select bb.parent_id as organ_id ,bb.organ_name ,aa.quota_name,aa.quota_level,avg(aa.score) score,avg(aa.weight_rate),avg(aa.original_value),arrayElement(topK(1)(aa.risk_data),1) as risk_data, 
                            aa.company_quota_id,aa.company_parent_id
                            from total_score aa GLOBAL inner join company_parent bb 
                            on aa.organ_id=bb.organ_id 
                            group by bb.parent_id,bb.organ_name,aa.quota_name,aa.quota_level, aa.company_quota_id,aa.company_parent_id   """

        sql=sql.replace("\n","")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_company_quota1_scores(self, strwheres: dict = None,start_time_str:str=None,end_time_str:str=None,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere=""
        if _start_time is not None:
            strwhere=f" and '{_start_time}' between start_time and end_time "

        s_sql=f"""
           select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score, 
             (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['driver_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['driver_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-驾驶员风险' as company_quota_id,'单位画像' as company_parent_id, '驾驶员风险' as company_quota_name
            from  
            (select * from ai_security.abs_driver_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_driver_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['driver']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id  
            union all 
            select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['route_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['route_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-线路风险' as company_quota_id,'单位画像' as company_parent_id, '线路风险' as company_quota_name
            from  
            (select * from ai_security.abs_route_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_route_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['route']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            union all 
            select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['vehicle_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['vehicle_quota_name']}' and deleted != '1' {strwhere} )) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-车辆风险' as company_quota_id,'单位画像' as company_parent_id, '车辆风险' as company_quota_name
            from 
            (select * from ai_security.abs_bus_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_bus_quota_score_sub b on a.id=b.main_id   
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['vehicle']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            """
        sql = f""" with detail_score as ({s_sql}) select organ_id,organ_name,parent_id,score,cast(weight_rate/100 as varchar(10)) as weight_rate,original_value,company_quota_id,company_parent_id,company_quota_name  from detail_score where organ_id  GLOBAL not in (
            SELECT DISTINCT aa.parent_id as parent_id
                    FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                    on aa.parent_id=bb.organ_id 
                    WHERE aa.parent_id <> '')  union all """
        sql = sql + f""" with total_score as ({s_sql}),
                    company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                           FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                           on aa.parent_id=bb.organ_id 
                           WHERE aa.parent_id <> '')
                    select bb.parent_id as organ_id ,bb.organ_name as organ_name ,'单位画像' as parent_id,                    
                     avg(aa.score) score,cast(avg(aa.weight_rate/100) as varchar(10)) weight_rate,avg(aa.original_value) original_value,                     
                     aa.company_quota_id,aa.company_parent_id,aa.company_quota_name 
                     from total_score aa GLOBAL inner join company_parent bb 
                     on aa.organ_id=bb.organ_id 
                     group by bb.parent_id,bb.organ_name,aa.company_quota_id,aa.company_parent_id,aa.company_quota_name 
                      union all 
                    select a.organ_id as organ_id,a.organ_name as organ_name , b.parent_id as parent_id,avg(b.score)  as score,
                    cast((select distinct case when weight_rate1 =0 then calculate_weight_rate1/100 else weight_rate1/100 end weight_rate from ai_security.obs_quota_weight_configuration 
                    where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['station_quota_name']}' and  deleted != '1' and
                    start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
                    where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['station_quota_name']}' and deleted != '1' {strwhere} )) as varchar(10)) as weight_rate,
                    avg(b.original_value) as original_value,
                    '单位画像-站场风险' as company_quota_id,'单位画像' as company_parent_id, '站场风险' as company_quota_name
                    from 
                    (select * from ai_security.abs_bus_station_profile_main ) a
                    GLOBAL inner join ai_security.abs_bus_station_quota_score_sub b on a.id=b.main_id   
                    where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
                    b.quota_name GLOBAL in ({strwheres['station']}) and b.quota_level='1'
                    group by a.organ_id,a.organ_name,b.parent_id 
                        """

        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_company_quota1_station_scores(self, strwheres: dict = None,start_time_str:str=None,end_time_str:str=None,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere=""
        if _start_time is not None:
            strwhere=f" and '{_start_time}' between start_time and end_time "

        s_sql=f"""
           select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score, 
             (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['driver_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['driver_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-驾驶员风险' as company_quota_id,'单位画像' as company_parent_id, '驾驶员风险' as company_quota_name
            from  
            (select * from ai_security.abs_driver_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_driver_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['driver']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id  
            union all 
            select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['route_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['route_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-线路风险' as company_quota_id,'单位画像' as company_parent_id, '线路风险' as company_quota_name
            from  
            (select * from ai_security.abs_route_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_route_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['route']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            union all 
            select a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['vehicle_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{strwheres['profile_type']}' and quota_name1='{strwheres['vehicle_quota_name']}' and deleted != '1' {strwhere} )) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-车辆风险' as company_quota_id,'单位画像' as company_parent_id, '车辆风险' as company_quota_name
            from 
            (select * from ai_security.abs_bus_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_bus_quota_score_sub b on a.id=b.main_id   
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({strwheres['vehicle']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            """
        sql = f""" with detail_score as ({s_sql}) select organ_id,organ_name,parent_id,score,cast(weight_rate/100 as varchar(10)) as weight_rate,original_value,company_quota_id,company_parent_id,company_quota_name  from detail_score where organ_id  GLOBAL not in (
            SELECT DISTINCT aa.parent_id as parent_id
                    FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                    on aa.parent_id=bb.organ_id 
                    WHERE aa.parent_id <> '')  union all """
        sql = sql + f""" with total_score as ({s_sql}),
                    company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                           FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                           on aa.parent_id=bb.organ_id 
                           WHERE aa.parent_id <> '')
                    select bb.parent_id as organ_id ,bb.organ_name as organ_name ,'单位画像' as parent_id,                    
                     avg(aa.score) score,cast(avg(aa.weight_rate/100) as varchar(10)) weight_rate,avg(aa.original_value) original_value,                     
                     aa.company_quota_id,aa.company_parent_id,aa.company_quota_name 
                     from total_score aa GLOBAL inner join company_parent bb 
                     on aa.organ_id=bb.organ_id 
                     group by bb.parent_id,bb.organ_name,aa.company_quota_id,aa.company_parent_id,aa.company_quota_name 
                        """

        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_company_total_scores(self,sqlwheres: dict = None,start_time_str:str=None,end_time_str:str=None,_start_time:str=None) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        s_sql=f""" select organ_id,organ_name,sum(score*weight_rate/100) as score from (
           select 1 as bz,a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score, 
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['driver_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['driver_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-驾驶员风险' as company_quota_id,'单位画像' as company_parent_id
            from  
             (select * from ai_security.abs_driver_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_driver_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({sqlwheres['driver']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id  
            union all 
            select 1 as bz,a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['route_quota_name']}' and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['route_quota_name']}' and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-线路风险' as company_quota_id,'单位画像' as company_parent_id
            from  
            (select * from ai_security.abs_route_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a 
            GLOBAL inner join ai_security.abs_route_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({sqlwheres['route']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            union all 
            select 1 as bz,a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['vehicle_quota_name']}'  and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '{sqlwheres['profile_type']}' and quota_name1='{sqlwheres['vehicle_quota_name']}'  and deleted != '1' {strwhere})) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-车辆风险' as company_quota_id,'单位画像' as company_parent_id
            from 
            (select * from ai_security.abs_bus_profile_main where 
            organ_id not in (select distinct parent_id FROM canbus.ods_jituan_bs_organ where parent_id<>'')) a
            GLOBAL inner join ai_security.abs_bus_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' and   
            b.quota_name GLOBAL in ({sqlwheres['vehicle']}) and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            union all 
            select 1 as bz,a.organ_id,a.organ_name,b.parent_id,avg(b.score) as score,
            (select distinct case when weight_rate1 =0 then calculate_weight_rate1 else weight_rate1 end weight_rate from ai_security.obs_quota_weight_configuration 
            where profile_type = '单位画像' and quota_name1='站场风险'  and  deleted != '1' and
            start_time GLOBAL in (select max(start_time) from ai_security.obs_quota_weight_configuration 
            where profile_type = '单位画像' and quota_name1='站场风险'  and deleted != '1' {strwhere}
            )) as weight_rate,
            avg(b.original_value) as original_value,
            '单位画像-站场风险' as company_quota_id,'单位画像' as company_parent_id
            from 
            (select * from ai_security.abs_bus_station_profile_main ) a
            GLOBAL inner join ai_security.abs_bus_station_quota_score_sub b on a.id=b.main_id 
            where b.ppartition between '{start_time_str}' and '{end_time_str}' and a.organ_id<>'' 
            and b.quota_name GLOBAL in ('路边区域','划定区域') and b.quota_level='1'
            group by a.organ_id,a.organ_name,b.parent_id 
            ) aa group by organ_id,organ_name
            """
        sql = s_sql+" union all "
        sql = sql+ f""" with total_score as ({s_sql}),
             company_parent as (  SELECT DISTINCT aa.parent_id as parent_id, aa.organ_id as organ_id,bb.organ_name  as organ_name 
                    FROM canbus.ods_jituan_bs_organ aa GLOBAL inner join canbus.ods_jituan_bs_organ bb 
                    on aa.parent_id=bb.organ_id 
                    WHERE aa.parent_id <> '')
             select bb.parent_id ,bb.organ_name ,avg(aa.score) as score from total_score aa GLOBAL inner join company_parent bb 
             on aa.organ_id=bb.organ_id 
             group by bb.parent_id,bb.organ_name """
        sql=" select organ_id,sum(score) as score from ("+sql+") group by organ_id "
        sql=" select bb.organ_id as organ_id,bb.organ_name as organ_name ,aa.score as score from ("+sql+") aa inner join (select organ_id, organ_name from canbus.ods_jituan_bs_organ) bb on aa.organ_id=bb.organ_id "
        sql = sql.replace("\n", "")
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def save(self, main_datas, score_datas):
        insert_operations = [
            {
                "table": "abs_company_profile_main",
                "list": main_datas
            },
            {
                "table": "abs_company_score_sub",
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

    async def save_accident(self, main_datas, score_datas):
        insert_operations = [
            {
                "table": "ads_accident_profile_main",
                "list": main_datas
            },
            {
                "table": "ads_accident_score_sub",
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

    async def get_company_weights(
            self,
            _id: str = None,_start_time:str=None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        strwhere = ""
        if _start_time is not None:
            strwhere = f" and '{_start_time}' between start_time and end_time "
        sql=f""" select distinct profile_type,quota_id1,quota_name1,calculate_weight_rate1,weight_rate1 ,quoa_desc1,quoa_unit1  from ai_security.obs_quota_weight_configuration 
            where profile_type in ('单位画像','事故画像') and  deleted != '1' and
            start_time in (select max(start_time) from ai_security.obs_quota_weight_configuration where profile_type in ('单位画像','事故画像') and deleted != '1' {strwhere})
            """
        sql=sql.replace("\n","")
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
                    f"ALTER TABLE {table} DELETE where profile_type in ('单位画像','事故画像') and start_time='{datas[0]['start_time']}'")
                success = await manager.batch_insert(table, datas, batch_size=m_size)
                if not success:
                    all_success = False
                    break

            # 根据结果提交或回滚
            if all_success:
                await manager.commit_transaction()
                logger.info("单位画像、事故画像权重 所有表保存成功")
                return True
            else:
                await manager.rollback_transaction()
                logger.error("单位画像、事故画像权重 部分保存失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"单位画像、事故画像权重保存 异常: {e}")
            await manager.rollback_transaction()
            return False

    async def get_company_report(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")

        sql =f"""
            select organ_id,organ_name,ppartition from ai_security.abs_company_profile_main where ppartition='{_start_time}' order by score desc limit 2 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def get_accident_report(self,_start_time) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql =f"""
            select b.employee_name,accident_time,ppartition  from canbus.ods_jituan_accident a 
            GLOBAL inner join canbus.ods_jituan_bs_employee  b on a.employee_code=b.employee_id  
            where ppartition='{_start_time}' order by accident_time desc  limit 2 
            """
        datas = await manager.get_data_sql_dict(sql)
        return datas
#保存单位画像权重、事故风险权重
async def save_company_weights_data(_start_time,company_weights):
    try:
        start_date_ = datetime.strptime(_start_time, '%Y-%m-%d')
        end_date = get_next_month_day(start_date_)
        end_date_ = end_date - timedelta(days=1)
        async with await connect_to_clickhouse() as client:
            _list = await Company(client).get_company_weights(get_last_month_day(start_date_).strftime('%Y-%m-%d'))
            for item in _list:
                item['id'] = str(uuid.uuid4())
                item['calculate_weight_rate1'] =company_weights[item['quota_name1']]*100
                item['calculate_weight_rate2'] = 0
                item['calculate_weight_rate3'] = 0
                item['start_time'] = start_date_
                item['end_time'] = end_date_
                item['creator'] = "system"
                item['create_time'] = datetime.now()
                item['updater'] = "system"
                item['update_time'] = datetime.now()

                # 保存权重
            await Company(client).save_weights(_list)
            return _list
    except Exception as e:
        print(f"驾驶员服务态度保存权重执行出错: {e}")
    print("数据库连接已关闭")

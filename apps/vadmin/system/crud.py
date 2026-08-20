
# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core.clickhouse_manage import ClickHouseManage

from apps.vadmin.system.schemas import can

#数据库增删改查
class Canpacking(ClickHouseManage):

    def __init__(self, db: Client):
        super(Canpacking, self).__init__(db, "ods_communication_can_packing", can)


    async def get_can_limit1(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "ods_communication_can_packing")
        # sql = "SELECT * FROM ai_security.ods_communication_can_packing as aa left JOIN ai_security.abs_can_stats_result as bb on aa.obuid = bb.obuid AND aa.report_time = bb.report_time WHERE formatDateTime(aa.report_time, '%%Y-%%m-%%d') between '2025-12-16' and '2025-12-19' and ifnull(bb.obuid,'')='' and ifnull(aa.obuid,'')<>'' order by aa.report_time DESC,aa.obuid  limit 1"
        # sql = "SELECT * FROM ai_security.ods_communication_can_packing as aa left JOIN ai_security.abs_can_stats_result as bb on aa.obuid = bb.obuid AND aa.report_time = bb.report_time WHERE  ifnull(bb.obuid,'')='' and ifnull(aa.obuid,'')<>'' order by aa.report_time DESC,aa.obuid  limit 1"
        sql=" select * from canbus.ods_communication_can_packing where ppartition between '20251130' and '20251230' and ((obuid, ppartition) not in (select distinct obuid, ppartition from ai_security.abs_can_stats_result where ppartition between '20251130' and '20251230')) order by ppartition DESC, obuid limit 1 "
        # sql = "select * from ai_security.ods_communication_can_packing WHERE(formatDateTime(report_time, '%%Y-%%m-%%d') between '2025-11-30' and '2025-12-30') and ((obuid, report_time) not in (select distinct obuid, report_time from ai_security.abs_can_data_result WHERE (formatDateTime(report_time, '%%Y-%%m-%%d') between '2025-11-30' and '2025-12-30'))) order by report_time DESC, obuid limit 1"
        result = await manager.get_data_sql_dict(sql)
        return result

    async def get_logs(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "ai_security.obs_module_weight_log")
        # sql = "SELECT * FROM ai_security.ods_communication_can_packing as aa left JOIN ai_security.abs_can_stats_result as bb on aa.obuid = bb.obuid AND aa.report_time = bb.report_time WHERE formatDateTime(aa.report_time, '%%Y-%%m-%%d') between '2025-12-16' and '2025-12-19' and ifnull(bb.obuid,'')='' and ifnull(aa.obuid,'')<>'' order by aa.report_time DESC,aa.obuid  limit 1"
        # sql = "SELECT * FROM ai_security.ods_communication_can_packing as aa left JOIN ai_security.abs_can_stats_result as bb on aa.obuid = bb.obuid AND aa.report_time = bb.report_time WHERE  ifnull(bb.obuid,'')='' and ifnull(aa.obuid,'')<>'' order by aa.report_time DESC,aa.obuid  limit 1"
        sql=" select module_name,calculate_date,remark,start_time,end_time,pid from ai_security.obs_module_weight_log "
        # sql = "select * from ai_security.ods_communication_can_packing WHERE(formatDateTime(report_time, '%%Y-%%m-%%d') between '2025-11-30' and '2025-12-30') and ((obuid, report_time) not in (select distinct obuid, report_time from ai_security.abs_can_data_result WHERE (formatDateTime(report_time, '%%Y-%%m-%%d') between '2025-11-30' and '2025-12-30'))) order by report_time DESC, obuid limit 1"
        result = await manager.get_data_sql_dict(sql)
        return result


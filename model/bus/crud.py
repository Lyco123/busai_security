from datetime import datetime

# @File           : crud.py
# @IDE            : PyCharm
# @desc           : 数据库 增删改查操作


from clickhouse_driver import Client

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from core.logger import logger
from model.bus.schemas.bus_profile import ObsModuleLog


#数据库增删改查
class Bus(ClickHouseManage):

    def __init__(self, db: Client):
        super(Bus, self).__init__(db, "", "","")


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

    async def save_log(self, log_datas,table_name):
        insert_operations = [
            {
                "table": table_name,
                "list": log_datas
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


async def insert_moudle_log(log_data,table_name=None):
    try:
        async with await connect_to_clickhouse() as client:
            if table_name is None:
                table_name = "obs_module_log"
            log_datas=[]
            log_datas.append(log_data)
            df=await Bus(client).save_log(log_datas,table_name)
            return df
    except Exception as e:
        print(f"保存日志信息执行出错: {e}")
    print("数据库连接已关闭")

async def update_moudle_log(id,remark,table_name=None):
    try:
        end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with await connect_to_clickhouse() as client:
            if table_name is None:
                table_name = "obs_module_log"
            query = f"ALTER TABLE {table_name} UPDATE end_time='{end_time}',remark='{remark}' WHERE id = '{id}'"
            # sql=f"""update ai_security.obs_module_log set end_time='{end_time}',remark='{remark}' where id='{id}'"""
            df=await Bus(client).execute_query(query)
            return df
    except Exception as e:
        print(f"保存日志信息执行出错: {e}")
    print("数据库连接已关闭")



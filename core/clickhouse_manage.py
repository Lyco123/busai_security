import asyncio
import datetime
import json
import time
from typing import Any, Union, Dict, List

from clickhouse_driver import Client
from fastapi.encoders import jsonable_encoder
from rich.status import Status

from core.logger import logger
from core.exception import CustomException
import pandas as pd



class ClickHouseManage:


    # 倒叙
    ORDER_FIELD = ["desc", "descending"]

    def __init__(
            self,
            db: Client = None,
            table_name: str = None,
            schema: Any = None,
            is_object_id: bool = False
    ):
        """
        初始化
        :param db:
        :param collection: 集合
        :param schema:
        :param is_object_id: _id 列是否为 ObjectId 格式
        """
        self.db = db
        self.table_name = table_name
        self.schema = schema
        self.is_object_id = is_object_id
        self.session_id = None

    def filter_condition(self, **kwargs):
        # 构建查询条件
        return kwargs

    async def get_data(
            self,
            _id: str = None,
            v_return_none: bool = False,
            v_schema: Any = None,
            **kwargs
    ) -> Union[Dict, None]:
        """
        获取单个数据，默认使用 ID 查询，否则使用关键词查询
        :param _id: 数据 ID
        :param v_return_none: 是否返回空 None，否则抛出异常，默认抛出异常
        :param v_schema: 指定使用的序列化对象
        """
        # 构建查询条件
        if _id:
            kwargs["id"] = _id  # ClickHouse中通常使用id字段而不是_id

        params = self.filter_condition(**kwargs)

        # 构建SQL查询语句
        query_conditions = []
        query_params = {}

        for key, value in params.items():
            query_conditions.append(f"{key} = %({key})s")
            query_params[key] = value

        if query_conditions:
            query = f"SELECT * FROM {self.table_name} WHERE {' AND '.join(query_conditions)} LIMIT 1"
        else:
            query = f"SELECT * FROM {self.table_name} LIMIT 1"

        try:
            # 执行查询
            result = self.db.execute(query, query_params, with_column_types=True)

            if not result and v_return_none:
                return None
            elif not result:
                raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            # 处理查询结果
            data, columns = result
            if not data:
                if v_return_none:
                    return None
                else:
                    raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            # 将结果转换为字典格式
            column_names = [col[0] for col in columns]
            row_data = dict(zip(column_names, data[0])) if data else {}

            if row_data and v_schema:
                return jsonable_encoder(v_schema(**row_data))

            return row_data

        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def create_data(self, data: Union[dict, Any]) -> Dict:
        """
        创建数据
        """
        if not isinstance(data, dict):
            data = jsonable_encoder(data)
        data['create_datetime'] = datetime.datetime.now()
        data['update_datetime'] = datetime.datetime.now()

        # 构建INSERT语句
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["%s"] * len(columns))
        column_names = ", ".join(columns)

        query = f"INSERT INTO {self.table_name} ({column_names}) VALUES ({placeholders})"

        try:
            # 执行插入
            result = self.db.execute(query, values)
            # 返回模拟的插入结果
            return {"acknowledged": True, "insert_id": str(result) if result else None}
        except Exception as e:
            raise CustomException(f"创建新数据失败: {str(e)}", code=Status.HTTP_ERROR)

    async def insert_data_fixed(self,data: Union[Dict, List[Dict]]):
        """
        修复后的数据插入方法，正确处理占位符和数据类型
        """
        if isinstance(data, dict):
            data = [data]

        if not data:
            print("无数据可插入")
            return

        # 获取列名
        columns = list(data[0].keys())

        # 构造正确的占位符（ClickHouse使用{}而不是%s）
        placeholders = ', '.join(['{}'] * len(columns))
        query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES"

        try:
            # 使用executemany处理多行数据
            result = self.db.execute(query, data)
            print("数据插入成功")
            return result
        except Exception as e:
            print(f"插入失败: {str(e)}")

    async def insert_data_with_prepared_statement(self, table: str, data: Union[Dict, List[Dict]]):
        """
        使用预编译语句的方式插入数据
        """
        if isinstance(data, dict):
            data = [data]

        if not data:
            print("无数据可插入")
            return

        columns = list(data[0].keys())
        column_names = ', '.join(columns)

        # 构造VALUES部分
        values_list = []
        params = []
        # 构造VALUES部分
        values_list = []
        params = []
        for row in data:
            # 处理特殊数据类型
            processed_row = {}
            for key, value in row.items():
                if isinstance(value, datetime.datetime):
                    processed_row[key] = value
                elif isinstance(value, dict):
                    processed_row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    processed_row[key] = value
            params.append(processed_row)

        query = f"INSERT INTO {table} ({column_names}) VALUES"

        try:
            result=self.db.execute(query, params)
            # 4. 判断结果
            # 不同驱动返回值不同：
            # - clickhouse-driver: 通常返回 None 或 (rows_read, rows_written)
            # - pymysql/psycopg2: 通常返回受影响行数 (int) 或 None

            if result is None:
                # 某些驱动成功时返回 None
                logger.info(f"数据成功插入 {len(data)} 行到 {table}")
                return True
            elif isinstance(result, int):
                if result >= 0:
                    logger.info(f"数据成功插入 {result} 行到 {table}")
                    return True
                else:
                    logger.error(f"插入返回负数结果: {result}")
                    return False
            elif isinstance(result, tuple):
                # 例如 clickhouse 可能返回 (rows_read, rows_written)
                logger.info(f"数据插入完成，结果: {result}")
                return True
            else:
                # 其他情况视为成功，除非有异常抛出
                logger.info(f"数据插入完成，响应类型: {type(result)}")
                return True

        except Exception as e:
            # 5. 详细错误日志
            print(f"插入失败: {str(e)}")
            logger.error(f"插入失败: {str(e)}")
            logger.error(f"表名: {table}")
            logger.error(f"列名: {columns}")
            if params:
                # 只打印第一行数据作为示例，避免日志过大
                logger.error(f"示例数据行 (前3个字段): {params[:3]}...")
            return False

    async def batch_insert(self, table: str, data: List[Dict], batch_size: int = 1000):
        """
        批量插入数据，避免大数据量时的性能问题
        """
        if not data:
            print("无数据可插入")
            return

        total = len(data)
        success = True
        for i in range(0, total, batch_size):
            batch = data[i:i + batch_size]
            success = await self.insert_data_with_prepared_statement(table, batch)
            print(f"已处理{table}:{min(i + batch_size, total)}/{total} 条记录")
        return success

    async def put_data(self, _id: str, data: Union[dict, Any]) -> Dict:
        """
        更新数据
        """
        if not isinstance(data, dict):
            data = jsonable_encoder(data)

        # 移除ID字段避免更新主键
        if '_id' in data:
            del data['_id']
        if 'id' in data:
            del data['id']

        data['update_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建UPDATE语句
        set_clauses = []
        values = []
        for key, value in data.items():
            if isinstance(value, str):
                set_clauses.append(f"{key} ='{value}'")
            else:
                set_clauses.append(f"{key} ={value}")
            # values.append(value)

        set_clause = ", ".join(set_clauses)
        # values.append(_id)  # 添加ID作为WHERE条件

        # query = f"""
        #  ALTER TABLE ai_security.abs_driver_profile_main
        #  UPDATE evalutaion_type ='安全型',
        #  score =10,
        #  update_time ='2026-04-09 16:46:30'
        #  WHERE id = 'cd7de9a8-bdae-4f28-b0bd-5322a9fca296'
        # """
        query = f"ALTER TABLE {self.table_name} UPDATE {set_clause} WHERE id = '{_id}'"

        try:
            result = self.db.execute(query)
            # 返回模拟的更新结果
            return {"matched_count": 1 if result else 0, "modified_count": 1 if result else 0}
        except Exception as e:
            raise CustomException(f"更新失败: {str(e)}", code=Status.HTTP_ERROR)

    async def put_data_by_name(self, _name:str, _value: str, data: Union[dict, Any]) -> Dict:
        """
        更新数据
        """
        if not isinstance(data, dict):
            data = jsonable_encoder(data)

        # 移除_name字段避免更新主键
        if _name in data:
            del data[_name]

        # 构建UPDATE语句
        set_clauses = []
        values = []
        for key, value in data.items():
            if value is not None:
                formatted_value = self.format_value_for_sql(value)
                set_clauses.append(f"{key} = {formatted_value}")
        set_clause = ", ".join(set_clauses)

        query = f"ALTER TABLE {self.table_name} UPDATE {set_clause} WHERE {_name} = '{_value}'"

        try:
            result = self.db.execute(query)
            # 返回模拟的更新结果
            return {"matched_count": 1 if result else 0, "modified_count": 1 if result else 0}
        except Exception as e:
            raise CustomException(f"更新失败: {str(e)}", code=Status.HTTP_ERROR)

    async def delete_data(self, _id: str) -> bool:
        """
        删除数据
        """
        query = f"ALTER TABLE {self.table_name} DELETE WHERE id = %s"

        try:
            result = self.db.execute(query, [_id])
            if result is not None:
                return True
            else:
                raise CustomException("删除失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"删除失败: {str(e)}", code=Status.HTTP_ERROR)

    async def delete_all_data(self) -> bool:
        """
        删除数据
        """
        query = f"ALTER TABLE {self.table_name} DELETE WHERE 1=1"

        try:
            result = self.db.execute(query)
            if result is not None:
                return True
            else:
                raise CustomException("删除失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"删除失败: {str(e)}", code=Status.HTTP_ERROR)

    async def delete_data_by_ppartition(self, _table:str,_ppartition: str) -> bool:
        """
        删除数据
        """
        query = f" ALTER TABLE {_table} DROP PARTITION '{_ppartition}'"
        # query = f"ALTER TABLE {_table} DELETE WHERE ppartition='{_ppartition}'"

        try:
            result = self.db.execute(query)
            if result is not None:
                return True
            else:
                raise CustomException("删除失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                logger.error(f"删除失败: {str(e)}")
                raise CustomException(f"删除失败: {str(e)}", code=Status.HTTP_ERROR)

    async def delete_data_by_where(self, _table:str,_strwhere: str) -> bool:
        """
        删除数据
        """
        query = f"ALTER TABLE {_table} DELETE WHERE  {_strwhere}"
        # query = f"ALTER TABLE {self.table_name} DELETE WHERE ppartition='{_ppartition}'"
        try:
            result = self.db.execute(query)
            if result is not None:
                return True
            else:
                raise CustomException("删除失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"删除失败: {str(e)}", code=Status.HTTP_ERROR)


    async def get_datas(
            self,
            page: int = 1,
            limit: int = 10,
            v_schema: Any = None,
            v_order: str = None,
            v_order_field: str = None,
            v_return_objs: bool = False,
            **kwargs
    ) -> List[Dict]:
        """
        获取数据列表
        """
        params = self.filter_condition(**kwargs)

        # 构建查询语句
        query = f"SELECT * FROM {self.table_name}"
        query_params = []

        # 添加WHERE条件
        if params:
            where_conditions = []
            for key, value in params.items():
                if isinstance(value, dict) and '$regex' in value:
                    where_conditions.append(f"{key} LIKE %s")
                    query_params.append(f"%{value['$regex']}%")
                elif isinstance(value, dict) and '$gte' in value:
                    where_conditions.append(f"{key} >= %s")
                    query_params.append(value['$gte'])
                elif isinstance(value, dict) and '$lt' in value:
                    where_conditions.append(f"{key} < %s")
                    query_params.append(value['$lt'])
                else:
                    where_conditions.append(f"{key} = %s")
                    query_params.append(value)

            query += " WHERE " + " AND ".join(where_conditions)

        # 添加排序
        if v_order or v_order_field:
            v_order_field = v_order_field if v_order_field else 'create_datetime'
            order_direction = 'DESC' if v_order in self.ORDER_FIELD else 'ASC'
            query += f" ORDER BY {v_order_field} {order_direction}"

        # 添加分页
        if limit != 0:
            query += f" LIMIT {limit} OFFSET {(page - 1) * limit}"

        try:
            # result = self.db.execute(query, query_params, with_column_types=True)
            result = self.db.execute(query, with_column_types=True)
            # result = self.db.execute(query, with_column_types=True)
            if not result or len(result) != 2:
                return []

            data, columns = result
            column_names = [col[0] for col in columns]

            # 转换为字典列表
            datas = []
            for row in data:
                row_dict = dict(zip(column_names, row))
                datas.append(row_dict)

            if not datas or v_return_objs:
                return datas
            elif v_schema:
                datas = [jsonable_encoder(v_schema(**data)) for data in datas]
            elif self.schema:
                datas = [jsonable_encoder(self.schema(**data)) for data in datas]
            return datas

        except Exception as e:
            raise CustomException(f"查询失败: {str(e)}", code=Status.HTTP_ERROR)

    async def get_count(self, **kwargs) -> int:
        """
        获取统计数据
        """
        params = self.filter_condition(**kwargs)

        # 构建COUNT查询
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        query_params = []

        # 添加WHERE条件
        if params:
            where_conditions = []
            for key, value in params.items():
                if isinstance(value, dict) and '$regex' in value:
                    where_conditions.append(f"{key} LIKE %s")
                    query_params.append(f"%{value['$regex']}%")
                elif isinstance(value, dict) and '$gte' in value:
                    where_conditions.append(f"{key} >= %s")
                    query_params.append(value['$gte'])
                elif isinstance(value, dict) and '$lt' in value:
                    where_conditions.append(f"{key} < %s")
                    query_params.append(value['$lt'])
                else:
                    where_conditions.append(f"{key} = %s")
                    query_params.append(value)

            query += " WHERE " + " AND ".join(where_conditions)

        try:
            result = self.db.execute(query)
            return result[0][0] if result and result[0] else 0
        except Exception as e:
            raise CustomException(f"统计查询失败: {str(e)}", code=Status.HTTP_ERROR)

    @classmethod
    def filter_condition(cls, **kwargs) -> Dict:
        """
        过滤条件
        """
        params = {}
        for k, v in kwargs.items():
            if not v:
                continue
            elif isinstance(v, tuple):
                if v[0] == "like" and v[1]:
                    params[k] = {'$regex': v[1]}
                elif v[0] == "between" and len(v[1]) == 2:
                    params[k] = {'$gte': f"{v[1][0]} 00:00:00", '$lt': f"{v[1][1]} 23:59:59"}
                elif v[0] == "ObjectId" and v[1]:
                    try:
                        params[k] = v[1]  # ClickHouse中直接使用字符串ID
                    except Exception:
                        raise CustomException("任务编号格式不正确！")
            else:
                params[k] = v
        return params

    async def get_data_sql(self,query,
            v_return_none: bool = False,
            v_schema: Any = None,):
        query_params = {}
        try:
            # 执行查询
            result = self.db.execute(query, query_params, with_column_types=True)

            if not result and v_return_none:
                return None
            elif not result:
                raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            # 处理查询结果
            datas, columns_name = result
            if not datas:
                if v_return_none:
                    return None
                else:
                    raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
            return datas, columns_name
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def get_data_sql_dict(self,query,
            v_return_none: bool = False,
            v_schema: Any = None,):
        query_params = {}
        try:
            # 执行查询
            result = self.db.execute(query, query_params, with_column_types=True)

            if not result and v_return_none:
                return None
            elif not result:
                raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            # 处理查询结果
            datas, columns_name = result
            if not datas :
                if v_return_none or datas==[]:
                    return None
                else:
                    raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            # 将结果转换为字典格式
            column_names = [col[0] for col in columns_name]
            row_datas = [dict(zip(column_names, data)) for data in datas] if datas else {}

            if row_datas and v_schema:
                return jsonable_encoder(v_schema(**row_datas))

            return row_datas

        except Exception as e:
            print(f"{query} 报错 {e}")
            logger.error(f"{query} 报错 {e}")
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def execute_query_and_export(self,query: str):
        try:
            # print(f"执行查询: {query}")
            result = self.db.execute(query, with_column_types=True)
            if not result[0]:
                print("查询返回空结果")
                return None
            column_names = [col[0] for col in result[1]]
            data = result[0]
            return column_names, data
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def execute_query_and_column(self, query: str):
        try:
            # print(f"执行查询: {query}")
            result = self.db.execute(query, with_column_types=True)
            column_names = [col[0] for col in result[1]]
            return column_names
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def execute_query(self,query):
        try:
            # 执行查询
            result = self.db.execute(query)
            if not result :
                return None
            elif not result:
                raise CustomException("查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)
            return result
        except Exception as e:
            if isinstance(e, CustomException):
                raise
            else:
                raise CustomException(f"查询执行失败: {str(e)}", code=Status.HTTP_404_NOT_FOUND)

    async def begin_transaction(self):
        """开启多表事务 - 设置会话ID"""
        self.session_id = f"multi_table_tx_{int(time.time() * 1000)}"
        logger.info(f"[多表事务] 开启事务，会话ID: {self.session_id}")

    async def commit_transaction(self):
        """提交多表事务 - 清理会话"""
        if self.session_id:
            logger.info(f"[多表事务] 提交事务，会话ID: {self.session_id}")
            self.session_id = None


    async def rollback_transaction(self):
        """回滚多表事务 - 取消未提交的操作"""
        if self.session_id:
            logger.info(f"[多表事务] 回滚事务，会话ID: {self.session_id}")
            self.session_id = None

    def format_value_for_sql(self,value):
        """格式化值为SQL格式"""
        if value is None:
            return 'NULL'
        elif isinstance(value, str):
            # 对字符串进行转义处理
            escaped_value = value.replace("'", "''")
            return f"'{escaped_value}'"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # 其他类型转换为字符串并用引号包围
            return f"'{str(value)}'"

    async def get_black_datas(
            self,
            _id: str = None,
    ) -> dict | None:
        manager = ClickHouseManage(self.db, "")
        sql = "select * from ai_security.v_ods_communication_driver_behavior_week_20251231"
        datas = await manager.get_data_sql_dict(sql)
        return datas

    async def optimize_and_fetch(self, query:str, columns: List[str] = None) -> pd.DataFrame:
        """优化策略下的数据获取主方法"""
        try:
            # 构建基础查询
            base_query=query

            print("开始优化读取大数据集...")

            # 首先尝试流式读取
            print("尝试流式读取...")
            df = self.fetch_data_streaming(base_query, columns,batch_size=100000)

            # # 如果流式读取失败或数据量不大，使用并行分区读取
            # if df.empty or len(df) < 1000000:  # 100万行以下使用并行
            #     print("切换到并行分区读取...")
            #     df = self.parallel_fetch_partitioned(base_query, 50000000, partitions=2)

            return df

        except Exception as e:
            logger.error(f"优化读取过程中发生错误: {e}")
            return pd.DataFrame()

    def fetch_data_streaming(self, query: str, columns: List[str] = None, batch_size: int = 100000) -> pd.DataFrame:
        """流式读取数据，减少内存占用"""
        try:
            with self.db as client:
                # 使用迭代器逐行读取数据
                result_iterator = client.execute_iter(query)
                batches = []
                current_batch = []
                row_count = 0

                for row in result_iterator:
                    current_batch.append(row)
                    row_count += 1

                    # 当达到批次大小时，处理当前批次
                    if len(current_batch) >= batch_size:
                        batch_df = pd.DataFrame(current_batch, columns=columns)
                        batches.append(batch_df)
                        current_batch = []  # 重置批次

                        # 显示进度信息
                        if row_count % (batch_size * 10) == 0:
                            print(f"已处理 {row_count} 行数据...")
                            import gc
                            gc.collect()

                # 处理最后一个不完整的批次
                if current_batch:
                    if columns:
                        batch_df = pd.DataFrame(current_batch, columns=columns)
                    else:
                        batch_df = pd.DataFrame(current_batch)
                    batches.append(batch_df)

                # 合并所有批次
                if batches:
                    final_df = pd.concat(batches, ignore_index=True)
                    print(f"流式读取完成，总计 {len(final_df)} 行数据")
                    # 清理临时变量
                    del batches, current_batch
                    import gc
                    gc.collect()
                    return final_df
                else:
                    return pd.DataFrame()

        except Exception as e:
            logger.error(f"流式读取数据时发生错误: {e}")
            return pd.DataFrame()


async def main():
    # 初始化ClickHouse客户端
    client = Client(host='117.72.212.82', port=9000, database='ai_security',user='default',password='Zhongda@84')

    # 创建管理实例
    # manager = ClickHouseManage(client, "obs_baseinfo_can")

    # 读取CSV文件
    df = pd.read_csv('../utils/baseinfo_can.csv')

    # 数据类型转换（根据需要）
    # df['id'] = df['id'].astype('int32')
    # df['date'] = df['moudle']).dt.date
    # df['value'] = df['value'].astype('float64')

    # df['moudle'] = df['moudle']
    # df['id'] = df['id']
    # df['data_name'] = df['data_name']

    # 批量插入数据
    client.insert_dataframe(
        "INSERT INTO obs_baseinfo_can VALUES",
        df,
        settings={'use_numpy': True}
    )

    # try:
    #     # 创建数据
    #     new_data = {
    #         "id": int(datetime.datetime.now().timestamp() * 1000),
    #         "name": "测试数据",
    #         "age": 34
    #     }
    #     # result = await manager.create_data(new_data)
    #
    #     result = await manager.insert_data_fixed(new_data)
    #     print("创建结果:", result)
    #
    #     # 查询数据
    #     datas = await manager.get_datas(limit=5)
    #     print("查询结果:", datas)
    #
    #     # 获取总数
    #     count = await manager.get_count()
    #     print("数据总数:", count)
    #
    # except CustomException as e:
    #     print(f"错误: {e.message}, 状态码: {e.code}")

if __name__ == "__main__":
    asyncio.run(main())
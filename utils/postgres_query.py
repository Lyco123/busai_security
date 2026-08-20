import psycopg2
import pandas as pd
from typing import Dict, List, Any, Tuple
import json
import sys

from application.settings import DB_CONFIG


class PostgreSQLQuery:
    def __init__(self):
        """
        初始化PostgreSQL连接参数
        :param host: 数据库主机地址
        :param port: 数据库端口号
        :param database: 数据库名称
        :param user: 用户名
        :param password: 密码
        """
        # db_config = {
        #     'host': '127.0.0.1',
        #     'port': 5432,
        #     'database': 'zhongda_map',
        #     'user': 'postgres',
        #     'password': 'jinqi2016'
        # }
        self.connection_params = {
            'host': DB_CONFIG['host'],
            'port': DB_CONFIG['port'],
            'database': DB_CONFIG['database'],
            'user': DB_CONFIG['user'],
            'password': DB_CONFIG['password']
        }
        self.connection = None
        # self.current_schema = DB_CONFIG['schema']

    def connect(self, schema: str = None) -> bool:
        """
        建立数据库连接
        :param schema: 可选的数据库模式
        :return: 连接是否成功
        """
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.current_schema = schema

            # 如果指定了模式，则设置search_path
            if schema:
                with self.connection.cursor() as cursor:
                    cursor.execute(f"SET search_path TO {schema}")

            print("数据库连接成功")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        """
        关闭数据库连接
        """
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        执行SQL查询并返回结果
        :param query: SQL查询语句
        :param params: 查询参数
        :return: 查询结果列表
        """
        if not self.connection:
            print("请先建立数据库连接")
            return []

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)

            # 获取列名
            columns = [desc[0] for desc in cursor.description]

            # 获取数据
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))

            cursor.close()
            print(f"查询成功，返回 {len(result)} 条记录")
            return result

        except Exception as e:
            print(f"查询执行失败: {e}")
            return []

    def execute_query_to_dataframe(self, query: str, params: tuple = None, schema: str = None) -> pd.DataFrame:
        """
        执行SQL查询并返回pandas DataFrame（支持模式选择）
        :param query: SQL查询语句
        :param params: 查询参数
        :param schema: 可选的数据库模式
        :return: DataFrame结果
        """
        if not self.connection:
            print("请先建立数据库连接")
            return pd.DataFrame()

        # 临时设置模式（如果指定了）
        original_schema = None
        try:
            # 如果指定了模式且与当前模式不同，则临时切换
            if schema and schema != self.current_schema:
                original_schema = self.current_schema
                with self.connection.cursor() as cursor:
                    cursor.execute(f"SET search_path TO {schema}")
                self.current_schema = schema

            # 执行查询
            df = pd.read_sql_query(query, self.connection, params=params)
            print(f"查询成功，返回 {len(df)} 行数据")
            return df

        except Exception as e:
            print(f"查询执行失败: {e}")
            return pd.DataFrame()
        finally:
            # 恢复原始模式（如果需要）
            if original_schema is not None:
                try:
                    with self.connection.cursor() as cursor:
                        cursor.execute(f"SET search_path TO {original_schema}")
                    self.current_schema = original_schema
                except:
                    pass

    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        执行更新操作（INSERT/UPDATE/DELETE）
        :param query: SQL更新语句
        :param params: 更新参数
        :return: 影响的行数
        """
        if not self.connection:
            print("请先建立数据库连接")
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            print(f"更新成功，影响 {affected_rows} 行")
            return affected_rows
        except Exception as e:
            self.connection.rollback()
            print(f"更新失败: {e}")
            return 0

    def execute_update_batch(self, query: str, data: List[Tuple]) -> int:
        """
        执行批量更新操作（INSERT/UPDATE/DELETE）
        :param query: SQL更新语句
        :param data: 批量数据列表
        :return: 影响的行数
        """
        if not self.connection:
            print("请先建立数据库连接")
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, data)
            self.connection.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            print(f"批量更新成功，影响 {affected_rows} 行")
            return affected_rows
        except Exception as e:
            self.connection.rollback()
            print(f"批量更新失败: {e}")
            return 0

    def execute_update_sql(self, query: str) -> int:
        """
        执行更新操作（INSERT/UPDATE/DELETE）
        :param query: SQL更新语句
        :param params: 更新参数
        :return: 影响的行数
        """
        if not self.connection:
            print("请先建立数据库连接")
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            self.connection.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            print(f"更新成功，影响 {affected_rows} 行")
            return affected_rows
        except Exception as e:
            self.connection.rollback()
            print(f"更新失败: {e}")
            return 0

def main():
    """
    主函数 - 演示PostgreSQL查询功能
    """
    # 数据库连接配置
    db_config = {
        'host': '127.0.0.1',
        'port': 5432,
        'database': 'zhongda_map',
        'user': 'postgres',
        'password': 'jinqi2016'
    }

    # 创建查询对象
    db_query = PostgreSQLQuery()

    # 连接数据库（可指定默认模式）
    if not db_query.connect(schema='bus_ai'):
        return

    try:
        # 示例查询1: 使用默认模式查询
        print("\n=== 使用默认模式查询用户 ===")
        users = db_query.execute_query("SELECT * FROM line_range LIMIT 5")
        for user in users:
            print(user)

        # # 示例查询2: 临时切换到其他模式查询
        # print("\n=== 临时切换模式查询 ===")
        # df = db_query.execute_query_to_dataframe(
        #     "SELECT * FROM some_table LIMIT 5",
        #     schema='other_schema'  # 临时使用other_schema模式
        # )
        # print(df.head() if not df.empty else "无数据")
        #
        # # 示例查询3: 带参数查询
        # print("\n=== 根据ID查询用户 ===")
        # user = db_query.execute_query(
        #     "SELECT * FROM users WHERE id = %s",
        #     (1,)
        # )
        # print(user)

    except Exception as e:
        print(f"操作过程中出现错误: {e}")
    finally:
        # 关闭连接
        db_query.disconnect()



if __name__ == "__main__":
    main()

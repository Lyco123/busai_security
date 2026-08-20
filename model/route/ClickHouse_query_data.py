import clickhouse_driver
import pandas as pd
import argparse
import sys
from application.settings import CLICKHOUSE_HOST,CLICKHOUSE_PORT,CLICKHOUSE_USER,CLICKHOUSE_PASSWORD,CLICKHOUSE_DATABASE,CLICKHOUSE_NAME
from model.vehicle_old.src.utils.common import get_default_attr


# 连接ClickHouse数据库读取表数据并且转换成dataframe
async def connect_to_clickhouse(host: str, port: int, database: str, user: str, password: str) -> clickhouse_driver.Client:
    client = clickhouse_driver.Client(
        host=host, port=port, database=database, user=user, password=password
    )
    return client

async def execute_query_and_export(client: clickhouse_driver.Client, query: str):
    try:
        print(f"执行查询: {query}")
        result = client.execute(query, with_column_types=True)
        if not result[0]:
            print("查询返回空结果")
            return
        column_names = [col[0] for col in result[1]]
        data = result[0]
        return column_names, data
    except Exception as e:
        print(f"导出过程中发生错误: {str(e)}")
        raise
    finally:
        client.disconnect()
        client = None

def parse_date_range_args(description: str, default_args=None, include_weight_month: bool = False):
    parser = argparse.ArgumentParser(description=description)
    # 创建子解析器
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    # 添加 'run' 子命令
    run_parser = subparsers.add_parser("run", help="Run the data processing task")
    # 为 'run' 子命令添加参数
    run_parser.add_argument(
        "--host",
        type=str,
        default=get_default_attr(default_args, "host"),
        required=False,  # 在子命令中，通常设为非必填，或在逻辑中检查
        help="ClickHouse服务器地址",
    )
    run_parser.add_argument(
        "--port",
        type=str,
        default=get_default_attr(default_args, "port"),
        required=False,
        help="ClickHouse服务器端口",
    )
    run_parser.add_argument(
        "--database",
        type=str,
        default=get_default_attr(default_args, "database"),
        required=False,
        help="数据库名",
    )
    run_parser.add_argument(
        "--user",
        type=str,
        default=get_default_attr(default_args, "user"),
        required=False,
        help="用户名",
        )
    run_parser.add_argument(
        "--password",
        type=str,
        default=get_default_attr(default_args, "password"),
        required=False,
        help="密码",
        )
    run_parser.add_argument(
        "--query",
        type=str,
        default=get_default_attr(default_args, "query"),
        required=False,
        help="要执行的SQL查询语句",
        )
    args = parser.parse_args()
    return args

# 【仅微调这部分：将默认query改为动态拼接table_name】
async def query(table_name):
    default_args = argparse.Namespace()
    default_args.host = CLICKHOUSE_HOST
    default_args.port = CLICKHOUSE_PORT
    default_args.database = CLICKHOUSE_DATABASE
    default_args.user = CLICKHOUSE_USER
    default_args.password=CLICKHOUSE_PASSWORD
    default_args.query=f'select * from {table_name};'
    args=parse_date_range_args("ClickHouse数据导出到CSV工具", default_args=default_args, include_weight_month=True)
    # parser = argparse.ArgumentParser(description='ClickHouse数据导出到CSV工具')
    # parser.add_argument('--host', default=CLICKHOUSE_HOST, help='ClickHouse服务器地址')
    # parser.add_argument('--port', type=int, default=CLICKHOUSE_PORT, help='ClickHouse服务器端口')
    # parser.add_argument('--database', default=CLICKHOUSE_DATABASE, help='数据库名')
    # parser.add_argument('--user', default=CLICKHOUSE_USER, help='用户名')
    # parser.add_argument('--password', default=CLICKHOUSE_PASSWORD, help='密码')
    # # 核心修改：默认查询改为「select * from 传入的table_name」，摒弃原固定视图
    # parser.add_argument('--query', default=f'select * from {table_name}', help='要执行的SQL查询语句')


    # args = parser.parse_args()
    try:
        client = await connect_to_clickhouse(
            host=args.host, port=args.port, database=args.database, user=args.user, password=args.password
        )
        column_names, data = await execute_query_and_export(client=client, query=args.query)
        return column_names, data
    except Exception as e:
        print(f"程序执行失败: {str(e)}")
        sys.exit(1)

async def main(table_name):
    column_names, data = await query(table_name)
    df = pd.DataFrame(data, columns = column_names)
    return df


if __name__ == '__main__':
    df = main('ads_line_cardtype_flow_daily')
    print(df)
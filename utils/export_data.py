import clickhouse_driver
import csv
import argparse
import sys


def connect_to_clickhouse(host: str, port: int, database: str, user: str, password: str) -> clickhouse_driver.Client:
    """
    建立ClickHouse数据库连接
    """
    client = clickhouse_driver.Client(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    return client


def execute_query_and_export(client: clickhouse_driver.Client, query: str, output_file: str) -> None:
    """
    执行查询并将结果导出到CSV文件
    """
    try:
        print(f"执行查询: {query}")
        # 执行查询并获取列信息

        result = client.execute(query, with_column_types=True)

        if not result[0]:
            print("查询返回空结果")
            return

        # 获取列名和数据
        column_names = [col[0] for col in result[1]]
        data = result[0]

        # 写入CSV文件
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # 写入表头
            writer.writerow(column_names)

            # 写入数据行
            writer.writerows(data)

        print(f"成功导出 {len(data)} 行数据到 {output_file}")

    except Exception as e:
        print(f"导出过程中发生错误: {str(e)}")
        raise


def main():
    """
    主函数 - 处理命令行参数并执行导出操作
    """
    parser = argparse.ArgumentParser(description='ClickHouse数据导出到CSV工具')
    parser.add_argument('--host', default='117.72.212.82', help='ClickHouse服务器地址 (默认: localhost)')
    parser.add_argument('--port', type=int, default=9000, help='ClickHouse服务器端口 (默认: 9000)')
    parser.add_argument('--database', default='ai_security', help='数据库名 (默认: default)')
    parser.add_argument('--user', default='default', help='用户名 (默认: default)')
    parser.add_argument('--password', default='Zhongda@84', help='密码 (默认: 空)')
    parser.add_argument('--query', default='select * from canbus.ods_jituan_bs_bus', help='要执行的SQL查询语句')
    parser.add_argument('--output', default='ods_jituan_bs_bus.csv', help='输出CSV文件路径')

    args = parser.parse_args()

    try:
        # 建立数据库连接
        client = connect_to_clickhouse(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )

        # 执行查询并导出数据
        execute_query_and_export(
            client=client,
            query=args.query,
            output_file=args.output
        )

        print("数据导出完成")

    except Exception as e:
        print(f"程序执行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

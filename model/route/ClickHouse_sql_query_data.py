import clickhouse_driver
import pandas as pd
from application.settings import CLICKHOUSE_HOST,CLICKHOUSE_PORT,CLICKHOUSE_USER,CLICKHOUSE_PASSWORD,CLICKHOUSE_DATABASE,CLICKHOUSE_NAME



# 1. 数据库连接函数 (保持原样)
def connect_to_clickhouse(host: str, port: int, database: str, user: str, password: str) -> clickhouse_driver.Client:
    client = clickhouse_driver.Client(
        host=host, port=port, database=database, user=user, password=password
    )
    return client


# 2. 核心执行函数 (接收 SQL 并返回 DataFrame)
async def query_to_dataframe(sql_query: str,
                       host: str = CLICKHOUSE_HOST,
                       port: int = CLICKHOUSE_PORT,
                       database: str = CLICKHOUSE_DATABASE,
                       user: str = CLICKHOUSE_USER,
                       password: str = CLICKHOUSE_PASSWORD) -> pd.DataFrame:
    """
    执行传入的 SQL 查询语句，并将结果直接转换为 Pandas DataFrame

    参数:
        sql_query: 完整的 SQL 查询语句
        host, port, database, user, password: 数据库连接信息 (有默认值)

    返回:
        pd.DataFrame: 查询结果的数据框
    """
    try:
        # 建立连接
        client = connect_to_clickhouse(host, port, database, user, password)

        print(f"正在执行查询:\n{sql_query[:100]}...")  # 打印前100个字符以防SQL过长

        # 执行查询 (with_column_types=True 用于获取列名)
        result = client.execute(sql_query, with_column_types=True)

        # 解析结果: result[0]是数据行, result[1]是列类型信息
        rows = result[0]
        columns_info = result[1]

        if not rows:
            print("警告：查询返回空结果集")
            return pd.DataFrame()

        # 提取列名
        column_names = [col[0] for col in columns_info]

        # 转换为 DataFrame
        df = pd.DataFrame(rows, columns=column_names)

        print(f"查询成功！返回 {len(df)} 行数据, 列: {column_names}")
        return df

    except Exception as e:
        print(f"数据库查询发生错误: {str(e)}")
        raise
    finally:
        client.disconnect()
        client = None


# ==========================================
# 【使用示例】
# ==========================================
if __name__ == '__main__':
    # 驾驶行为序号名称对应字典
    behavior_dict = {
        1: '起步急加速',
        2: '急加速',
        3: '急减速',
        4: '急刹车',
        5: '斑马线不文明礼让',
        6: '斑马线超速',
        7: '违规使用手刹',
        8: '停站N档违规',
        9: '违规使用N档',
        10: '不规范转弯',
        11: '车辆未停稳开车门',
        12: '车辆起步不关车门',
        13: '空档滑行',
        14: '熄火滑行',
        15: '不文明鸣笛',
        16: '安全带行为',
        17: '不规范进站',
        18: '不规范出站',
        19: '急停',
        20: '门开禁启开关',
        21: '停车不挂N挡',
        22: '不规范开关门',
        23: '安全启动',
        24: '违规使用空调',
        25: '平路不规范行为',
        26: '上坡不规范行为',
        27: '下坡不规范行为',
        28: '违规使用总电',
        29: '路口大油门',
        30: '进站违规制动',
        33: '区间超速',
        34: '全局超速',
        36: '左转弯未刹车',
        37: '右转弯未刹车'
    }
    # 定义您的复杂 SQL 语句
    my_sql = """
    select * from ai_security.obs_quota_weight_configuration 
    where quota_id2='驾驶员画像-事故风险-不良行为'
    and start_time in (
        select max(start_time) from ai_security.obs_quota_weight_configuration 
        where quota_id2='驾驶员画像-事故风险-不良行为' and deleted!='1'
    )
    """

    # 调用函数获取 DataFrame
    try:
        df_result = query_to_dataframe(my_sql)

        # 查看结果
        print("\n--- 查询结果预览 ---")
        print(df_result.head())
        # 这里可以继续后续的数据处理...
        # 例如: df_result.to_csv('result.csv', index=False)

    except Exception as e:
        print(f"程序执行终止: {e}")
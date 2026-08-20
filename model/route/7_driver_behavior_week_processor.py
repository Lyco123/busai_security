from datetime import datetime, timedelta
import asyncio
from model.route import ClickHouse_query_data
import pandas as pd
from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud
import importlib
driver_behavior_top10_weight_calculator = importlib.import_module("model.route.13_read_route_quota_weight")

def process_dataframe(df, CONFIG):
    """
    处理DataFrame：删除列名后缀_count，提取指定列，删除route_id为空的行
    参数:
        df: 输入的DataFrame，包含route_id和带_count后缀的report_type列
    返回:处理后的DataFrame，包含route_id和指定的report_type列（无_count后缀），已删除route_id为空的行
    """
    # 创建副本以避免修改原数据
    df_processed = df.copy()

    # 1. 重命名列：删除_count后缀
    new_columns = {}
    for col in df_processed.columns:
        if col.endswith('_count'):
            new_columns[col] = col.replace('_count', '')
        else:
            new_columns[col] = col

    df_processed = df_processed.rename(columns=new_columns)

    # 2. 获取配置中的列名
    route_id_col = CONFIG['route_id_column']
    report_type_cols = CONFIG['report_type_columns']

    # 3. 合并所有需要的列
    required_columns = [route_id_col] + report_type_cols

    # 4. 检查所需列是否都存在于DataFrame中
    missing_columns = []
    for col in required_columns:
        if col not in df_processed.columns:
            missing_columns.append(col)

    if missing_columns:
        print(f"警告: 以下列不存在于数据中: {missing_columns}")
        # 只提取存在的列
        existing_route_id_cols = [col for col in [route_id_col] if col in df_processed.columns]
        existing_report_type_cols = [col for col in report_type_cols if col in df_processed.columns]
        existing_columns = existing_route_id_cols + existing_report_type_cols
    else:
        existing_columns = required_columns

    # 5. 提取指定列
    result_df = df_processed[existing_columns].copy()

    # 6. 删除route_id列为空的行
    initial_row_count = len(result_df)
    result_df = result_df.dropna(subset=[route_id_col])
    final_row_count = len(result_df)

    print(f"处理完成:")
    print(f"- 原始列数: {len(df.columns)}")
    print(f"- 处理后列数: {len(result_df.columns)}")
    print(f"- 处理后列名: {list(result_df.columns)}")
    print(f"- 删除{route_id_col}为空的行数: {initial_row_count - final_row_count}")
    print(f"- 最终数据行数: {len(result_df)}")
    print(result_df.head())

    return result_df


async def main(start_time,day):
    try:
        async with await connect_to_clickhouse() as client:
            # 配置参数模块
            CONFIG = {
                'route_id_column': 'route_id',
                'report_type_columns': []
            }
            # 从线路画像所有指标权重数据库中取出10种权重最大的驾驶行为的report_type，传入CONFIG['report_type_columns']
            dict1, report_type_columns_list = await driver_behavior_top10_weight_calculator.main(start_time)
            CONFIG['report_type_columns'] = report_type_columns_list

            start_date_ = start_time
            # 计算结束日期
            end_date_ = start_date_ + timedelta(days=day)
            start_date_str = start_date_.strftime('%Y%m%d')
            end_date_str = end_date_.strftime('%Y%m%d')
            # 连接数据库并读取相应的数据表
            driver_behavior_week_df = await crud.Route(client).get_driver_behavior_week_df("",start_date_str, end_date_str)
            # driver_behavior_week_df = ClickHouse_query_data.main('v_ods_communication_driver_bus_behavior_route_week_sum')
            print(f"原始数据形状: {driver_behavior_week_df.shape}")
            print(f"原始列名: {list(driver_behavior_week_df.columns)}")

            # 处理DataFrame
            result_df = process_dataframe(driver_behavior_week_df, CONFIG)

            return result_df
    except Exception as e:
        print(f"线路画像风险计算分数执行出错: {e}")

# 主程序
if __name__ == "__main__":
    # 示例 使用 asyncio.run 启动异步主函数
    print('1')


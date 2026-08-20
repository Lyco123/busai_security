# 不同线路的车辆故障总数统计
from datetime import datetime, timedelta
import asyncio
from model.route import ClickHouse_query_data
import pandas as pd
from core.logger import logger

from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud


def process_fault_type_data(df):
    """
    处理线路故障类型数据：提取route_id列和包含'fault_type'的列，计算总和
    参数:
        df: 输入的DataFrame，包含route_id和fault_type相关的列
    返回:处理后的DataFrame，包含route_id列和各故障类型列的总和
    """
    # 创建副本以避免修改原数据
    df_processed = df.copy()

    # 1. 查找包含'fault_type'的列
    fault_type_columns = [col for col in df_processed.columns if 'fault_type' in col.lower()]

    # 2. 确保route_id列存在
    if 'route_id' not in df_processed.columns:
        raise ValueError("数据中不包含 'route_id' 列")

    # 3. 构建要提取的列列表
    columns_to_extract = ['route_id'] + fault_type_columns

    # 4. 检查是否有包含'fault_type'的列
    if not fault_type_columns:
        print("警告: 数据中没有找到包含 'fault_type' 的列")
        return df_processed[['route_id']].copy()

    print(f"找到 {len(fault_type_columns)} 个包含 'fault_type' 的列: {fault_type_columns}")

    # 5. 提取指定列
    result_df = df_processed[columns_to_extract].copy()

    # 6. 确保所有故障类型列都是数值类型
    for col in fault_type_columns:
        result_df[col] = pd.to_numeric(result_df[col], errors='coerce').fillna(0)

    # 7. 计算每个route_id的故障类型总和
    result_df['总故障次数'] = result_df[fault_type_columns].sum(axis=1)

    print(f"处理完成:")
    print(f"- 提取的故障类型列数: {len(fault_type_columns)}")
    print(f"- 处理后数据形状: {result_df.shape}")
    print(f"- 包含列: {list(result_df.columns)}")
    print(result_df.head())

    return result_df


async def main(start_time,day):
    try:
        async with await connect_to_clickhouse() as client:
            # 解析开始日期
            start_date_ = start_time
            # 计算结束日期
            end_date_ = start_date_ + timedelta(days=day)

            start_date_str = start_date_.strftime('%Y%m%d')
            end_date_str = end_date_.strftime('%Y%m%d')
            fault_analysis_week_df = await crud.Route(client).get_fault_analysis_week_df('',start_date_str,end_date_str)
            # fault_analysis_week_df = ClickHouse_query_data.main('v_ads_fault_analysis_route_week_sum')
            try:
                # 执行透视表生成
                result_df = process_fault_type_data(fault_analysis_week_df)
                return result_df
            except Exception as e:
                print(f"\n错误: {str(e)}")
                print("请检查配置参数和输入文件路径")
                print("=" * 80)
                exit(1)

    except Exception as e:
        logger.error("线路画像不同线路的车辆故障总数统计主程序执行出错", exc_info=True)
        print(f"线路画像不同线路的车辆故障总数统计主程序执行出错: {e}")
    print("数据库连接已关闭")


if __name__ == "__main__":
    start_time = '2026-01-14'
    line_fault_week_df = asyncio.run(main(start_time, 6))

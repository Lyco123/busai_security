# 处理线路车辆里程数据，修正异常值并汇总每条线路的里程
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import numpy as np
import os
from model.route import ClickHouse_query_data
from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud


def process_mileage_data(triplog_energy_week_df, route_id_col='route_id', run_mileage_can_col='run_mileage_can',
                         run_mileage_col='run_mileage'):
    """
    处理线路车辆里程数据，修正异常值并汇总
    route_id_col: 线路ID列名 (默认: 'route_id')
    run_mileage_can_col: CAN里程列名 (默认: 'run_mileage_can')
    run_mileage_col: 运行里程列名 (默认: 'run_mileage')
    """
    # 读取数据
    try:
        df = triplog_energy_week_df.copy()
        print(f"成功读取文件，共 {len(df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取文件失败: {str(e)}")

    # 检查必要列是否存在
    missing_cols = []
    if route_id_col not in df.columns:
        missing_cols.append(route_id_col)
    if run_mileage_can_col not in df.columns:
        missing_cols.append(run_mileage_can_col)
    if run_mileage_col not in df.columns:
        missing_cols.append(run_mileage_col)

    if missing_cols:
        raise ValueError(f"缺少必要列: {', '.join(missing_cols)}")

    # 确保里程列是数值类型
    df[run_mileage_can_col] = pd.to_numeric(df[run_mileage_can_col], errors='coerce')
    df[run_mileage_col] = pd.to_numeric(df[run_mileage_col], errors='coerce')

    # 处理空值：删除空值行
    initial_count = len(df)
    df = df.dropna(subset=[run_mileage_can_col, run_mileage_col])
    print(f"已删除 {initial_count - len(df)} 行空值记录")

    # 新增"修正can里程"列
    print("正在计算修正CAN里程...")
    # 创建条件：CAN里程在运行里程的±10%范围内
    condition = (
            (df[run_mileage_can_col] >= df[run_mileage_col] * 0.9) &
            (df[run_mileage_can_col] <= df[run_mileage_col] * 1.1)
    )

    # 应用条件：在范围内用CAN里程，否则用运行里程
    df['修正can里程'] = np.where(
        condition,
        df[run_mileage_can_col],
        df[run_mileage_col]
    )

    # 检查异常值处理结果
    in_range_count = condition.sum()
    out_of_range_count = len(df) - in_range_count
    print(f"异常值处理结果:")
    print(f"  - CAN里程在范围内: {in_range_count} 条记录")
    print(f"  - CAN里程在范围外: {out_of_range_count} 条记录")

    # 以route_id为索引，对修正can里程求和
    mileage_summary = df.groupby(route_id_col)['修正can里程'].sum().reset_index()
    mileage_summary = mileage_summary.rename(columns={'修正can里程': '总修正里程'})

    print(f"\n里程汇总完成，共 {len(mileage_summary)} 条线路数据")

    # 生成统计摘要
    print(f"总线路数: {len(mileage_summary)}")

    return mileage_summary

async def main(start_time,day):
    # 加载配置
    try:
        async with (await connect_to_clickhouse() as client):
            CONFIG = {
                'route_id_col': 'route_id',  # 线路ID列名
                'run_mileage_can_col': 'run_mileage_can',  # CAN里程列名
                'run_mileage_col': 'run_mileage'  # 运行里程列名
            }
            # 解析开始日期
            start_date_ = start_time
            # 计算结束日期
            end_date_ = start_date_ + timedelta(days=day)

            start_date_str = start_date_.strftime('%Y%m%d')
            end_date_str = end_date_.strftime('%Y%m%d')
            # 连接数据库并读取相应的数据表
            triplog_energy_week = await crud.Route(client).get_triplog_energy_week('',start_date_str,end_date_str)
            # triplog_energy_week = ClickHouse_query_data.main('v_ods_triplog_energy_week_20251231')
            try:
                # 执行里程处理与汇总
                result_df = process_mileage_data(
                    triplog_energy_week,
                    CONFIG['route_id_col'],
                    CONFIG['run_mileage_can_col'],
                    CONFIG['run_mileage_col']
                )
                print("\n任务执行成功!")
                print(f"列名: {list(result_df.columns)}")
                return result_df
            except Exception as e:
                print(f"\n错误: {str(e)}")
                print("请检查配置参数和输入文件路径")
                exit(1)


    except Exception as e:
        print(f"线路画像分数主程序执行出错: {e}")
    print("数据库连接已关闭")

# 主程序
if __name__ == "__main__":
    print('1')


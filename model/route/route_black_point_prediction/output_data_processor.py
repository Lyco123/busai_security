import pandas as pd
import numpy as np
from sklearn.neighbors import BallTree
from datetime import datetime


def filter_output_behavior_black_points(accept_df, new_df, dist_threshold):
    """过滤掉与 现有黑点和最近一个月内的拒接黑点 距离过近的新点（距离 ≤ dist_threshold 米则拒绝）"""

    if accept_df.empty or new_df.empty:  # 处理空数据
        return new_df.copy()

    # 提取坐标并转换为弧度（BallTree 的 haversine 距离需要弧度）
    accept_df['longitude'] = pd.to_numeric(accept_df['longitude'])
    accept_df['latitude'] = pd.to_numeric(accept_df['latitude'])
    new_df['longitude'] = pd.to_numeric(new_df['longitude'])
    new_df['latitude'] = pd.to_numeric(new_df['latitude'])

    existing_coords = np.radians(accept_df[['latitude', 'longitude']].values)
    new_coords = np.radians(new_df[['latitude', 'longitude']].values)

    # 构建 BallTree，使用 Haversine 距离
    tree = BallTree(existing_coords, metric='haversine')

    # 将阈值从米转换为弧度
    R = 6371393  # 地球半径，单位：米
    radius = dist_threshold / R

    # 查询每个新点在半径内的现有点数量, count_only=True 时只返回计数
    counts = tree.query_radius(new_coords, r=radius, count_only=True)

    # 保留计数为 0 的新点（即半径内没有现有黑点）
    keep_indices = np.where(counts == 0)[0]

    return new_df.iloc[keep_indices].reset_index(drop=True)


def filter_output_black_points(new_df, filter_df, dist_threshold):
    if filter_df.empty or new_df.empty:  # 如果任一 DataFrame 为空，直接返回 new_df
        return new_df.copy()

    # 将 filter_df 按 (route_id, report_type) 分组，构建快速查找字典
    filter_df_dict = {}
    for (rid, tp), group in filter_df.groupby(['route_id', 'report_type']):
        filter_df_dict[(rid, tp)] = group

    results = []
    # 遍历 new_df 的每个分组
    for (rid, tp), new_part in new_df.groupby(['route_id', 'report_type']):
        filter_part = filter_df_dict.get((rid, tp), pd.DataFrame())  # 获取对应的 filter 分组（若无则为空 DataFrame）
        temp = filter_output_behavior_black_points(filter_part, new_part, dist_threshold)  # 调用过滤函数
        if not temp.empty:
            results.append(temp)
    # 合并所有结果
    if results:
        return pd.concat(results, axis=0, ignore_index=True)
    else:
        return pd.DataFrame()


if __name__ == "__main__":
    distance_threshold = 30
    df1 = pd.read_csv('input_data/black_list4route_black_points.csv')
    df1['accept_statu'] = 1
    acc_df = df1.copy()
    df1['accept_statu'] = 2
    rjc_df = df1.copy()
    # df1.to_csv('input_data/black_list4route_black_points.csv')
    # df1 = pd.read_csv('input_data/4_route_data_week.csv')
    df2 = pd.read_csv('input_data/input_black_list_4route_black_points.csv')
    # df2 = pd.read_csv('input_data/all_routes_data_week(parts).csv')
    print(acc_df.to_string())
    print()
    print(df2.to_string())

    # 确保黑点列表数据类型
    accept_df = acc_df[acc_df['accept_statu'] == 1]
    # 确保是1个月内的拒绝数据
    month_reject_df = rjc_df[rjc_df['accept_statu'] == 2]
    one_month_ago = get_shanghai_time() - pd.Timedelta(days=30)  # 一个月前的时间点
    month_reject_df['calculate_date'] = pd.to_datetime(month_reject_df['calculate_date'])  # 确保为 datetime 类型
    month_reject_df = month_reject_df[month_reject_df['calculate_date'] >= one_month_ago]
    # 合并黑点列表数据和1个月内的拒绝数据
    filter_df = pd.concat([accept_df, month_reject_df], axis=0, ignore_index=True)

    fff = filter_output_black_points(df2, filter_df, distance_threshold)
    print(fff.to_string())

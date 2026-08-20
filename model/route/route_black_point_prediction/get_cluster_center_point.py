import numpy as np
import pandas as pd


def find_peaks_clustering(df, labels):
    coords = df[['longitude', 'latitude']].values

    unique_labels = list(set(labels))  # 排除噪声点 label=-1，如果存在噪声
    if -1 in unique_labels:
        unique_labels.remove(-1)

    cluster_centers = []  # 计算每个聚类的中心
    for label in unique_labels:
        cluster_points = coords[labels == label]
        center = cluster_points.mean(axis=0)
        cluster_centers.append(center)
    cluster_centers = np.array(cluster_centers)

    peaks = []
    for i, center in enumerate(cluster_centers):
        lon, lat = center
        cluster_size = np.sum(labels == list(unique_labels)[i])  # 获取聚类大小
        peaks.append({
            'longitude': lon,
            'latitude': lat,
            'cluster_size': cluster_size
        })
    pd_peaks = pd.DataFrame(peaks)  # 转换格式

    return pd_peaks


def find_peaks_clustering_with_weight(df, labels):
    coords = df[['longitude', 'latitude']].values
    weights = df['weight'].values

    unique_labels = list(set(labels))  # 排除噪声点 label=-1，如果存在噪声
    if -1 in unique_labels:
        unique_labels.remove(-1)

    peaks = []
    for label in unique_labels:
        mask = (labels == label)
        cluster_coords = coords[mask]
        cluster_weights = weights[mask]

        # 加权中心
        center_lon = np.average(cluster_coords[:, 0], weights=cluster_weights)
        center_lat = np.average(cluster_coords[:, 1], weights=cluster_weights)

        # 簇的总权重
        total_weight = cluster_weights.sum()

        peaks.append({
            'longitude': center_lon,
            'latitude': center_lat,
            'cluster_size': total_weight
        })

    return pd.DataFrame(peaks)


def haversine_distance(lat1, lon1, lat2, lon2):
    # 使用Haversine公式计算两点间距离（单位：米）
    # 将角度转换为弧度
    print(f"====={lat1}, {lon1}, {lat2}, {lon2}")
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    # Haversine公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371393  # 地球半径，单位：米
    return c * r


def count_cluster_size_nearby(checkpoint_df, accident_df, radius_m):
    checkpoint_df['longitude'] = pd.to_numeric(checkpoint_df['longitude'])
    checkpoint_df['latitude'] = pd.to_numeric(checkpoint_df['latitude'])

    df = accident_df
    df['longitude'] = pd.to_numeric(df['longitude'])
    df['latitude'] = pd.to_numeric(df['latitude'])
    # 检查必要列
    required_cols = ['longitude', 'latitude']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"数据必须包含'{col}'列")
    # 删除缺失值、保留聚类所需的经纬度数据
    df = df.dropna(subset=required_cols)
    df_clean = df.copy()
    df_clean = df_clean[(df_clean['longitude'] >= 109) & (df_clean['longitude'] <= 118) &
                        (df_clean['latitude'] >= 20) & (df_clean['latitude'] <= 26)]
    accident_df = df_clean

    counts = []
    for _, row in checkpoint_df.iterrows():
        # 筛选同线路、同类别的事故
        mask = (accident_df['route_id'] == row['route_id']) & \
               (accident_df['report_type'] == row['report_type'])
        sub = accident_df[mask]

        if sub.empty:
            counts.append(0)
            continue

        # 批量计算距离
        dists = haversine_distance(row['latitude'], row['longitude'],
                                   sub['latitude'].values, sub['longitude'].values)
        counts.append(np.sum(dists <= radius_m))

    result = checkpoint_df.copy()
    result['now_size'] = counts
    return result


def count_acc_cluster_size_nearby(checkpoint_df, accident_df, radius_m):
    checkpoint_df['longitude'] = pd.to_numeric(checkpoint_df['longitude'])
    checkpoint_df['latitude'] = pd.to_numeric(checkpoint_df['latitude'])

    df = accident_df
    df['longitude'] = pd.to_numeric(df['longitude'])
    df['latitude'] = pd.to_numeric(df['latitude'])
    # 检查必要列
    required_cols = ['longitude', 'latitude']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"数据必须包含'{col}'列")
    # 删除缺失值、保留聚类所需的经纬度数据
    df = df.dropna(subset=required_cols)
    df_clean = df.copy()
    df_clean = df_clean[(df_clean['longitude'] >= 109) & (df_clean['longitude'] <= 118) &
                        (df_clean['latitude'] >= 20) & (df_clean['latitude'] <= 26)]
    accident_df = df_clean

    # 提前将列表转为set
    accident_df = accident_df.copy()
    accident_df['report_type_set'] = accident_df['accident_types'].apply(set)

    counts = []
    for _, row in checkpoint_df.iterrows():
        mask = (accident_df['route_id'] == row['route_id']) & \
               accident_df['report_type_set'].apply(lambda s: row['report_type'] in s)
        sub = accident_df[mask]

        if sub.empty:
            counts.append(0)
            continue

        dists = haversine_distance(
            row['latitude'], row['longitude'],
            sub['latitude'].values, sub['longitude'].values
        )
        counts.append(np.sum(dists <= radius_m))

    result = checkpoint_df.copy()
    result['now_size'] = counts
    return result

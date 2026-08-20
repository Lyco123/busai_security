from sklearn.cluster import DBSCAN
import numpy as np
import pandas as pd


def merge_close_points(df, distance_threshold):
    # 合并距离小于阈值的点，cluster_size相加
    # 使用 DBSCAN 聚类（min_samples=1）快速找到所有连通簇，并计算每个簇的中心和总 cluster_size。
    if df.empty:
        return df.copy()

    R = 6371393  # 地球半径，单位：米

    # 提取坐标并转换为弧度（DBSCAN 的 haversine 距离要求输入弧度）
    coords = np.radians(df[['latitude', 'longitude']].values)  # 注意列顺序：纬度, 经度

    # 使用 DBSCAN 进行聚类。eps 需要转换为弧度，min_samples=1 确保所有点都被分配到簇（无噪声点）
    eps_rad = distance_threshold / R
    clustering = DBSCAN(eps=eps_rad, min_samples=1, metric='haversine')
    labels = clustering.fit_predict(coords)

    # 根据标签分组，计算每个簇的中心和总 cluster_size
    df['cluster_label'] = labels

    # 向量化加权平均
    sum_lon = df.groupby('cluster_label').apply(lambda g: (g['longitude'] * g['cluster_size']).sum())
    sum_lat = df.groupby('cluster_label').apply(lambda g: (g['latitude'] * g['cluster_size']).sum())
    total_weight = df.groupby('cluster_label')['cluster_size'].sum()
    lon_weighted = sum_lon / total_weight
    lat_weighted = sum_lat / total_weight
    result = pd.DataFrame(
        {'longitude': lon_weighted, 'latitude': lat_weighted, 'cluster_size': total_weight}).reset_index(drop=True)
    return result
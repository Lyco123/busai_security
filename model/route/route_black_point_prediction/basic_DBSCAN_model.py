import numpy as np
import utm
from sklearn.cluster import DBSCAN


def DBSCAN_predict(df_clean, eps_meters, min_samples):
    # 判断输入是否合理
    if min_samples < 1:
        return np.array([-1])

    # 基于经纬度的DBSCAN聚类模型
    lon = df_clean['longitude'].values
    lat = df_clean['latitude'].values

    # 1. 坐标转换
    easting, northing, _, _ = utm.from_latlon(lat, lon)  # 将WGS84经纬度批量转换为UTM坐标（东向，北向）
    coords = np.column_stack((easting, northing))  # 组合成 (n, 2) 数组

    # 2. 标准化数据（DBSCAN对尺度敏感）
    mean = coords.mean(axis=0)
    std = coords.std(axis=0)
    if np.mean(std) == 0:  # 如果所有维度的标准差均为0，则所有点坐标相同，返回1类
        return np.array([1] * len(lon))
    eps_normalized = eps_meters / np.mean(std)  # 先计算 eps_normalized（使用原始标准差，避免被后续修改影响）
    std[std == 0] = 1.0  # 将标准差为0的维度替换为1，避免后续除以0的错误.这些维度的点坐标均等于均值，缩放后变为0，符合要求
    coords_scaled = (coords - mean) / std  # 计算标准化后的坐标

    # 3. 应用DBSCAN
    dbscan = DBSCAN(
        eps=eps_normalized,
        min_samples=min_samples,
        metric='euclidean'
    )

    labels = dbscan.fit_predict(coords_scaled)
    return labels


def DBSCAN_predict_with_weight(df_clean, eps_meters, min_samples):
    """
    带权重的 DBSCAN 聚类
    """
    if min_samples < 1:
        return np.array([-1])

    weights = df_clean['weight'].values
    lon = df_clean['longitude'].values
    lat = df_clean['latitude'].values

    # 1. 坐标转换
    easting, northing, _, _ = utm.from_latlon(lat, lon)
    coords = np.column_stack((easting, northing))

    # 2. 标准化数据
    mean = coords.mean(axis=0)
    std = coords.std(axis=0)
    if np.mean(std) == 0:
        return np.array([1] * len(lon))

    eps_normalized = eps_meters / np.mean(std)
    std[std == 0] = 1.0
    coords_scaled = (coords - mean) / std

    # 3. 应用DBSCAN
    dbscan = DBSCAN(
        eps=eps_normalized,
        min_samples=min_samples,
        metric='euclidean'
    )

    labels = dbscan.fit_predict(coords_scaled, sample_weight=weights)
    return labels


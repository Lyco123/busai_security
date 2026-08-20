import numpy as np
import utm
from scipy.stats import gaussian_kde

def spatial_kde(df):
    # 执行空间核密度估计,返回:x_grid, y_grid, kde_matrix: 网格坐标和KDE矩阵

    # 提取经纬度数据
    lon = df['longitude'].values
    lat = df['latitude'].values

    # 创建网格
    x_min, x_max = lon.min(), lon.max()
    y_min, y_max = lat.min(), lat.max()

    # 扩展边界以避免边缘效应
    x_buffer = (x_max - x_min) * 0.1
    y_buffer = (y_max - y_min) * 0.1

    # 转换经纬度坐标，设置网格大小为30m左右
    lat_min, lon_min, _, _ = utm.from_latlon(y_min - y_buffer, x_min - x_buffer)
    lat_max, lon_max, _, _ = utm.from_latlon(y_max + y_buffer, x_max + x_buffer)
    x_grid_size = round((lon_max - lon_min) / 30)
    y_grid_size = round((lat_max - lat_min) / 30)
    x_grid = np.linspace(x_min - x_buffer, x_max + x_buffer, x_grid_size)
    y_grid = np.linspace(y_min - y_buffer, y_max + y_buffer, y_grid_size)
    X, Y = np.meshgrid(x_grid, y_grid)

    # 计算KDE
    positions = np.vstack([X.ravel(), Y.ravel()])
    values = np.vstack([lon, lat])

    # 使用scipy的gaussian_kde
    kernel = gaussian_kde(values, bw_method=0.01)
    Z = np.reshape(kernel(positions).T, X.shape)

    return x_grid, y_grid, Z
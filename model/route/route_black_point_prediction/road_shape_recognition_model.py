import pandas as pd
import numpy as np
import requests
import time

import application.settings

# 高德路径规划2.0-驾车路线规划 API URL
URL = ''
# 高德Web服务 key
API_KEY = ''

# QPS 限制相关配置
MAX_QPS = 3  # 最大 QPS，根据高德配额调整
SLEEP_SECONDS = 2.0 / MAX_QPS  # 等待时间


def find_endpoints_by_extremes(df):
    # 通过经纬度极值快速找到候选端点。

    # 初始化极值点
    lon_min_point = lon_max_point = lat_min_point = lat_max_point = None
    lon_min = lon_max = lat_min = lat_max = None

    for idx, row in df.iterrows():
        lon, lat = row['longitude'], row['latitude']
        # 经度极值
        if lon_min is None or lon < lon_min:
            lon_min = lon
            lon_min_point = (lon, lat)
        if lon_max is None or lon > lon_max:
            lon_max = lon
            lon_max_point = (lon, lat)
        # 纬度极值
        if lat_min is None or lat < lat_min:
            lat_min = lat
            lat_min_point = (lon, lat)
        if lat_max is None or lat > lat_max:
            lat_max = lat
            lat_max_point = (lon, lat)

    # 候选点集合（去重）
    candidates = list({lon_min_point, lon_max_point, lat_min_point, lat_max_point})

    # 计算所有候选点对的距离平方，取最远一对
    max_sq = -1
    best_pair = [candidates[0], candidates[1]]
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            dx = candidates[i][0] - candidates[j][0]
            dy = candidates[i][1] - candidates[j][1]
            sq = dx * dx + dy * dy
            if sq > max_sq:
                max_sq = sq
                best_pair = [candidates[i], candidates[j]]
    return best_pair


def get_distance_and_move_steps(origin, destination):
    parameters = {
        "origin": origin,
        "destination": destination,
        "output": "json",
        "key": API_KEY}

    response = requests.get(URL, params=parameters)
    data = response.json()

    if data['status'] == '1':
        distance = int(data['route']['paths'][0]['distance'])
        steps = data['route']['paths'][0]['steps']
        # print(distance)
        # print(steps)
        return distance, steps

    else:
        raise ValueError("Error in API response: " + data['info'])


def judge_road_shape(d1, d2, steps1, steps2):
    """
    根据两个方向的导航步骤判断道路是否为直线。返回 True 表示道路为直线，False 表示弯道
    """
    # 定义关键词
    TURN_BACK = '调头'
    TURN_LEFT = '左转'
    TURN_RIGHT = '右转'
    TURN_LEFT_SPECIAL = '左转专用道'
    TURN_RIGHT_SPECIAL = '右转专用道'

    # 选择距离较短的方向的步骤
    short_steps = steps1 if d1 < d2 else steps2

    # 检查短路径中是否有掉头指令
    has_turn_back = False
    for step in short_steps:
        if TURN_BACK in step.get('instruction', ''):
            has_turn_back = True
            break

    if not has_turn_back:  # 情况1：短路径无掉头，通过检查普通转弯判断
        for step in short_steps:
            instruction = step.get('instruction', '')
            if TURN_LEFT in instruction or TURN_RIGHT in instruction:
                return False  # 存在转弯，说明是弯道
        return True  # 无转弯，说明是直线

    else:  # 情况2：短路径有掉头，合并两个方向检查专用道
        all_steps = steps1 + steps2
        for step in all_steps:
            instruction = step.get('instruction', '')
            if TURN_LEFT_SPECIAL in instruction or TURN_RIGHT_SPECIAL in instruction:
                return False  # 存在专用道，说明是弯道
        return True  # 无专用道，说明是直线


def identify_road_shape(df):
    """识别道路线形类型"""

    # 调用函数，找到点集中两个代表性强的点
    p1, p2 = find_endpoints_by_extremes(df)
    point1 = str(p1[0]) + ',' + str(p1[1])
    point2 = str(p2[0]) + ',' + str(p2[1])

    # 调用高德api，判断两点之间的距离及其导航走法
    distance1, steps1 = get_distance_and_move_steps(origin=point1, destination=point2)
    distance2, steps2 = get_distance_and_move_steps(origin=point2, destination=point1)

    # print(distance1, steps1)
    # print(distance2, steps2)

    # 调用函数，判断是否需要转弯，从而判断道路线形
    road_shape = judge_road_shape(distance1, distance2, steps1, steps2)
    time.sleep(SLEEP_SECONDS)
    return road_shape


def get_direction(subset):
    sub_mean = subset.mean(axis=0)
    sub_centered = subset - sub_mean
    # 子集协方差矩阵的最大特征值对应的特征向量
    _, sub_vecs = np.linalg.eigh(sub_centered.T @ sub_centered / (len(subset) - 1))
    return sub_vecs[:, 1]  # 返回子集的第一主方向


def classify_road_shape(df, angle_thresh=30, min_points_per_half=5):
    """判断点集是“直线”还是“曲线”"""
    points = df[['longitude', 'latitude']].values
    points = np.asarray(points)
    n = points.shape[0]
    if n < 2 * min_points_per_half:  # 点数不足，直接归为直线型
        return True

    # 1. 整体PCA，获取第一主轴方向
    mean = points.mean(axis=0)
    centered = points - mean
    # 协方差矩阵的特征向量（特征值升序，索引1对应较大特征值的特征向量）
    _, eigvecs = np.linalg.eigh(centered.T @ centered / (n - 1))
    v1 = eigvecs[:, 1]  # 第一主成分方向（单位向量）

    # 2. 按投影排序并平分为两半
    proj = centered @ v1  # 投影值
    sorted_idx = np.argsort(proj)
    sorted_points = points[sorted_idx]
    half = n // 2
    left_pts, right_pts = sorted_points[:half], sorted_points[half:]

    # 4. 计算两子集的方向向量
    left_dir = get_direction(left_pts)
    right_dir = get_direction(right_pts)

    # 4. 计算两方向夹角（取绝对值，锐角时，angle取值为锐角，钝角时，angle取值为钝角的补角，也为锐角）
    cos_angle = np.abs(np.dot(left_dir, right_dir))
    angle = np.arccos(np.clip(cos_angle, -1.0, 1.0)) * 180 / np.pi
    if angle > angle_thresh:  # 夹角大于30度（或小于150度），判断为曲线
        return False
    else:
        return True


# 示例用法
if __name__ == "__main__":

    # 示例数据
    p1 = [23.196117, 113.242860]
    p2 = [23.194026, 113.244695]
    df = pd.DataFrame({'longitude': [p1[1], p2[1]], 'latitude': [p1[0], p2[0]]})
    API_KEY = "0fe9674ec14dd7449427652adbd319eb"
    result = identify_road_shape(df)
    if result:
        print('这段路是直线路段')
    else:
        print('这段路是曲线路段')

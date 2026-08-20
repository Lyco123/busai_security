import asyncio
from datetime import datetime

import pandas as pd
import numpy as np

from core.clickhouse_connect import connect_to_clickhouse
from model.driver import crud
from model.driver.crud import save_attitude_weights_data
from model.route.main_route_quota_weight_month import save_weights


try:
    from scipy.stats import norm
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def _linear_rank_score(series: pd.Series, step: float = 5.0) -> pd.Series:
    """
    对同一线路内的次数进行降序线性排名赋分（0~100）。
    规则（修改后）：
        - 次数为 0  → 得分 0 分（代表最好）
        - 次数非 0 → 按降序排名，次数最高的第1名得100分，
          之后每降 1 名扣 step 分，最低 0 分。

    参数
    ----------
    series : pd.Series
        某线路内某一类投诉次数列
    step : float, default=5.0
        每下降一个名次扣减的分数

    返回
    -------
    pd.Series
        与输入索引相同的得分列
    """
    scores = pd.Series(index=series.index, dtype=float)
    mask_zero = (series == 0)
    scores[mask_zero] = 0.0

    non_zero = series[~mask_zero]
    if non_zero.empty:
        return scores

    # 降序排名：次数最高的排第1（method='min' 保证并列相同排名）
    ranks = non_zero.rank(method='min', ascending=False)
    # 得分 = 100 - step * (rank - 1)
    non_zero_scores = 100 - step * (ranks - 1)
    non_zero_scores = non_zero_scores.clip(lower=0.0)
    scores[~mask_zero] = non_zero_scores
    return scores


async def score_drivers_aggregated(_start_time, df: pd.DataFrame,
                                   category_weights: dict,
                                   attitude_weight: float = 0.25) -> pd.DataFrame:
    """
    对已聚合的驾驶员投诉次数进行服务态度评分（按线路线性排名）。
    要求：驾驶员 id 和姓名均不得为空，否则丢弃该记录。

    参数
    ----------
    _start_time : str
        评分时间（仅用于传参，本函数内未使用）
    df : pandas.DataFrame
        必须包含以下列：
        - involve_employee_code : 驾驶员工号（不可为空）
        - involve_employee_name : 驾驶员姓名（不可为空）
        - line_code             : 线路编号
        - line_name             : 线路名称
        - skill_times           : 车辆技术类投诉次数
        - secure_times          : 安全管理类投诉次数
        - service_times         : 服务质量类投诉次数
        - org_id, org_name, org_code : 二级单位信息
        - dept_id, dept_name, dept_code : 单位信息
    category_weights : dict
        三类小指标的权重字典，键为 'skill', 'secure', 'service'，值为对应的权重。
        例如：{'skill': 0.3, 'secure': 0.3, 'service': 0.4}
    attitude_weight : float, default=0.25
        服务态度这个大指标的全局权重

    返回
    -------
    pandas.DataFrame
        包含评分结果的数据框
    """
    # 从字典中提取权重（提供默认值以防缺失）
    w_skill = float(category_weights.get('skill', 0.3))
    w_secure = float(category_weights.get('secure', 0.3))
    w_service = float(category_weights.get('service', 0.4))

    # ---- 关键修改：过滤掉驾驶员信息缺失的行 ----
    df = df.dropna(subset=['involve_employee_code', 'involve_employee_name'], how='any')
    # 如果存在空字符串，也可一并过滤
    df = df[(df['involve_employee_code'] != '') & (df['involve_employee_name'] != '')]

    if df.empty:
        # 没有有效驾驶员，返回空DataFrame但保持列结构
        empty_cols = [
            'employee_name', 'employee_code',
            'org_id', 'org_name', 'org_code',
            'dept_id', 'dept_name', 'dept_code',
            'line_code', 'line_name',
            'skill_times', 'secure_times', 'service_times',
            'raw_score_skill', 'raw_score_secure', 'raw_score_service',
            'weighted_skill', 'weighted_secure', 'weighted_service',
            'total_weighted_score',
            'global_skill', 'global_secure', 'global_service',
            'total_global_score',
            'weight_skill', 'weight_secure', 'weight_service',
            'global_weight_skill', 'global_weight_secure', 'global_weight_service',
            'attitude_weight'
        ]
        return pd.DataFrame(columns=empty_cols)

    # 1. 复制一份，保留所有原始列
    result = df.copy()

    # 2. 处理驾驶员标识（用于展示），现在不会为空，但保留此逻辑也无妨
    result['employee_name'] = result['involve_employee_name'].fillna(result['involve_employee_code'])
    result['employee_code'] = result['involve_employee_code'].fillna('')

    # 3. 按线路分组，对三类次数分别进行降序线性排名赋分
    result_parts = []
    for _, group in result.groupby('line_code'):
        group['raw_score_skill'] = _linear_rank_score(group['skill_times'])
        group['raw_score_secure'] = _linear_rank_score(group['secure_times'])
        group['raw_score_service'] = _linear_rank_score(group['service_times'])
        result_parts.append(group)
    result = pd.concat(result_parts, ignore_index=True)

    # 4. 加权计算
    result['weighted_skill'] = result['raw_score_skill'] * w_skill
    result['weighted_secure'] = result['raw_score_secure'] * w_secure
    result['weighted_service'] = result['raw_score_service'] * w_service

    result['total_weighted_score'] = result['weighted_skill'] + result['weighted_secure'] + result['weighted_service']

    result['global_skill'] = result['weighted_skill'] * attitude_weight
    result['global_secure'] = result['weighted_secure'] * attitude_weight
    result['global_service'] = result['weighted_service'] * attitude_weight
    result['total_global_score'] = result['total_weighted_score'] * attitude_weight

    # 添加权重列（常量）
    result['weight_skill'] = w_skill
    result['weight_secure'] = w_secure
    result['weight_service'] = w_service
    result['global_weight_skill'] = w_skill * attitude_weight
    result['global_weight_secure'] = w_secure * attitude_weight
    result['global_weight_service'] = w_service * attitude_weight
    result['attitude_weight'] = attitude_weight

    # 5. 输出列顺序
    output_cols = [
        'employee_name', 'employee_code',
        'org_id', 'org_name', 'org_code',
        'dept_id', 'dept_name', 'dept_code',
        'line_code', 'line_name',
        'skill_times', 'secure_times', 'service_times',
        'raw_score_skill', 'raw_score_secure', 'raw_score_service',
        'weighted_skill', 'weighted_secure', 'weighted_service',
        'total_weighted_score',
        'global_skill', 'global_secure', 'global_service',
        'total_global_score',
        'weight_skill', 'weight_secure', 'weight_service',
        'global_weight_skill', 'global_weight_secure', 'global_weight_service',
        'attitude_weight'
    ]
    # 确保所有列都存在
    for col in output_cols:
        if col not in result.columns:
            result[col] = np.nan
    return result[output_cols]


async def driver_attitude_scores_main(start_time: str):
    try:
        async with await connect_to_clickhouse() as client:
            date_range = [start_time]
            for date in date_range:
                start_date = datetime.strptime(date, '%Y-%m-%d')
                _start_time = start_date.strftime('%Y-%m-%d')
                list = await crud.Driver(client).get_driver_attitude_weights(start_time)
                _category_weights = {}
                for col in list:
                    if col['quota_name'] == '车辆技术投诉次数':
                        _category_weights['skill'] = col['weight_rate2'] / 100
                    if col['quota_name'] == '安全管理投诉次数':
                        _category_weights['secure'] = col['weight_rate2'] / 100
                    if col['quota_name'] == '服务质量投诉次数':
                        _category_weights['service'] = col['weight_rate2'] / 100
                    _attitude_weight = col['weight_rate1'] / 100
                _dict = await crud.Driver(client).get_driver_attitude(_start_time)
                _df = pd.DataFrame(_dict)
                result_df = await score_drivers_aggregated(
                    _start_time,
                    _df,
                    category_weights=_category_weights,
                    attitude_weight=float(_attitude_weight)
                )
                await crud.Driver(client).save_attitude_scores_data(_start_time, result_df.to_dict('records'))
    except Exception as e:
        print(f"驾驶服务态度取数执行出错: {e}")
    print("数据库连接已关闭")


async def driver_attitude_weight_main(_start_time):
    category_weights = {'车辆技术投诉次数': 0.3,
                        '安全管理投诉次数': 0.3,
                        '服务质量投诉次数': 0.4}
    await save_attitude_weights_data(_start_time, category_weights)


if __name__ == "__main__":
    # asyncio.run(driver_attitude_scores_main('2026-01-01'))
    asyncio.run(driver_attitude_weight_main('2026-01-01'))
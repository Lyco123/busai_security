import asyncio
from datetime import datetime

import pandas as pd
import numpy as np

from core.clickhouse_connect import connect_to_clickhouse
from model.driver import crud
from model.driver.crud import save_safety_weights_data, read_raw_sql
from model.driver.src import driver_sql

# ---------- 共享常量（与能耗模块保持一致）----------
ALL_DRIVING_BEHAVIORS = [
    '停站N档违规', '停车不挂N档', '安全带行为', '熄火滑行', '空档滑行',
    '起步急加速', '急减速', '急加速', '急刹车', '急停',
    '车辆未停稳开车门', '车辆起步不关车门', '门开禁启开关', '斑马线超速', '斑马线不文明礼让',
    '违规使用N档', '不规范开关门', '违规使用手刹', '不文明鸣笛', '不规范出站',
    '不规范进站', '不规范转弯', '安全启动', '违规使用空调', '平路不规范行为',
    '上坡不规范行为', '下坡不规范行为', '违规使用总电', '路口大油门', '进站违规制动',
    '区间超速', '全局超速', '左转弯未刹车', '右转弯未刹车'
]

# 行为分类（用于计算标准化指标）
THOUSAND_KM_BEHAVIORS = {
    '起步急加速', '急加速', '急减速', '急刹车', '斑马线不文明礼让',
    '斑马线超速', '车辆起步不关车门', '空档滑行', '熄火滑行', '急停',
    '违规使用空调', '平路不规范行为', '上坡不规范行为', '下坡不规范行为',
    '违规使用总电', '路口大油门', '进站违规制动', '区间超速', '全局超速'
}
HUNDRED_POINT_BEHAVIORS = {
    '不规范转弯', '左转弯未刹车', '右转弯未刹车'
}
HUNDRED_STATION_BEHAVIORS = {
    '不规范进站', '不规范出站', '不规范开关门'
}
PER_KM_BEHAVIORS = {
    '违规使用N档', '违规使用手刹', '停站N档违规', '停车不挂N档', '安全启动'
}

# 英文列名到中文行为的映射（依据实际输入列名）
COL_TO_BEHAVIOR = {
    'stop_ndang_cnt': '停站N档违规',
    'no_n_on_stop_cnt': '停车不挂N档',
    'no_seat_belt_cnt': '安全带行为',
    'stall_coast_cnt': '熄火滑行',
    'neutral_coast_cnt': '空档滑行',
    'start_accel_eval_cnt': '起步急加速',
    'decel_eval_cnt': '急减速',
    'accel_eval_cnt': '急加速',
    'sudden_brake_cnt': '急刹车',
    'sudden_stop_cnt': '急停',
    'door_open_before_stop_cnt': '车辆未停稳开车门',
    'start_with_open_door_cnt': '车辆起步不关车门',
    'illegal_door_switch_cnt': '门开禁启开关',
    'junction_spd_eval_cnt': '斑马线超速',
    'junction_reaccel_eval_cnt': '斑马线不文明礼让',
    'ndang_cnt': '违规使用N档',
    'door_op_eval_cnt': '不规范开关门',
    'illegal_hand_brake_cnt': '违规使用手刹',
    'rude_horn_cnt': '不文明鸣笛',
    'skip_station_cnt': '不规范出站',
    'refuse_ride_cnt': '不规范进站',
    'bad_turn_cnt': '不规范转弯',
    'before_move_safe_cnt': '安全启动',
    'illegal_ac_cnt': '违规使用空调',
    'flat_bad_cnt': '平路不规范行为',
    'upslope_bad_cnt': '上坡不规范行为',
    'downslope_bad_cnt': '下坡不规范行为',
    'illegal_main_power_cnt': '违规使用总电',
    'junction_heavy_gas_cnt': '路口大油门',
    'illegal_brake_on_entry_cnt': '进站违规制动',
    'section_over_spd_cnt': '区间超速',
    'global_over_spd_cnt': '全局超速',
    'left_turn_no_brake_cnt': '左转弯未刹车',
    'right_turn_no_stop_cnt': '右转弯未刹车'
}

# ---------- 主函数 ----------
async def driver_calculate_safety_scores(df, safety_weights, global_weight):
    """
    安全评价打分模块（输入数据已包含标准化指标，0分判断依据改为工时 work_hour）
    输入 df 应包含：employee_id（或 driver_id）, route_id, work_hour
    以及对应34个驾驶行为的标准化指标列（列名与 COL_TO_BEHAVIOR 中的英文名一致）
    """
    # 清理列名：去除 'd.' 和 'o.' 前缀
    df_renamed = df.copy()
    df_renamed.columns = df_renamed.columns.str.replace(r'^d\.', '', regex=True)
    df_renamed.columns = df_renamed.columns.str.replace(r'^o\.', '', regex=True)
    
    # 定义全部34个驾驶行为
    all_behaviors = [
        '停站N档违规', '停车不挂N档', '安全带行为', '熄火滑行', '空档滑行',
        '起步急加速', '急减速', '急加速', '急刹车', '急停',
        '车辆未停稳开车门', '车辆起步不关车门', '门开禁启开关', '斑马线超速', '斑马线不文明礼让',
        '违规使用N档', '不规范开关门', '违规使用手刹', '不文明鸣笛', '不规范出站',
        '不规范进站', '不规范转弯', '安全启动', '违规使用空调', '平路不规范行为',
        '上坡不规范行为', '下坡不规范行为', '违规使用总电', '路口大油门', '进站违规制动',
        '区间超速', '全局超速', '左转弯未刹车', '右转弯未刹车'
    ]
    
    # 基础列名映射
    if 'driver_id' in df_renamed.columns and 'employee_id' not in df_renamed.columns:
        df_renamed.rename(columns={'driver_id': 'employee_id'}, inplace=True)
    if 'driver_name' in df_renamed.columns and 'employee_name' not in df_renamed.columns:
        df_renamed.rename(columns={'driver_name': 'employee_name'}, inplace=True)
    
    # *** 修改点 1：将必要列强校验从里程改为工时 work_hour ***
    required_columns = ['employee_id', 'route_id', 'work_hour']
    missing_columns = [col for col in required_columns if col not in df_renamed.columns]
    if missing_columns:
        raise ValueError(f"缺少必要列: {missing_columns}")
        
    df_renamed['work_hour'] = pd.to_numeric(df_renamed['work_hour'], errors='coerce').fillna(0)
    
    # 兼容处理总里程列（作为非必需字段输出）
    if 'total_mileage' not in df_renamed.columns and 'safty_mileage' in df_renamed.columns:
        df_renamed.rename(columns={'safty_mileage': 'total_mileage'}, inplace=True)
    if 'total_mileage' in df_renamed.columns:
        df_renamed['total_mileage'] = pd.to_numeric(df_renamed['total_mileage'], errors='coerce').fillna(0)
    
    # 直接使用输入中的标准化指标列作为 _rate
    for behavior in all_behaviors:
        src_col = None
        for col, b in COL_TO_BEHAVIOR.items():
            if b == behavior and col in df_renamed.columns:
                src_col = col
                break
        if src_col:
            df_renamed[f'{behavior}_rate'] = pd.to_numeric(df_renamed[src_col], errors='coerce').fillna(0)
        else:
            print(f"警告：数据中缺少行为 '{behavior}' 的标准化指标列，已填充0")
            df_renamed[f'{behavior}_rate'] = 0.0
        df_renamed[f'{behavior}_rate'] = df_renamed[f'{behavior}_rate'].replace([np.inf, -np.inf], 0)
    
    # *** 修改点 2：分离工时为零和非零的驾驶员 ***
    zero_work = df_renamed['work_hour'] <= 0
    df_nonzero = df_renamed[~zero_work].copy()
    df_zero = df_renamed[zero_work].copy()
    
    results = []
    
    for route_id in df_nonzero['route_id'].unique():
        route_data = df_nonzero[df_nonzero['route_id'] == route_id].copy()
        
        # 单驾驶员线路：rate > 0 给50分，否则0
        if len(route_data) == 1:
            for _, row in route_data.iterrows():
                res = _build_result_row(row, all_behaviors, safety_weights, global_weight,
                                        default_score=None, force_zero=False, use_rate_based_score=True)
                results.append(res)
            continue
        
        # 多驾驶员线路：只对 rate > 0 的驾驶员进行排名
        for behavior in all_behaviors:
            rate_col = f'{behavior}_rate'
            if rate_col not in route_data.columns:
                route_data[f'{behavior}_score'] = 0.0
                continue
            positive_mask = route_data[rate_col] > 1e-9
            if positive_mask.any():
                positive_values = route_data.loc[positive_mask, rate_col].values
                positive_ranks = _custom_rank(positive_values, method='min')
                positive_scores = _rank_to_normal_score(positive_ranks)
                scores = np.zeros(len(route_data))
                scores[positive_mask] = positive_scores
                route_data[f'{behavior}_score'] = scores
            else:
                route_data[f'{behavior}_score'] = 0.0
        
        for _, row in route_data.iterrows():
            res = _build_result_row(row, all_behaviors, safety_weights, global_weight,
                                    default_score=None, force_zero=False, use_rate_based_score=False)
            results.append(res)
    
    # *** 修改点 3：处理工时为0的驾驶员 ***
    for _, row in df_zero.iterrows():
        res = _build_result_row(row, all_behaviors, safety_weights, global_weight,
                                default_score=0, force_zero=True, use_rate_based_score=False)
        results.append(res)
    
    if not results:
        return pd.DataFrame()
    
    scores_df = pd.DataFrame(results)
    scores_df['rank'] = scores_df.groupby('route_id')['weighted_total_score'].rank(
        method='min', ascending=False
    ).astype(int)
    
    # *** 修改点 4：整理输出列顺序，加入 work_hour ***
    base_cols = ['employee_id', 'employee_name', 'organ_id', 'organ_name',
                 'route_id', 'route_name', 'work_hour', 'total_mileage',
                 'weighted_total_score', 'global_total_score', 'global_weight', 'rank']
    behavior_cols = []
    for behavior in all_behaviors:
        behavior_cols.extend([
            f'{behavior}_rate',
            f'{behavior}_score',
            f'{behavior}_weighted',
            f'{behavior}_global_weight',
            f'{behavior}_global_score'
        ])
    final_cols = [c for c in base_cols + behavior_cols if c in scores_df.columns]
    return scores_df[final_cols].sort_values(['route_id', 'rank'])

def _build_result_row(row, behavior_list, safety_weights, global_weight,
                      default_score=None, force_zero=False, use_rate_based_score=False):
    """构建单个驾驶员的结果字典（基于 _rate 值）"""
    # *** 修改点 5：在此处向结果字典注入 work_hour，并将里程设为可选读取 ***
    result = {
        'employee_id': row['employee_id'],
        'employee_name': row.get('employee_name', ''),
        'organ_id': row.get('organ_id', ''),
        'organ_name': row.get('organ_name', ''),
        'route_id': row['route_id'],
        'route_name': row.get('route_name', ''),
        'work_hour': row['work_hour'],
        'total_mileage': row.get('total_mileage', 0.0),
        'global_weight': global_weight
    }
    total_weighted = 0.0
    for behavior in behavior_list:
        if force_zero:
            rate = 0.0
        else:
            rate_col = f'{behavior}_rate'
            rate = row.get(rate_col, 0.0)
        result[f'{behavior}_rate'] = rate

        if force_zero:
            score = 0.0
        elif use_rate_based_score:
            score = 50.0 if rate > 1e-9 else 0.0
        elif default_score is not None:
            score = default_score
        else:
            score_col = f'{behavior}_score'
            score = row.get(score_col, 0.0) if score_col in row else 0.0

        weight = safety_weights.get(behavior, 0.0)
        weighted = score * weight
        global_w = weight * global_weight
        global_s = score * global_w

        result[f'{behavior}_score'] = score
        result[f'{behavior}_weighted'] = weighted
        result[f'{behavior}_global_weight'] = global_w
        result[f'{behavior}_global_score'] = global_s
        total_weighted += weighted

    result['weighted_total_score'] = total_weighted
    result['global_total_score'] = total_weighted * global_weight
    return result


# ---------- 辅助函数（保持不变）----------
def _custom_rank(values, method='min'):
    arr = np.array(values)
    sorted_idx = np.argsort(-arr)
    ranks = np.zeros_like(arr, dtype=int)
    if method == 'min':
        cur_rank = 1
        i = 0
        while i < len(sorted_idx):
            same_vals = [sorted_idx[i]]
            j = i + 1
            while j < len(sorted_idx) and arr[sorted_idx[j]] == arr[sorted_idx[i]]:
                same_vals.append(sorted_idx[j])
                j += 1
            for idx in same_vals:
                ranks[idx] = cur_rank
            cur_rank += len(same_vals)
            i = j
    return ranks


def _rank_to_normal_score(ranks):
    n = len(ranks)
    if n == 1:
        return np.array([50.0])
    p = (np.array(ranks) - 0.5) / n
    z = 4.91 * (p ** 0.14 - (1 - p) ** 0.14)
    scores = 100 / (1 + np.exp(z))
    return np.clip(scores, 0, 100)


# ---------- 主流程（保持不变）----------
async def driver_safety_cores_main(start_date):
    try:
        async with await connect_to_clickhouse() as client:
            date_range = [start_date]
            for date in date_range:
                start_time = datetime.strptime(date, '%Y-%m-%d')
                start_time_str = start_time.strftime('%Y%m%d')

                db_weights = await crud.Driver(client).get_driver_safety_weights(start_date)
                safety_weights = {}
                for col in db_weights:
                    safety_weights[col['quota_name']] = float(col['weight_rate2'] / 100)
                    global_weight = float(col['weight_rate1'] / 100)

                for behavior in ALL_DRIVING_BEHAVIORS:
                    if behavior not in safety_weights:
                        safety_weights[behavior] = 0.0
                        print(f"警告：数据库缺少行为 '{behavior}' 的权重，已设为0")
                # if df.empty:
                sql = driver_sql.predict_1d_sql(start_time_str, start_time_str)
                df = await read_raw_sql(sql)

                # df = await crud.Driver(client).get_drivers_day_datas(start_time_str)
                if df.empty:
                    raise ValueError(f"{start_time_str} 安全评价数据为空，无法输出评分结果")

                # 调用评分函数
                safety_scores = await driver_calculate_safety_scores(df, safety_weights, global_weight)
                await crud.Driver(client).save_safety_scores_data(date, safety_scores.to_dict('records'), safety_weights)

    except Exception as e:
        print(f"驾驶安全评价执行出错: {e}")
    print("数据库连接已关闭")


async def driver_safety_weight_main(start_time):
    default_weights = {
        '停站N档违规': 0.03, '停车不挂N档': 0.03, '安全带行为': 0.02, '熄火滑行': 0.03, '空档滑行': 0.03,
        '起步急加速': 0.04, '急减速': 0.04, '急加速': 0.04, '急刹车': 0.04, '急停': 0.04,
        '车辆未停稳开车门': 0.02, '车辆起步不关车门': 0.02, '门开禁启开关': 0.02, '斑马线超速': 0.05, '斑马线不文明礼让': 0.05,
        '违规使用N档': 0.04, '不规范开关门': 0.02, '违规使用手刹': 0.03, '不文明鸣笛': 0.02, '不规范出站': 0.02,
        '不规范进站': 0.02, '不规范转弯': 0.04, '安全启动': 0.04, '违规使用空调': 0.02, '平路不规范行为': 0.02,
        '上坡不规范行为': 0.02, '下坡不规范行为': 0.02, '违规使用总电': 0.02, '路口大油门': 0.03, '进站违规制动': 0.03,
        '区间超速': 0.04, '全局超速': 0.05, '左转弯未刹车': 0.04, '右转弯未刹车': 0.04
    }
    total = sum(default_weights.values())
    if abs(total - 1.0) > 1e-6:
        default_weights = {k: v / total for k, v in default_weights.items()}
    safety_weights = await save_safety_weights_data(start_time, default_weights)
    return safety_weights


if __name__ == "__main__":
    asyncio.run(driver_safety_cores_main('2026-05-12'))
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

async def calculate_driver_energy_scores(df, behavior_weights, global_weight=0.3):
    """
    根据驾驶行为权重对驾驶员进行打分（行为列已是标准化指标，0分判断依据改为工时 work_hour）
    """
    # 清理列名：去除 'd.' 和 'o.' 前缀（来自SQL查询的表别名）
    df_renamed = df.copy()
    df_renamed.columns = df_renamed.columns.str.replace(r'^d\.', '', regex=True)
    df_renamed.columns = df_renamed.columns.str.replace(r'^o\.', '', regex=True)
    
    # 定义所有驾驶行为（按编号顺序）
    driving_behaviors = [
        '停站N档违规', '停车不挂N档', '安全带行为', '熄火滑行', '空档滑行',
        '起步急加速', '急减速', '急加速', '急刹车', '急停',
        '车辆未停稳开车门', '车辆起步不关车门', '门开禁启开关', '斑马线超速', '斑马线不文明礼让',
        '违规使用N档', '不规范开关门', '违规使用手刹', '不文明鸣笛', '不规范出站',
        '不规范进站', '不规范转弯', '安全启动', '违规使用空调', '平路不规范行为',
        '上坡不规范行为', '下坡不规范行为', '违规使用总电', '路口大油门', '进站违规制动',
        '区间超速', '全局超速', '左转弯未刹车', '右转弯未刹车'
    ]
    
    # 实际列名到中文行为的映射（列名已去除前缀）
    col_to_behavior = {
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
    
    # 基础列名映射（清理后直接使用）
    if 'driver_id' in df_renamed.columns and 'employee_id' not in df_renamed.columns:
        df_renamed.rename(columns={'driver_id': 'employee_id'}, inplace=True)
    if 'driver_name' in df_renamed.columns and 'employee_name' not in df_renamed.columns:
        df_renamed.rename(columns={'driver_name': 'employee_name'}, inplace=True)
        
    # 保留里程字段兼容（作为非必需字段输出）
    if 'total_mileage' not in df_renamed.columns and 'safty_mileage' in df_renamed.columns:
        df_renamed.rename(columns={'safty_mileage': 'total_mileage'}, inplace=True)
    
    # *** 修改点 1：将必须列校验从 total_mileage 改为 work_hour ***
    required_columns = ['employee_id', 'route_id', 'work_hour']
    missing_columns = [col for col in required_columns if col not in df_renamed.columns]
    if missing_columns:
        print(f"错误：数据中缺少必要列: {missing_columns}")
        return pd.DataFrame()
    
    # *** 修改点 2：确保 work_hour 为数值型 ***
    df_renamed['work_hour'] = pd.to_numeric(df_renamed['work_hour'], errors='coerce').fillna(0)
    
    # 如果数据里有里程，也顺便保证它是数值，防止下游报错
    if 'total_mileage' in df_renamed.columns:
        df_renamed['total_mileage'] = pd.to_numeric(df_renamed['total_mileage'], errors='coerce').fillna(0)
    
    # 为每个驾驶行为创建 _rate 列（直接取输入中的值）
    for behavior in driving_behaviors:
        src_col = None
        for col, b in col_to_behavior.items():
            if b == behavior and col in df_renamed.columns:
                src_col = col
                break
        if src_col:
            df_renamed[f'{behavior}_rate'] = pd.to_numeric(df_renamed[src_col], errors='coerce').fillna(0)
        else:
            df_renamed[f'{behavior}_rate'] = 0.0
        df_renamed[f'{behavior}_rate'] = df_renamed[f'{behavior}_rate'].replace([np.inf, -np.inf], 0)
    
    # *** 修改点 3：分离工时为零和非零的驾驶员 ***
    zero_work_drivers = df_renamed[df_renamed['work_hour'] <= 0].copy()
    nonzero_work_drivers = df_renamed[df_renamed['work_hour'] > 0].copy()
    
    results = []
    
    # 按线路分组处理工时 > 0 的人
    for route_id in nonzero_work_drivers['route_id'].unique():
        route_data = nonzero_work_drivers[nonzero_work_drivers['route_id'] == route_id].copy()
        
        if len(route_data) < 2:
            # 单驾驶员线路
            for _, row in route_data.iterrows():
                result = {
                    'employee_id': row['employee_id'],
                    'employee_name': row.get('employee_name', ''),
                    'organ_id': row.get('organ_id', ''),
                    'organ_name': row.get('organ_name', ''),
                    'route_id': route_id,
                    'route_name': '',
                    'work_hour': row['work_hour'],
                    'total_mileage': row.get('total_mileage', 0.0),
                    'weighted_total_score': 0.0
                }
                total_score = 0.0
                for behavior in driving_behaviors:
                    rate = row.get(f'{behavior}_rate', 0.0)
                    result[f'{behavior}_rate'] = rate
                    weight = behavior_weights.get(behavior, 0.0)
                    original_score = 50.0 if rate > 1e-9 else 0.0
                    result[f'{behavior}_score'] = original_score
                    weighted = original_score * weight
                    result[f'{behavior}_weighted'] = weighted
                    global_w = weight * global_weight
                    result[f'{behavior}_global_weight'] = global_w
                    result[f'{behavior}_global_score'] = original_score * global_w
                    total_score += weighted
                result['weighted_total_score'] = total_score
                result['global_total_score'] = total_score * global_weight
                result['global_weight'] = global_weight
                results.append(result)
            continue
        
        # 多驾驶员线路
        for behavior in driving_behaviors:
            rate_col = f'{behavior}_rate'
            if rate_col not in route_data.columns:
                route_data[f'{behavior}_score'] = 0.0
                continue
            positive_mask = route_data[rate_col] > 1e-9
            if positive_mask.any():
                positive_values = route_data.loc[positive_mask, rate_col].values
                positive_ranks = custom_rank(positive_values, method='min')
                positive_scores = rank_to_normal_score(positive_ranks)
                scores = np.zeros(len(route_data))
                scores[positive_mask] = positive_scores
                route_data[f'{behavior}_score'] = scores
            else:
                route_data[f'{behavior}_score'] = 0.0
        
        for _, row in route_data.iterrows():
            total_score = 0.0
            result = {
                'employee_id': row['employee_id'],
                'employee_name': row.get('employee_name', ''),
                'organ_id': row.get('organ_id', ''),
                'organ_name': row.get('organ_name', ''),
                'route_id': route_id,
                'route_name': '',
                'work_hour': row['work_hour'],
                'total_mileage': row.get('total_mileage', 0.0)
            }
            for behavior in driving_behaviors:
                rate = row.get(f'{behavior}_rate', 0.0)
                result[f'{behavior}_rate'] = rate
                weight = behavior_weights.get(behavior, 0.0)
                original_score = row.get(f'{behavior}_score', 0.0)
                weighted_score = original_score * weight
                global_w = weight * global_weight
                global_s = original_score * global_w
                result[f'{behavior}_score'] = original_score
                result[f'{behavior}_weighted'] = weighted_score
                result[f'{behavior}_global_weight'] = global_w
                result[f'{behavior}_global_score'] = global_s
                total_score += weighted_score
            result['weighted_total_score'] = total_score
            result['global_total_score'] = total_score * global_weight
            result['global_weight'] = global_weight
            results.append(result)
    
    # *** 修改点 4：处理工时为0的驾驶员，直接赋0分 ***
    for _, row in zero_work_drivers.iterrows():
        result = {
            'employee_id': row['employee_id'],
            'employee_name': row.get('employee_name', ''),
            'organ_id': row.get('organ_id', ''),
            'organ_name': row.get('organ_name', ''),
            'route_id': row.get('route_id', ''),
            'route_name': '',
            'work_hour': row['work_hour'],
            'total_mileage': row.get('total_mileage', 0.0),
            'weighted_total_score': 0.0
        }
        for behavior in driving_behaviors:
            rate = row.get(f'{behavior}_rate', 0.0)
            result[f'{behavior}_rate'] = rate
            result[f'{behavior}_score'] = 0.0
            weight = behavior_weights.get(behavior, 0.0)
            result[f'{behavior}_weighted'] = 0.0
            result[f'{behavior}_global_weight'] = weight * global_weight
            result[f'{behavior}_global_score'] = 0.0
        result['global_total_score'] = 0.0
        result['global_weight'] = global_weight
        results.append(result)
    
    if not results:
        print("警告：没有有效的打分结果")
        return pd.DataFrame()
    
    scores_df = pd.DataFrame(results)
    scores_df['rank'] = scores_df.groupby('route_id')['weighted_total_score'].rank(
        method='min', ascending=False
    ).astype(int)
    
    # *** 修改点 5：整理输出列顺序时，将 work_hour 加入基础字段 ***
    base_columns = [
        'employee_id', 'employee_name', 'organ_id', 'organ_name',
        'route_id', 'route_name', 'work_hour', 'total_mileage',
        'weighted_total_score', 'global_total_score', 'global_weight', 'rank'
    ]
    for behavior in driving_behaviors:
        base_columns.extend([
            f'{behavior}_rate',
            f'{behavior}_score',
            f'{behavior}_weighted',
            f'{behavior}_global_weight',
            f'{behavior}_global_score'
        ])
    existing_cols = [col for col in base_columns if col in scores_df.columns]
    result_df = scores_df[existing_cols].copy()
    result_df = result_df.sort_values(['route_id', 'rank'])
    return result_df


    
# 以下辅助函数保持不变
def custom_rank(values, method='min'):
    arr = np.array(values)
    sorted_indices = np.argsort(-arr)
    ranks = np.zeros_like(arr, dtype=int)
    if method == 'min':
        current_rank = 1
        i = 0
        while i < len(sorted_indices):
            idx = sorted_indices[i]
            current_value = arr[idx]
            same_value_indices = [idx]
            j = i + 1
            while j < len(sorted_indices) and arr[sorted_indices[j]] == current_value:
                same_value_indices.append(sorted_indices[j])
                j += 1
            for same_idx in same_value_indices:
                ranks[same_idx] = current_rank
            current_rank += len(same_value_indices)
            i = j
    return ranks

def rank_to_normal_score(ranks):
    ranks = np.array(ranks)
    n = len(ranks)
    if n == 1:
        return np.array([50.0])
    p = (ranks - 0.5) / n
    z_scores = 4.91 * (np.power(p, 0.14) - np.power(1 - p, 0.14))
    scores = 100 * (1 / (1 + np.exp(z_scores)))
    scores = np.clip(scores, 0, 100)
    return scores
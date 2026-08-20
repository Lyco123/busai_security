"""
公交站场安全指标评分模块（划定区域）
输入：宽表DataFrame，包含站场基本信息及各二级指标的等级值（2=好，1=一般，0=差）
输出：评分汇总DataFrame，包含权重、得分、风险等级等
"""
import asyncio
from datetime import datetime

import pandas as pd

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from model.station import crud
from model.station.crud import save_station_weights_data


# 等级值到百分制分数的映射（2=好→0分，1=一般→50分，0=差→100分）
# 修改代码顶部的字典
LEVEL_TO_SCORE = {
    2: 0, 1: 50, 0: 100, 
    '2': 0, '1': 50, '0': 100  # 增加对字符串类型的兼容
}

# ========== 本地划定区域评分规则（好得分）==========
# 直接使用固定规则，避免依赖数据库中可能存储错误的weight_rate
AREA_RULES_RAW_LOCAL = {
    '交通安全': {
        '人车分流': 20,
        '人流量、车流量': 15,
        '站场警示标志': 15,
        '安保': 10,
        '出入口': 10,
        '公交线路、车数': 10,
        '夜间灯光': 10,
        '视觉盲区': 10
    },
    '消防安全': {
        '充电场充电车数': 30,
        '风险隐患': 30,
        '消防水源': 20,
        '消防设备': 20
    },
    '三防安全': {
        '场站地势': 20,
        '临水临崖': 20,
        '场地设施、建筑、树木': 20,
        '三防应急设施、设备': 20,
        '监控设备': 20
    }
}


async def calculate_weights(rules, global_weights):
    """
    计算每个二级指标的局部权重和全局权重（好得分 / 100）
    参数:
        rules: 评分规则字典 {一级指标: {二级指标: 好得分}}
        global_weights: 一级指标全局权重字典
    返回:
        dict: {二级指标名: {'local_weight': float, 'global_weight': float}}
    """
    result = {}
    for l1, items in rules.items():
        l1_global = global_weights.get(l1, 0)
        for sec_name, max_score in items.items():
            local_weight = max_score / 100.0          # 好得分/100
            global_weight = local_weight * l1_global  # 局部权重 * 一级权重
            result[sec_name] = {
                'local_weight': local_weight,
                'global_weight': global_weight
            }
    return result


def risk_level_new(score):
    """风险等级：分数越高风险越大，0~40三级，40~70二级，70~100一级"""
    if score < 40:
        return "三级风险"
    elif score < 70:
        return "二级风险"
    else:
        return "一级风险"


async def score_designated_area_stations(input_data, global_weights=None):
    """
    参数:
        input_data (str): 日期字符串或其他标识，用于SQL查询
        global_weights (dict, optional): 一级指标全局权重，默认从数据库获取
    返回:
        pd.DataFrame: 包含基本信息、权重、得分、风险等级等
    """
    try:
        async with await connect_to_clickhouse() as client:
            # ---------- 从数据库获取一级指标权重 ----------
            _quota1_datas = await crud.BusStation(client).get_bus_station_quota1('划定区域', input_data)
            _quota2_datas = await crud.BusStation(client).get_bus_station_quota2('划定区域', input_data)
            _quota3_datas = await crud.BusStation(client).get_bus_station_quota3('划定区域', input_data)
            global_weights_db = {}
            for item in _quota2_datas:
                global_weights_db[item['quota_name']] = item['weight_rate']

            if global_weights is None:
                global_weights = global_weights_db
                
            # 【优化】：增加自动归一化逻辑，防止数据库读取的权重是 40, 30, 30 而不是 0.4, 0.3, 0.3
            total_weight = sum(global_weights.values())
            if abs(total_weight - 1.0) > 1e-6:
                print(f"警告：一级指标权重之和为 {total_weight}（不等于1），系统已自动将其归一化（/100）")
                for k in global_weights:
                    global_weights[k] = global_weights[k] / 100.0

            # 使用本地规则计算二级指标权重（确保正确）
            sec_weights = await calculate_weights(AREA_RULES_RAW_LOCAL, global_weights)

            ym = datetime.strptime(input_data, "%Y-%m-%d")
            ym_str = ym.strftime("%Y-%m")
            sql="select max(run_date) as run_date from ai_security.ods_custom_bus_station_profile"
            record_date=await crud.BusStation(client).get_data_sql_dict(sql)
            if record_date is not None:
                if record_date[0]['run_date']<ym_str:
                    ym_str=record_date[0]['run_date']

            # 从数据库读取宽表数据
            sql = sql_config.station_huading_sql(ym_str)
            df = await crud.BusStation(client).read_raw_sql(sql)

            # 列名映射
            df.rename(columns={
                'station_code': '站场id',
                'station_name': '站场名称',
                'terminal_name': '总站名称',
                'organ_id': '所属公司id',
                'organ_name': '所属公司名称',
                'station_type': '站场类型',
                'run_area': '营运面积',
                'station_properties': '站场属性',
                'route_num': '公交线路数',
                'service_bus_number': '场内车辆数'
            }, inplace=True)

            # ---------- 列名兼容处理 ----------
            if '所属公司' not in df.columns and '所属公司名称' in df.columns:
                df.rename(columns={'所属公司名称': '所属公司'}, inplace=True)
            if '充电场充电车数' not in df.columns and '充电场车数' in df.columns:
                df.rename(columns={'充电场车数': '充电场充电车数'}, inplace=True)

            base_cols = ['站场id', '站场名称', '总站名称', '所属公司', '站场类型',
                         '营运面积', '站场属性', '公交线路数', '场内车辆数']
            extra_info_cols = []
            if '所属公司id' in df.columns:
                extra_info_cols.append('所属公司id')

            for col in base_cols:
                if col not in df.columns:
                    raise ValueError(f"输入数据缺少必需列: {col}")

            # 记录时间处理
            if '记录时间' not in df.columns:
                df['记录时间'] = pd.Timestamp('now')
            else:
                df['记录时间'] = pd.to_datetime(df['记录时间'])

            all_sec = list(sec_weights.keys())
            missing = [c for c in all_sec if c not in df.columns]
            if missing:
                raise ValueError(f"缺少二级指标列: {missing}")


            for sec in all_sec:
                df[sec] = df[sec].fillna(2)

            # ---------- 1. 计算二级指标百分制分数 ----------
            for sec in all_sec:
                df[f'{sec}_百分制分数'] = df[sec].map(LEVEL_TO_SCORE).fillna(0).astype(float)

            # ---------- 2. 计算局部分数和全局分数 ----------
            for sec in all_sec:
                df[f'{sec}_局部分数'] = df[f'{sec}_百分制分数'] * sec_weights[sec]['local_weight']
                df[f'{sec}_全局分数'] = df[f'{sec}_百分制分数'] * sec_weights[sec]['global_weight']

            # ---------- 3. 权重写入 ----------
            for sec in all_sec:
                df[f'{sec}_局部权重'] = sec_weights[sec]['local_weight']
                df[f'{sec}_全局权重'] = sec_weights[sec]['global_weight']

            # ---------- 4. 一级指标得分 ----------
            for l1, items in AREA_RULES_RAW_LOCAL.items():
                sec_list = list(items.keys())
                df[f'{l1}_原始分数'] = sum(
                    df[f'{sec}_百分制分数'] * sec_weights[sec]['local_weight']
                    for sec in sec_list
                )
                df[f'{l1}_全局分数'] = df[f'{l1}_原始分数'] * global_weights[l1]

            # ---------- 5. 站场总分 ----------
            df['站场总分'] = df[[f'{l1}_全局分数' for l1 in global_weights.keys()]].sum(axis=1)

            # ---------- 6. 风险等级 ----------
            for l1 in global_weights.keys():
                df[f'{l1}_风险等级'] = df[f'{l1}_原始分数'].apply(risk_level_new)

            # ---------- 7. 整理输出列 ----------
            output_cols = base_cols + extra_info_cols + ['站场总分']
            
            for l1 in global_weights.keys():
                output_cols += [f'{l1}_原始分数', f'{l1}_全局分数', f'{l1}_风险等级']
                
            for sec in all_sec:
                output_cols += [
                    sec,  # <--- 【修改处】新增原列（如：'人车分流'），它保存着输入的 2, 1, 0 值
                    f'{sec}_百分制分数',
                    f'{sec}_局部分数',
                    f'{sec}_全局分数',
                    f'{sec}_局部权重',
                    f'{sec}_全局权重'
                ]

            final_df = df[output_cols].copy()
            
            # 【修复列名冲突】：有时候直接输出 sec 列会导致业务逻辑困扰，我们可以在最终输出前为这些等级值列加上 "_等级" 后缀（可选，如不需要可注释掉下两行）
            # rename_dict = {sec: f'{sec}_等级' for sec in all_sec}
            # final_df.rename(columns=rename_dict, inplace=True)
            
            final_df.to_csv("final_huading_df.csv", index=False, encoding="utf-8-sig")  # 调试时可开启

            station_dict = sql_config.station_roadside_dict()['划定区域']
            await crud.BusStation(client).save_scores_data(input_data, final_df.to_dict("records"),
                                                           _quota1_datas, _quota2_datas, _quota3_datas,station_dict)
            return final_df
    except Exception as e:
        print(f"划定区域评分主程序执行出错: {e}")
    print("数据库连接已关闭")


async def station_weights_main(start_time: str):
    """保存划定区域评分规则（区域权重=1）"""
    station_weights = {'划定区域': 100}
    station_area_weights = {'交通安全': 40, '消防安全': 30, '三防安全': 30}
    result = {
        'quota1': station_weights,
        'quota2': station_area_weights,
        'quota3': AREA_RULES_RAW_LOCAL
    }
    await save_station_weights_data(start_time, result, "划定区域")


if __name__ == "__main__":
    asyncio.run(station_weights_main("2026-05-01"))
    # asyncio.run(score_designated_area_stations("2026-05-03"))
"""
公交站场安全指标评分模块（路边区域）
输入：宽表DataFrame，包含站场基本信息及各二级指标的等级值（2=好，1=一般，0=差）
输出：评分汇总DataFrame，包含权重、得分、风险等级等
"""
import asyncio
import os
import uuid
from datetime import datetime

import pandas as pd

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.station import crud
from model.station.crud import save_station_weights_data, delete_station_datas, update_station_scores_main, \
    delete_station_weights_datas
from model.station.station_huading_score import score_designated_area_stations, station_weights_main
from services.ai_report_summary import report_main
from utils.logger import logger

# 等级值到百分制分数的映射（2=好→0分，1=一般→50分，0=差→100分）
# 修改代码顶部的字典
LEVEL_TO_SCORE = {
    2: 0, 1: 50, 0: 100, 
    '2': 0, '1': 50, '0': 100  # 增加对字符串类型的兼容
}

# ========== 本地路边区域评分规则（好得分）==========
ROADSIDE_RULES_RAW_LOCAL = {
    '交通安全': {
        '人流量、车流量': 40,
        '公交线路、车数': 20,
        '夜间灯光': 20,
        '视觉盲区': 20
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
            local_weight = max_score / 100.0
            global_weight = local_weight * l1_global
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


async def score_roadside_stations(input_data, global_weights=None):
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
            _quota1_datas = await crud.BusStation(client).get_bus_station_quota1('路边区域', input_data)
            _quota2_datas = await crud.BusStation(client).get_bus_station_quota2('路边区域', input_data)
            _quota3_datas = await crud.BusStation(client).get_bus_station_quota3('路边区域', input_data)
            # 不再从数据库获取二级指标的具体分值，避免 weight_rate 错误
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
            sec_weights = await calculate_weights(ROADSIDE_RULES_RAW_LOCAL, global_weights)

            ym = datetime.strptime(input_data, "%Y-%m-%d")
            ym_str = ym.strftime("%Y-%m")
            sql="select max(run_date) as run_date from ai_security.ods_custom_bus_station_profile"
            record_date=await crud.BusStation(client).get_data_sql_dict(sql)
            if record_date is not None:
                if record_date[0]['run_date']<ym_str:
                    ym_str=record_date[0]['run_date']
            # 从数据库读取宽表数据
            sql = sql_config.station_roadside_sql(ym_str)
            df = await crud.BusStation(client).read_raw_sql(sql)

            # 列名映射
            df.rename(columns={
                'station_code': '站场id', 'station_name': '站场名称',
                'terminal_name': '总站名称', 'organ_id': '所属公司id',
                'organ_name': '所属公司名称', 'station_type': '站场类型',
                'run_area': '营运面积', 'station_properties': '站场属性',
                'route_num': '公交线路数', 'service_bus_number': '场内车辆数'
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

            if '记录时间' not in df.columns:
                df['记录时间'] = pd.Timestamp('2024-01-01')
            else:
                df['记录时间'] = pd.to_datetime(df['记录时间'])

            all_sec = list(sec_weights.keys())
            missing = [c for c in all_sec if c not in df.columns]
            if missing:
                raise ValueError(f"缺少二级指标列: {missing}")

            for sec in all_sec:
                df[sec] = df[sec].fillna(2)

            # 1. 计算二级指标百分制分数
            for sec in all_sec:
                df[f'{sec}_百分制分数'] = df[sec].map(LEVEL_TO_SCORE).fillna(0).astype(float)

            # 2. 计算局部分数和全局分数
            for sec in all_sec:
                df[f'{sec}_局部分数'] = df[f'{sec}_百分制分数'] * sec_weights[sec]['local_weight']
                df[f'{sec}_全局分数'] = df[f'{sec}_百分制分数'] * sec_weights[sec]['global_weight']

            # 3. 权重写入
            for sec in all_sec:
                df[f'{sec}_局部权重'] = sec_weights[sec]['local_weight']
                df[f'{sec}_全局权重'] = sec_weights[sec]['global_weight']

            # 4. 一级指标得分
            for l1, items in ROADSIDE_RULES_RAW_LOCAL.items():
                sec_list = list(items.keys())
                df[f'{l1}_原始分数'] = sum(
                    df[f'{sec}_百分制分数'] * sec_weights[sec]['local_weight']
                    for sec in sec_list
                )
                df[f'{l1}_全局分数'] = df[f'{l1}_原始分数'] * global_weights[l1]

            # 5. 站场总分
            df['站场总分'] = df[[f'{l1}_全局分数' for l1 in global_weights.keys()]].sum(axis=1)

            # 6. 风险等级
            for l1 in global_weights.keys():
                df[f'{l1}_风险等级'] = df[f'{l1}_原始分数'].apply(risk_level_new)

            # 7. 整理输出列
            output_cols = base_cols + extra_info_cols + ['站场总分']
            for l1 in global_weights.keys():
                output_cols += [f'{l1}_原始分数', f'{l1}_全局分数', f'{l1}_风险等级']
                
            for sec in all_sec:
                output_cols += [
                    sec,  # <--- 【修改处】新增原列（如：'人流量、车流量'），它保存着输入的 2, 1, 0 值
                    f'{sec}_百分制分数',
                    f'{sec}_局部分数',
                    f'{sec}_全局分数',
                    f'{sec}_局部权重',
                    f'{sec}_全局权重'
                ]

            final_df = df[output_cols].copy()

            final_df.to_csv("final_roadside_df.csv", index=False, encoding="utf-8-sig")  # 调试时可开启
            # 保存结果
            station_dict=sql_config.station_roadside_dict()['路边区域']

            await crud.BusStation(client).save_scores_data(input_data, final_df.to_dict("records"),
                                                           _quota1_datas, _quota2_datas, _quota3_datas,station_dict)
            return final_df
    except Exception as e:
        print(f"站场画像分数主程序执行出错: {e}")
    print("数据库连接已关闭")


async def station_roadside_weights_main(start_time: str):
    """保存路边区域评分规则（区域权重=1）"""
    station_weights = {'路边区域': 100}
    station_area_weights = {'交通安全': 40, '消防安全': 30, '三防安全': 30}
    result = {
        'quota1': station_weights,
        'quota2': station_area_weights,
        'quota3': ROADSIDE_RULES_RAW_LOCAL
    }
    await save_station_weights_data(start_time, result, "路边区域")

async def station_score_main(start_date:str):

    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='画像',
        module_name='站场画像',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict)

    start_date_ = start_date
    _start_time = start_date
    start_time=datetime.strptime(_start_time,'%Y-%m-%d')
    _start_time_str=start_time.strftime('%Y%m%d')


    logger.info(f"删除{_start_time}站场画像数据 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await delete_station_datas(_start_time_str)
    logger.info(f"删除{_start_time}站场画像数据 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    #

    #计算路边区域
    logger.info(f"准备{_start_time}站场路边区域画像分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await score_roadside_stations(_start_time)
    logger.info(f"{_start_time}站场路边区域画像分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    #计算站场划定区域
    logger.info(f"准备{_start_time}站场划定区域画像分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await score_designated_area_stations(_start_time)
    logger.info(f"{_start_time}站场划定区域画像分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 计算站场总分
    logger.info(f"准备{_start_time}站场画像总分 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await update_station_scores_main(_start_time)
    logger.info(f"{_start_time}站场画像总分计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    import gc
    gc.collect()

    remark = '站场画像计算完成'
    await update_moudle_log(_id, remark)

async def station_all_weights_main(start_date_time: str):

    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='站场权重',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date_time,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict)

    _start_time = start_date_time
    logger.info(f"删除{_start_time}站场权重数据 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await delete_station_weights_datas(_start_time)
    logger.info(f"删除{_start_time}站场权重数据 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        logger.info(
            f"准备{_start_time}站场权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await station_roadside_weights_main(_start_time)
        await station_weights_main(_start_time)
        logger.info(
            f"{_start_time}站场权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}站场权重执行出错：{e}")
        print(f"{_start_time}站场权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

    remark = ''
    await update_moudle_log(_id, remark)

async def get_station_report(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            list = await crud.BusStation(client).get_station_report(_ppartition)
            for data in list:
                payload = {
                    "busStationName": data["bus_station_name"],
                    "ppartition": data["ppartition"],
                }
                logger.info(f"获取站场{data['bus_station_name']}：{start_date}总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                result=await report_main(payload)
                logger.info(f"获取站场{data['bus_station_name']}：{start_date}总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(result)
    except Exception as e:
        logger.info(f"生成站场报告执行出错: {e}")
        print(f"生成站场报告执行出错: {e}")
    print("数据库连接已关闭")


if __name__ == "__main__":
    # asyncio.run(station_all_weights_main("2026-05-01"))
    asyncio.run(station_score_main("2026-05-31"))
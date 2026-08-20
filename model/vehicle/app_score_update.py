# -*- coding: utf-8 -*-
"""本地评分入口：读入 raw 宽表 -> 读取权重产物 -> 评分 -> 输出结果表。"""
from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.vehicle.src import crud
from model.vehicle.src.config import SCORE_OUTPUT_MODE
from model.vehicle.src.crud import save_scores, get_weights
from model.vehicle_old.src.utils.common import read_raw_file
from model.vehicle.src.data_io import (
    load_score_bundle,
    read_feature_source,
    save_01_summary_scores,
    save_02_original_values,
    save_02_original_values,
    save_03_normalized_values,
    save_04_contribution_values,
    save_05_daily_monitor,
    save_06_unscoreable_vehicles,
    save_07_missing_fill_records, read_feature_source_table, read_csv, require_file,
)
from model.vehicle.src.features import required_source_window
from model.vehicle.src.modeling import ScoreUpdater
from model.vehicle.src.utils import logger
from services.ai_report_summary import report_main
from utils.tools import get_last_month_day

# =========================
# 运行配置：日常主要改这里
# =========================
# START_DATE = "2026-05-01"
# END_DATE = "2026-05-07"
# CREATE_DATE = "2026-05-01"
# RAW_SOURCE_PATH = "data/*feature_source*.csv"
# WEIGHT_TABLE_PATH = "output/weight_20260401_20260430_20260501/02_weights/XGB正式权重表_2026-05_2026-05-01.csv"


# def parse_args():
#     parser = argparse.ArgumentParser(description="车辆画像评分更新")
#     parser.add_argument("--start-date", default=START_DATE)
#     parser.add_argument("--end-date", default=END_DATE)
#     parser.add_argument("--create-date", default=CREATE_DATE)
#     return parser.parse_args()


def make_score_dir(weight_table_path: str, start_date: str, end_date: str) -> Path:
    """评分结果写到权重批次目录下，便于追溯模型版本。"""
    weight_dir = Path(weight_table_path).parent.parent
    score_name = f"score_{start_date}" if start_date == end_date else f"score_{start_date}_{end_date}"
    out_dir = weight_dir / "scores" / score_name
    (out_dir / "00_logs").mkdir(parents=True, exist_ok=True)
    return out_dir

async def data_init(start_time):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_time, "%Y-%m-%d")
            start_date = end_date
            end_date=end_date

            logger.info(f"车辆{start_date}--{end_date}风险分数数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            try:
              s_start_date = get_last_month_day(end_date).strftime("%Y-%m-%d")
              e_start_date = end_date.strftime("%Y-%m-%d")
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_00_params',sql_config.tmp_vrp_00_params_sql(s_start_date,e_start_date))
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_01_energy_route_day',sql_config.tmp_vrp_01_energy_route_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_02_static_bus',sql_config.tmp_vrp_02_static_bus_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_03_fault_day',sql_config.tmp_vrp_03_fault_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_04_can_day',sql_config.tmp_vrp_04_can_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_05_behavior_day',sql_config.tmp_vrp_05_behavior_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_06_charge_day', sql_config.tmp_vrp_06_charge_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_07_aircond_day', sql_config.tmp_vrp_07_aircond_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_08_route_trip_day', sql_config.tmp_vrp_08_route_trip_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_09_route_station_static', sql_config.tmp_vrp_09_route_station_static_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_10_route_black_static',sql_config.tmp_vrp_10_route_black_static_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_11_passenger_day',sql_config.tmp_vrp_11_passenger_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_12_repair_day',sql_config.tmp_vrp_12_repair_day_sql())
              await crud.Vehicle(client).gen_tmp_table('tmp_vrp_00_feature_source',sql_config.tmp_vrp_00_feature_source_sql())

            except Exception as e:
                print(f"车辆计算分数一个月数据存入临时表执行出错: {e}")
            logger.info(f"车辆{start_date}--{end_date}风险分数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"车辆计算权重半年数据存入临时表执行出错{e}")
        print(f"车辆计算权重半年数据存入临时表执行出错: {e}")


async def main():
    pass
    # args = parse_args()
    # out_dir = make_score_dir(WEIGHT_TABLE_PATH, args.start_date, args.end_date)
    # logger.configure(out_dir / "00_logs", "score", args.create_date)
    #
    # # await data_init(args.create_date)
    #
    # # 1. 读入 raw 宽表和同版本模型产物。
    # # 数据库对接时，可替换 raw_df 这一行，例如：
    # # sqlwhere = f"stat_date BETWEEN '{source_start}' AND '{source_end}'"
    # # raw_df = await read_raw_db("ai_security.tmp_vehicle_profile_feature_source", sqlwhere, "*")
    # # bundle 若改为数据库读取，必须同时保证模型、metadata、填充统计、归一化统计和权重表同版本。
    # source_start, source_end =await required_source_window(args.start_date, args.end_date, for_training=False)
    # # raw_df = await read_feature_source(RAW_SOURCE_PATH)
    #
    # bundle = await load_score_bundle(WEIGHT_TABLE_PATH)
    #
    # bundle['xgb_weight_table']=await get_weights(args.end_date,bundle['xgb_weight_table'])
    #
    # raw_df = await read_feature_source_table("tmp_vrp_00_feature_source")
    #
    # # 2. 评分：SCORE_OUTPUT_MODE 控制 01/05 使用正式分或评分卡分，默认 formal。
    # tables = await ScoreUpdater(args.start_date, args.end_date, args.create_date).run(raw_df, bundle)
    # score_date = str(tables["daily_monitor"]["统计日期"].iloc[0])
    #
    # # 3. 输出：每张表单独一行，后续改写库时更容易替换。
    # # 默认业务写库一般只需要 01 汇总表 + 05 贡献表；07/08/09 可作为监控审计表按需入库。
    # save_01_summary_scores(tables["summary_scores"], out_dir, score_date)
    # save_02_original_values(tables["original_values"], out_dir, score_date)
    # save_03_normalized_values(tables["normalized_values"], out_dir, score_date)
    # save_04_contribution_values(tables["contribution_values"], out_dir, score_date)
    # save_05_daily_monitor(tables["daily_monitor"], out_dir, score_date)
    # save_06_unscoreable_vehicles(tables["unscoreable_vehicles"], out_dir, score_date)
    # save_07_missing_fill_records(tables["missing_fill_records"], out_dir, score_date)
    #
    # result={}
    # result['summary_scores'] = tables["summary_scores"]
    # result['original_values']=tables["original_values"]
    # result['normalized_values'] = tables["normalized_values"]
    # result['contribution_values'] = tables["contribution_values"]
    # result['daily_monitor'] = tables["daily_monitor"]
    # result['unscoreable_vehicles'] = tables["unscoreable_vehicles"]
    # result['missing_fill_records'] = tables["missing_fill_records"]
    # await save_scores(result, args.start_date, args.end_date)
    # logger.info(f"[输出] 01/03/04/05/07/08/09 已生成 | 口径={SCORE_OUTPUT_MODE} | 原始数据窗口={source_start}~{source_end}")

def build_default_args(start_date:str,end_date:str):
    args = argparse.Namespace()
    args.start_date = start_date
    args.end_date = end_date
    args.create_date = start_date
    args.weight_month = None
    return args

async def vehicle_score_main(start_time:str,end_time:str):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='画像',
        module_name='车辆画像',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_time,
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

    _start_time = start_time
    _end_date = datetime.strptime(_start_time, '%Y-%m-%d')
    _end_time = _end_date.strftime('%Y-%m-%d')
    args = build_default_args(_start_time, _end_time)

    w_create_date = _end_date - timedelta(days=_end_date.day - 1)
    w_start_date = get_last_month_day(w_create_date)
    w_end_date = w_create_date-timedelta(days=1)
    w_create_date_str=w_create_date.strftime('%Y%m%d')
    w_start_date_str=w_start_date.strftime('%Y%m%d')
    w_end_date_str=w_end_date.strftime('%Y%m%d')
    w_ym=_end_time[:7]
    WEIGHT_TABLE_PATH = f"output/weight_{w_start_date_str}_{w_end_date_str}_{w_create_date_str}/02_weights/XGB正式权重表_{w_ym}_{w_create_date.strftime('%Y-%m-%d')}.csv"

    out_dir = make_score_dir(WEIGHT_TABLE_PATH, args.start_date, args.end_date)
    logger.configure(out_dir / "00_logs", "score", args.create_date)

    await data_init(args.start_date)

    # 1. 读入 raw 宽表和同版本模型产物。
    # 数据库对接时，可替换 raw_df 这一行，例如：
    # sqlwhere = f"stat_date BETWEEN '{source_start}' AND '{source_end}'"
    # raw_df = await read_raw_db("ai_security.tmp_vehicle_profile_feature_source", sqlwhere, "*")
    # bundle 若改为数据库读取，必须同时保证模型、metadata、填充统计、归一化统计和权重表同版本。
    source_start, source_end =await required_source_window(args.start_date, args.end_date, for_training=False)
    # raw_df = await read_feature_source(RAW_SOURCE_PATH)

    bundle = await load_score_bundle(WEIGHT_TABLE_PATH)

    bundle['xgb_weight_table']=await get_weights(args.end_date,bundle['xgb_weight_table'])

    raw_df = await read_feature_source_table("tmp_vrp_00_feature_source")

    # 2. 评分：SCORE_OUTPUT_MODE 控制 01/05 使用正式分或评分卡分，默认 formal。
    tables = await ScoreUpdater(args.start_date, args.end_date, args.create_date).run(raw_df, bundle)
    score_date = str(tables["daily_monitor"]["统计日期"].iloc[0])

    # 3. 输出：每张表单独一行，后续改写库时更容易替换。
    # 默认业务写库一般只需要 01 汇总表 + 05 贡献表；07/08/09 可作为监控审计表按需入库。
    save_01_summary_scores(tables["summary_scores"], out_dir, score_date)
    save_02_original_values(tables["original_values"], out_dir, score_date)
    save_03_normalized_values(tables["normalized_values"], out_dir, score_date)
    save_04_contribution_values(tables["contribution_values"], out_dir, score_date)
    save_05_daily_monitor(tables["daily_monitor"], out_dir, score_date)
    save_06_unscoreable_vehicles(tables["unscoreable_vehicles"], out_dir, score_date)
    save_07_missing_fill_records(tables["missing_fill_records"], out_dir, score_date)

    result={}
    result['summary_scores'] = tables["summary_scores"]
    result['original_values']=tables["original_values"]
    result['normalized_values'] = tables["normalized_values"]
    result['contribution_values'] = tables["contribution_values"]
    result['daily_monitor'] = tables["daily_monitor"]
    result['unscoreable_vehicles'] = tables["unscoreable_vehicles"]
    result['missing_fill_records'] = tables["missing_fill_records"]

    await save_scores(result, args.start_date, args.end_date)
    logger.info(f"[输出] 01/03/04/05/07/08/09 已生成 | 口径={SCORE_OUTPUT_MODE} | 原始数据窗口={source_start}~{source_end}")

    remark = '车辆画像计算完成'
    await update_moudle_log(_id, remark)


async def get_vehicle_report(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            list = await crud.Vehicle(client).get_vehicle_report(_ppartition)
            for data in list:
                payload = {
                    "numberPlate": data["bus_name"],
                    "ppartition": data["ppartition"],
                }
                logger.info(f"获取车辆{data['bus_name']}：{start_date}总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                result=await report_main(payload)
                logger.info(f"获取车辆{data['bus_name']}：{start_date}总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(result)
    except Exception as e:
        logger.info(f"生成车辆报告执行出错: {e}")
        print(f"生成车辆报告执行出错: {e}")
    print("数据库连接已关闭")

if __name__ == "__main__":
    path="output/weight_20260401_20260430_20260501/scores/score_2026-05-01/01_评分汇总表_2026-05-01.csv"
    p_dir = Path(path)
    summary_scores = read_csv(p_dir)
    print(f"<UNK>{p_dir}<UNK>")
    path="output/weight_20260401_20260430_20260501/scores/score_2026-05-01/02_特征原值表_2026-05-01.csv"
    p_dir = Path(path)
    original_values = read_csv(p_dir)
    path = "output/weight_20260401_20260430_20260501/scores/score_2026-05-01/04_特征贡献值表_2026-05-01.csv"
    p_dir = Path(path)
    contribution_values = read_csv(p_dir)
    result = {}
    result['summary_scores'] = summary_scores
    result['original_values'] = original_values
    result['contribution_values'] = contribution_values
    asyncio.run(save_scores(result, '2026-05-01', '2026-05-01'))
    # # weight_dir = Path(path)
    # # summary_scores = read_csv(weight_dir)
    # #
    # # out_dir = make_score_dir(WEIGHT_TABLE_PATH, '2026-05-01', '2026-05-01')
    # # print(f"<UNK>{out_dir}<UNK>")
    # asyncio.run(main())

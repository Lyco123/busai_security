# -*- coding: utf-8 -*-
"""本地权重入口：读入 raw 宽表 -> 训练 -> 输出 Weight 产物。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from core import sql_config
from core.clickhouse_connect import connect_to_clickhouse
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.vehicle.src import crud
from model.vehicle.src.crud import save_weights_dict
from model.vehicle.src.data_io import read_feature_source, save_weight_result, read_feature_source_table, read_csv
from model.vehicle.src.features import required_source_window
from model.vehicle.src.modeling import WeightUpdater
from model.vehicle.src.utils import get_date_token, logger
from utils.tools import get_last_month_day, get_last_half_year_day

# =========================
# 运行配置：日常主要改这里
# =========================
START_DATE = "2026-04-01"
END_DATE = "2026-04-30"
CREATE_DATE = "2026-05-01"
RAW_SOURCE_PATH = "data/*feature_source*.csv"
OUTPUT_DIR = "output"


def parse_args():
    parser = argparse.ArgumentParser(description="车辆画像权重更新")
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument("--end-date", default=END_DATE)
    parser.add_argument("--create-date", default=CREATE_DATE)
    return parser.parse_args()


def make_weight_paths(start_date: str, end_date: str, create_date: str):
    """创建当前训练批次目录。"""
    name = f"weight_{get_date_token(start_date)}_{get_date_token(end_date)}_{get_date_token(create_date)}"
    root = Path(OUTPUT_DIR) / name
    paths = SimpleNamespace(
        batch_name=name,
        batch_dir=root,
        logs_dir=root / "00_logs",
        models_dir=root / "01_models",
        weights_dir=root / "02_weights",
        scores_dir=root / "scores",
    )
    for path in [paths.logs_dir, paths.models_dir, paths.weights_dir, paths.scores_dir]:
        path.mkdir(parents=True, exist_ok=True)
    return paths

async def data_init(start_time):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_time, "%Y-%m-%d")
            start_date = get_last_month_day(end_date)
            end_date=end_date-timedelta(days=1)
            start_time_str = start_date.strftime("%Y%m%d")
            end_time_str = end_date.strftime("%Y%m%d")

            logger.info(f"车辆{start_date}--{end_date}风险权重数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            try:
              s_start_date = get_last_half_year_day(end_date).strftime("%Y-%m-%d")
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
                print(f"车辆计算权重半年数据存入临时表执行出错: {e}")
            logger.info(f"车辆{start_date}--{end_date}风险权重数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"车辆计算权重半年数据存入临时表执行出错{e}")
        print(f"车辆计算权重半年数据存入临时表执行出错: {e}")



def build_default_args(start_date:str,end_date:str,create_date:str):
    args = argparse.Namespace()
    args.start_date = start_date
    args.end_date = end_date
    args.create_date = create_date
    args.weight_month = None
    return args


def build_weight_log_summary(model_evaluation):
    """构建权重更新模块的精简日志。"""
    if model_evaluation is None:
        return []

    if hasattr(model_evaluation, "to_dict"):
        records = model_evaluation.to_dict("records")
    elif isinstance(model_evaluation, list):
        records = model_evaluation
    else:
        return []
    key_fields = [
        "模型名称",
        "正样本数",
        "预测高风险数",
        "命中数",
        "Precision",
        "Recall",
        "F1",
        "F2",
    ]
    summary = []

    for row in records:
        if not isinstance(row, dict):
            continue

        # 只保留验证集结果，不保留 train/test/all 等其他范围
        scope = row.get("evaluation_scope")
        if scope is not None and scope != "validation":
            continue

        item = {}
        for field in key_fields:
            if field in row:
                item[field] = row[field]

        if item:
            summary.append(item)

    return summary


async def vehicle_weight_main(start_date:str,end_date:str,create_date:str):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='车辆权重',
        pid=str(os.getpid()),
        remark='',
        calculate_date=create_date,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict,"obs_module_weight_log")

    args = build_default_args(start_date, end_date, create_date)
    paths = make_weight_paths(args.start_date, args.end_date,args.create_date)
    logger.configure(paths.logs_dir, "weight", create_date)

    await data_init(args.create_date)

    source_start, source_end = await required_source_window(args.start_date, args.end_date, for_training=True)
    raw_df = await read_feature_source_table("tmp_vrp_00_feature_source")

    # 2. 训练：modeling.py 只负责计算。
    result = await WeightUpdater(args.start_date, args.end_date, args.create_date).run(raw_df)

    # 3. 输出：当前写本地模型 json、metadata、权重表、填充/归一化统计。
    # 数据库对接时，可在 save_weight_result() 内补充：
    # await save_weights_dict(args.start_date, args.end_date, result["xgb_weight_table"].to_dict("records"))
    model_evaluation=await save_weight_result(result, paths, args.start_date, args.end_date)
    # s = json.dumps(model_evaluation, indent=2, ensure_ascii=False)
    # remark=s
    # 模块日志只写验证集核心指标，完整明细仍保存到“模型效果表”CSV。
    log_summary = build_weight_log_summary(model_evaluation)
    remark = json.dumps(log_summary, ensure_ascii=False)
    await update_moudle_log(_id,remark,"obs_module_weight_log")

    logger.info(f"[输出] Weight 本地产物已生成 | 原始数据窗口={source_start}~{source_end}")


async def main():
    args = parse_args()
    paths = make_weight_paths(args.start_date, args.end_date, args.create_date)
    logger.configure(paths.logs_dir, "weight", args.create_date)

    # await data_init(args.create_date)
    source_start, source_end = await required_source_window(args.start_date, args.end_date, for_training=True)
    raw_df = await read_feature_source_table("tmp_vrp_00_feature_source")

    # 2. 训练：modeling.py 只负责计算。
    result = await WeightUpdater(args.start_date, args.end_date, args.create_date).run(raw_df)

    # 3. 输出：当前写本地模型 json、metadata、权重表、填充/归一化统计。
    # 数据库对接时，可在 save_weight_result() 内补充：
    # await save_weights_dict(args.start_date, args.end_date, result["xgb_weight_table"].to_dict("records"))
    await save_weight_result(result, paths,args.start_date, args.end_date)
    logger.info(f"[输出] Weight 本地产物已生成 | 原始数据窗口={source_start}~{source_end}")


if __name__ == "__main__":
    path = "output/weight_20260401_20260430_20260501/02_weights/模型效果表_2026-05_2026-05-01.csv"
    p_dir = Path(path)
    xgb_weight_table = read_csv(p_dir)
    # s=json.dumps(xgb_weight_table.to_dict("records"),indent=2, ensure_ascii=False)
    # print(s)
    # 避免本地直接运行时打印完整权重表造成控制台日志过长。
    print(f"权重表读取成功：{len(xgb_weight_table)} 行，文件={p_dir}")
    # asyncio.run(save_weights_dict("2026-04-01", "2026-04-30", xgb_weight_table.to_dict("records")))
    # asyncio.run(main())

# -*- coding: utf-8 -*-
import argparse
import asyncio
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd

from core.clickhouse_connect import connect_to_clickhouse
from core.sql_config import get_risk_value
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.vehicle.src import crud
from model.vehicle.src.crud import save_scores
from model.vehicle.src.score_builder import ScoreUpdater
from model.vehicle.src.utils.common import parse_date_range_args, read_raw_file, build_batch_paths
from model.vehicle.src.utils.logger import logger


def build_default_args(start_time, end_time):
    args = argparse.Namespace()
    args.start_date = start_time
    args.end_date = end_time
    # args.create_date = (datetime.strptime(end_time, "%Y-%m-%d")+timedelta(days=1)).strftime("%Y-%m-%d")
    args.create_date = (datetime.strptime(end_time, "%Y-%m-%d")).strftime("%Y-%m-%d")
    args.weight_month = None
    return args


async def vehicle_score_main(start_time:str,end_time:str):
    # start_time = datetime.now().strftime("%Y-%m-%d")
    # _start_time=start_time.strip("%Y-%m-%d")
    #+timedelta(days=6)
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

    _start_time=start_time
    _end_time=datetime.strptime(_start_time,'%Y-%m-%d')
    _end_time=_end_time.strftime('%Y-%m-%d')
    default_args = build_default_args(_start_time,_end_time)
    args = parse_date_range_args("vehicle 评分更新", default_args=default_args, include_weight_month=True)
    batch_paths = await build_batch_paths("score", args.start_date, args.end_date, args.create_date)
    logger.configure(batch_paths.logs_dir, "score", args.create_date, batch_paths.batch_name)
    try:
        await ScoreUpdater(
            args.start_date,
            args.end_date,
            args.create_date,
            weight_month=args.weight_month,
            batch_paths=batch_paths,
        ).run()
        logger.chapter("评分更新完成")
    except Exception as e:
        logger.error(f"评分更新失败：{e}")
        raise

    remark = '车辆画像计算完成'
    await update_moudle_log(_id, remark)

async def test():
    try:
        async with await connect_to_clickhouse() as client:
            sss=await crud.Vehicle(client).get_risk_value(55)
            print(sss)
    except Exception as e:
        logger.error("车辆画像主程序执行出错", exc_info=True)
        print(f"车辆画像主程序执行出错: {e}")
    print("数据库连接已关闭")
if __name__ == "__main__":
    # final_contrib_df = read_raw_file("最终贡献分表_2026-01-04.csv", source="raw")
    # original_df = read_raw_file("原值表_2026-01-04.csv", source="raw")
    # normalized_df = read_raw_file("归一化值表_2026-01-04.csv", source="raw")
    # raw_risk_df = read_raw_file("原始风险分表_2026-01-04.csv", source="raw")
    # missing_df = read_raw_file("缺失值检查表_2026-01-04.csv", source="raw")
    # result = {}
    # final_contrib_df = final_contrib_df.apply(
    #     lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
    # original_df = original_df.apply(
    #     lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
    # normalized_df = normalized_df.apply(
    #     lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
    # raw_risk_df = raw_risk_df.apply(
    #     lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
    # missing_df = missing_df.apply(
    #     lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
    # result['final_contrib_df']=final_contrib_df
    # result['original_df'] = original_df
    # result['normalized_df']=normalized_df
    # result['raw_risk_df']=raw_risk_df
    # result['missing_df']=missing_df
    # asyncio.run(save_scores(result, '2025-12-29', '2026-01-04'))
    # asyncio.run(test())
    date_range = pd.date_range(start="2025-12-29", end="2025-12-29")
    for date in date_range:
        start_time = date.to_pydatetime()
        start_time_str = start_time.strftime("%Y-%m-%d")
        asyncio.run(vehicle_score_main(start_time_str))

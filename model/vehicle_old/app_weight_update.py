# -*- coding: utf-8 -*-
import argparse
import asyncio
import os
import uuid
from datetime import datetime

from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.vehicle.src.crud import save_weights_dict
from model.vehicle.src.utils.common import parse_date_range_args, read_raw_file, build_batch_paths
from model.vehicle.src.utils.logger import logger
from model.vehicle.src.weight_trainer import WeightUpdater


def build_default_args(start_date:str,end_date:str,create_date:str):
    args = argparse.Namespace()
    args.start_date = start_date
    args.end_date = end_date
    args.create_date = create_date
    args.weight_month = None
    return args


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
    await insert_moudle_log(log_dict)

    default_args = build_default_args(start_date,end_date,create_date)
    args = parse_date_range_args("vehicle 权重更新", default_args=default_args, include_weight_month=True)
    batch_paths = await build_batch_paths("weight", args.start_date, args.end_date, args.create_date)
    logger.configure(batch_paths.logs_dir, "weight", args.create_date, batch_paths.batch_name)
    try:
        await WeightUpdater(
            args.start_date,
            args.end_date,
            args.create_date,
            weight_month=args.weight_month,
            batch_paths=batch_paths,
        ).run()
        logger.chapter("权重更新完成")
    except Exception:
        logger.error("权重更新失败")
        raise

    remark=''
    await update_moudle_log(_id,remark)

if __name__ == "__main__":
    # local_weight_df = read_raw_file("车辆画像权重SQL读取表_2026-01_2026-01-01.csv", source="raw")
    # asyncio.run(save_weights_dict(local_weight_df.to_dict("records")))
    asyncio.run(vehicle_weight_main("2025-12-01","2025-12-31","2026-01-01"))

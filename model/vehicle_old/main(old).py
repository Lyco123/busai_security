# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timedelta

from model.vehicle.src.utils.common import OUT_DIR, get_pipeline_args
from model.vehicle.src.utils.logger import logger
from model.vehicle.src.pipeline_01_feature import build_wide_table
from model.vehicle.src.pipeline_02_model import ModelPipeline
from model.vehicle.src.pipeline_03_score import FeatureScorer
from utils.tools import get_next_month_day, get_last_month_day


async def vechicle_weights_main():
    # 1. 获取统一参数 (一行代码搞定时间默认值和命令行解析)
    start_date_='2026-01-01'
    start_date = datetime.strptime(start_date_, '%Y-%m-%d')
    start_date_=(start_date-timedelta(days=1)).strftime('%Y-%m-%d')
    end_date=get_last_month_day(start_date)
    end_date_=end_date.strftime('%Y-%m-%d')
    args = get_pipeline_args("主流程：车辆画像模型",end_date_,start_date_)
    # 2. 创建批次输出目录
    output_base = OUT_DIR / f"run_{args.run_date}"
    output_base.mkdir(parents=True, exist_ok=True)

    logger.chapter(f"🚀 流程启动 | 时间: {args.start_date} ~ {args.end_date} | 批次: {args.run_date}")
    
    try:
        # logger.chapter("步骤 1/3: 构建特征宽表")
        await build_wide_table(args.start_date, args.end_date)

        # logger.chapter("步骤 2/3: 模型训练与预测")
        await ModelPipeline(args.start_date, args.end_date, output_base).run()
        
        # logger.chapter("步骤 3/3: 特征评分与分片导出")
        # await FeatureScorer(args.start_date, args.end_date, output_base, args.run_date).run()

        logger.chapter(f"✅ 流程全部成功！结果已存至: {output_base}")
        
    except Exception as e:
        logger.exception("❌ 流程执行失败:")
        raise


async def vechicle_score_main():
    # 1. 获取统一参数 (一行代码搞定时间默认值和命令行解析)
    start_date_ = '2025-12-01'
    start_date = datetime.strptime(start_date_, '%Y-%m-%d')
    end_date = start_date+timedelta(days=6)
    end_date_ = end_date.strftime('%Y-%m-%d')
    args = get_pipeline_args("主流程：车辆画像模型",start_date_,end_date_)

    # 2. 创建批次输出目录
    output_base = OUT_DIR / f"run_{args.run_date}"
    output_base.mkdir(parents=True, exist_ok=True)

    logger.chapter(f"🚀 流程启动 | 时间: {args.start_date} ~ {args.end_date} | 批次: {args.run_date}")

    try:

        logger.chapter("步骤 3/3: 特征评分与分片导出")
        await FeatureScorer(args.start_date, args.end_date, output_base, args.run_date).run()

        logger.chapter(f"✅ 流程全部成功！结果已存至: {output_base}")

    except Exception as e:
        logger.exception("❌ 流程执行失败:")
        raise

if __name__ == "__main__":
    asyncio.run(vechicle_weights_main())
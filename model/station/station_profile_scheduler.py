import asyncio
from datetime import datetime, timedelta
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from clickhouse_driver import Client
from fastapi import Depends

from application.settings import HOUR, MINUTE, interval_minutes
from core.database import clickhouse_getter

from core.logger import logger
from model.driver.main import driver_score_main, driver_weights_main
from model.route.main_route_quota_weight_month import route_quota_weight_main
from model.route.main_route_risk_score import route_cores
from model.route.route_black_point_prediction.accident_black_point_prediction_model import accident_black_main
from model.route.route_black_point_prediction.behavior_black_point_prediction_model import behavior_black_main
from model.station.score_roadside_stations import station_score_main, station_all_weights_main


def start_scheduler_sync_station():
    """
    同步版本的调度器启动函数
    专门用于multiprocessing.Process调用
    """
    # 配置执行器
    executors = {
        'default': ThreadPoolExecutor(2)
    }

    job_defaults = {
        'coalesce': False,
        'max_instances': 2
    }

    # 创建调度器
    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone = 'Asia/Shanghai'  # 全局时区
    )

    # 配置站场权重任务 - 每个月1号凌晨7点执行
    scheduler.add_job(
        scheduled_task_station_weights,
        trigger=CronTrigger(minute=MINUTE, hour=HOUR, day='1'),
        misfire_grace_time=300,
        id='station_weights_monthly',
        name=f'站场权重每月计算任务-每月1号{HOUR}点{MINUTE}分'
    )

    # 计算线路分数任务 - 每周一7点40分执行一次
    scheduler.add_job(
        scheduled_task_station_score,
        trigger=CronTrigger(day_of_week='mon', hour=HOUR, minute=MINUTE+10),
        misfire_grace_time=300,
        id='station_score_weekly',
        name=f'站场评分每周计算任务-每周一{HOUR}点{MINUTE+10}分'
    )


    scheduler.start()
    logger.info("调度器已在独立进程中启动")

    # 保持进程运行
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("调度器已关闭")



#每周一
def scheduled_task_station_score():
    """站场画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time=(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time}:计算站场分数")
            result = loop.run_until_complete(station_score_main(start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"站场分数计算任务失败: {e}")

#每月1日
def scheduled_task_station_weights():
    """站场画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time = datetime.now().strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time}:计算站场权重")
            result = loop.run_until_complete(station_all_weights_main(start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"站场权重计算任务失败: {e}")



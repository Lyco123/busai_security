import asyncio
from datetime import datetime, timedelta
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from application.settings import HOUR, MINUTE
from core.logger import logger
from model.vehicle.app_score_update import vehicle_score_main
from model.vehicle.app_weight_update import vehicle_weight_main
from utils.tools import get_last_month_day


def start_scheduler_sync_vehicle():
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
        timezone='Asia/Shanghai'  # 全局时区
    )

    # 配置车辆权重任务 - 每个月1号凌晨5点执行
    scheduler.add_job(
        scheduled_task_vehicle_weights,
        trigger=CronTrigger(minute=MINUTE-15, hour=HOUR+2, day='1'),
        misfire_grace_time=300,
        id='vehicle_weights_monthly',
        name=f'车辆权重每月计算任务-每月1日{HOUR+2}点{MINUTE-15}分'
    )

    # 计算车辆分数任务 - 每天9点25执行一次
    scheduler.add_job(
        scheduled_task_vehicle_score,
        trigger=CronTrigger(hour=HOUR+2, minute=MINUTE-5),
        misfire_grace_time=300,
        id='vehicle_score_days',
        name=f'车辆评分每天计算任务-每天{HOUR+2}点{MINUTE-5}分'
    )

    # 计算车辆分数任务 - 每天8点30第二执行
    scheduler.add_job(
        scheduled_task_vehicle_score_two,
        trigger=CronTrigger(hour=HOUR+1, minute=MINUTE),
        misfire_grace_time=300,
        id='vehicle_score_days_two',
        name=f'车辆评分第二次计算任务-每天{HOUR+1}点{MINUTE}分'
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
def scheduled_task_vehicle_score():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time_one = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time_one}:计算车辆分数")
            result = loop.run_until_complete(vehicle_score_main(start_time_one,start_time_one))
            # return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"线路分数计算任务失败: {e}")

def scheduled_task_vehicle_score_two():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            start_time_two = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time_two}:计算车辆分数")
            result = loop.run_until_complete(vehicle_score_main(start_time_two,start_time_two))
            # return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"线路分数计算任务失败: {e}")

#每月1日
def scheduled_task_vehicle_weights():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time = datetime.now().strftime('%Y-%m-%d')
            first_month_day = get_last_month_day(datetime.now()).strftime('%Y-%m-%d')
            last_month_day = (datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time}:计算车辆权重")
            result = loop.run_until_complete(vehicle_weight_main(first_month_day,last_month_day,start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"线路权重计算任务失败: {e}")
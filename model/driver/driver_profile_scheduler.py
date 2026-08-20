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
from model.driver.main import driver_score_main, driver_weights_main, driver_weight_data_init, \
    driver_behavior_data_init, driver_score_hour_main


def start_scheduler_sync_driver():
    """
    同步版本的调度器启动函数
    专门用于multiprocessing.Process调用
    """
    # 配置执行器
    executors = {
        'default': ThreadPoolExecutor(3)
    }

    job_defaults = {
        'coalesce': False,
        'max_instances': 3
    }

    # 创建调度器
    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone = 'Asia/Shanghai'  # 全局时区
    )

    # 配置驾驶员权重任务 - 每个月1号凌晨7点执行
    scheduler.add_job(
        scheduled_task_driver_weights,
        trigger=CronTrigger(minute=MINUTE-20, hour=HOUR, day='1-5'),
        misfire_grace_time=300,
        id='driver_weights_monthly',
        name=f'驾驶员权重每月计算任务-每个月1-5号{HOUR}点{MINUTE-20}分'
    )


    # 配置驾驶员评分任务 - 每天凌晨7点30执行
    scheduler.add_job(
        scheduled_task_driver_score,
        trigger=CronTrigger(hour=HOUR, minute=MINUTE+20),
        misfire_grace_time=300,
        id='driver_score_daily',
        name=f'驾驶员评分每日计算任务-每天{HOUR}点{MINUTE+20}分'
    )


    # 配置驾驶员评分任务 - 每天凌晨8点30执行
    scheduler.add_job(
        scheduled_task_driver_score_two,
        trigger=CronTrigger(hour=HOUR+1, minute=MINUTE),
        misfire_grace_time=300,
        id='driver_score_daily_two',
        name=f'驾驶员评分第二次计算任务-每天{HOUR+1}点{MINUTE}分'
    )

    # # 配置驾驶员事故风险 - 每小时执行
    # scheduler.add_job(
    #     scheduled_task_driver_hour_score,
    #     trigger=CronTrigger(minute=0),
    #     misfire_grace_time=300,
    #     id='driver_score_hour',
    #     name='驾驶员事故风险每小时计算任务'
    # )


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


# def start_scheduler_sync_data_init():
#     """
#     同步版本的调度器启动函数
#     专门用于multiprocessing.Process调用
#     """
#     # 配置执行器
#     executors = {
#         'default': ThreadPoolExecutor(2)
#     }
#
#     job_defaults = {
#         'coalesce': False,
#         'max_instances': 2
#     }
#
#     # 创建调度器
#     scheduler = BackgroundScheduler(
#         executors=executors,
#         job_defaults=job_defaults
#     )
#
#     # 配置驾驶员权重任务 - 每个月1号凌晨5点执行
#     scheduler.add_job(
#         scheduled_task_driver_weights_data_init,
#         trigger=CronTrigger(minute='0', hour='5', day='1'),
#         misfire_grace_time=300,
#         id='driver_weights_monthly',
#         name='驾驶员权重每月计算任务'
#     )
#
#
#     # 驾驶员行为汇总任务 - 每天凌晨5点30执行
#     scheduler.add_job(
#         scheduled_task_driver_behavior_data_init,
#         trigger=CronTrigger(hour=5, minute=30),
#         misfire_grace_time=300,
#         id='driver_score_daily',
#         name='驾驶员评分每日计算任务'
#     )
#
#     scheduler.start()
#     logger.info("调度器已在独立进程中启动")
#
#     # 保持进程运行
#     try:
#         while True:
#             import time
#             time.sleep(1)
#     except KeyboardInterrupt:
#         scheduler.shutdown()
#         logger.info("调度器已关闭")



#每天
def scheduled_task_driver_score():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time_one=(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time_one}:计算驾驶员分数")
            result = loop.run_until_complete(driver_score_main(start_time_one,start_time_one))
                # return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")

    # 每天
def scheduled_task_driver_score_two():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time_two = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time_two}:计算驾驶员分数")
            result = loop.run_until_complete(driver_score_main(start_time_two, start_time_two))
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")

#每小时
def scheduled_task_driver_hour_score():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time = datetime.now().strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time}:计算驾驶员小时风险分数")
            result = loop.run_until_complete(driver_score_hour_main(start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")

# def scheduled_task_driver_behavior_data_init():
#     """驾驶员画像定时器"""
#     try:
#         # 创建新的事件循环
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#
#         try:
#             # 运行异步任务
#             result = loop.run_until_complete(driver_behavior_data_init())
#             return result
#         finally:
#             loop.close()
#
#     except Exception as e:
#         logger.error(f"距离计算任务失败: {e}")


# def scheduled_task_driver_weights_data_init():
#     """驾驶员画像定时器"""
#     try:
#         # 创建新的事件循环
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#
#         try:
#             # 运行异步任务
#             result = loop.run_until_complete(driver_weight_data_init())
#             return result
#         finally:
#             loop.close()
#
#     except Exception as e:
#         logger.error(f"距离计算任务失败: {e}")

#每月1日
def scheduled_task_driver_weights():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time = datetime.now().strftime('%Y-%m-%d')
            print(f"{datetime.now()}======{start_time}:计算驾驶员权重")
            result = loop.run_until_complete(driver_weights_main(start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")





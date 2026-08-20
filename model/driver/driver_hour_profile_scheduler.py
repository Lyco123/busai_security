import asyncio
import time
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


def start_scheduler_sync_hour_driver():
    """
    同步版本的调度器启动函数
    专门用于 multiprocessing.Process 调用
    """
    # 1. 配置执行器
    # 根据任务IO/CPU特性调整线程数。如果是IO密集型（如数据库/网络请求），可适当增加
    executors = {
        'default': ThreadPoolExecutor(1)
    }

    # 2. 配置全局任务默认值
    job_defaults = {
        'coalesce': False,  # 不合并错过的执行，确保每次触发都尝试执行（根据业务需求调整）
        'max_instances': 2,  # 允许最多2个实例并行运行
        'misfire_grace_time': 300  # 全局默认容错时间5分钟
    }

    # 3. 创建调度器
    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone='Asia/Shanghai'  # 显式指定时区
    )

    try:
        # 4. 添加任务
        scheduler.add_job(
            func=scheduled_task_driver_hour_score,
            trigger=CronTrigger(minute=0),  # 每小时整点执行
            id='driver_score_hour',
            name='驾驶员事故风险小时计算任务',
            replace_existing=True,  # 如果ID存在则替换，防止重启后重复添加
            misfire_grace_time=300  # 单独设置该任务的容错时间
        )

        # 5. 启动调度器
        scheduler.start()
        logger.info("驾驶员事故风险小时计算任务调度器已在独立进程中启动")

        # 6. 保持进程运行
        while True:
            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到退出信号，准备关闭调度器...")
    except Exception as e:
        logger.error(f"调度器运行过程中发生错误: {e}", exc_info=True)
    finally:
        # 7. 确保资源释放
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("调度器已安全关闭，资源已释放")



# #每小时
# def scheduled_task_driver_hour_score():
#     """驾驶员画像定时器"""
#     try:
#         # 创建新的事件循环
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#
#         try:
#             # 运行异步任务
#             start_time = datetime.now().strftime('%Y-%m-%d')
#             print(f"{datetime.now()}======{start_time}:计算驾驶员小时风险分数")
#             result = loop.run_until_complete(driver_score_hour_main(start_time))
#             return result
#         finally:
#             loop.close()
#
#     except Exception as e:
#         logger.error(f"距离计算任务失败: {e}")


def scheduled_task_driver_hour_score():
    """
    驾驶员画像定时器 - 同步包装器
    用于在同步环境（如定时任务线程）中运行异步任务
    """
    start_time = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now()

    try:
        print(f"{current_time}======{start_time}:计算驾驶员小时风险分数")

        # asyncio.run 是 Python 3.7+ 推荐的方式
        # 它会自动创建新的事件循环，运行协程，然后关闭循环并清理资源
        result = asyncio.run(driver_score_hour_main(start_time))

        return result

    except Exception as e:
        # 修正日志描述，并打印堆栈跟踪以便调试
        logger.error(f"驾驶员小时风险分数计算任务失败: {e}", exc_info=True)

        # 重要：重新抛出异常
        # 这样 APScheduler 等调度框架才能捕获到错误，进行重试或记录失败状态
        raise




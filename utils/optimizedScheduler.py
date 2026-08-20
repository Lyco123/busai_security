import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from application.settings import HOUR, MINUTE, interval_minutes

from core.logger import logger
from utils.can_decrypt import decrypt_main



def start_scheduler_sync():
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
        'max_instances': 4
    }

    # 创建调度器
    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults
    )

    scheduler.add_job(
        scheduled_task_can,
        trigger=CronTrigger(second='*/10'),  # 修改为每30秒执行
        misfire_grace_time=300
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



def start_scheduler_sync_day():
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
        'max_instances': 4
    }

    # 创建调度器
    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults
    )

    scheduler.add_job(
        scheduled_task_day,
        trigger=CronTrigger(second='*/10'),  # 修改为每30秒执行
        misfire_grace_time=300
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




def scheduled_task_can():
    """同步包装器，在内部运行异步任务"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            result = loop.run_until_complete(decrypt_main())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")

def scheduled_task_day():
    """同步包装器，在内部运行异步任务"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            result = loop.run_until_complete(decrypt_main())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")



# if __name__ == "__main__":
#      decrypt_can()
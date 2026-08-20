import asyncio
from datetime import datetime, timedelta
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from application.settings import HOUR, MINUTE
from core.logger import logger
from model.company.main import company_score_main, company_weights_main


def start_scheduler_sync_company():
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


    # 计算单位分数任务 - 每周一9点40分执行一次
    scheduler.add_job(
        scheduled_task_company_score,
        trigger=CronTrigger(day_of_week='mon', hour=HOUR+2, minute=MINUTE+20),
        misfire_grace_time=300,
        id='company_score_weekly',
        name=f'单位评分、事故评分每周计算任务-每周一{HOUR+2}时{MINUTE+20}分'
    )

    # 配置单位、事故权重任务 - 每个月1号凌晨7点30点执行
    scheduler.add_job(
        scheduled_task_company_weights,
        trigger=CronTrigger(minute=MINUTE, hour=HOUR, day='1'),
        misfire_grace_time=300,
        id='company_weights_monthly',
        name=f'单位、事故权重每月计算任务-每月1日{HOUR}时{MINUTE}分'
    )

    # 配置单位评分、事故评分评分任务 - 每天凌晨9点50执行
    scheduler.add_job(
        scheduled_task_company_score_two,
        trigger=CronTrigger(day_of_week='mon', hour=HOUR+2, minute=MINUTE+20),
        misfire_grace_time=300,
        id='company_score_weekly_two',
        name=f'单位评分、事故评分第二次计算任务-每周一{HOUR+2}点{MINUTE+20}分'
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
def scheduled_task_company_score():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time_one = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time_one}:计算单位分数")
            result = loop.run_until_complete(company_score_main(start_time_one))
                # return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"线路分数计算任务失败: {e}")

def scheduled_task_company_score_two():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time_two = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time_two}:计算单位分数")
            result = loop.run_until_complete(company_score_main(start_time_two))
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"距离计算任务失败: {e}")

#每月1日
def scheduled_task_company_weights():
    """驾驶员画像定时器"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行异步任务
            start_time = datetime.now().strftime('%Y-%m-%d')
            print(f"{datetime.now()}====={start_time}:计算单位权重")
            result = loop.run_until_complete(company_weights_main(start_time))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"线路权重计算任务失败: {e}")
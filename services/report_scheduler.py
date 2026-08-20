import asyncio
from datetime import datetime, timedelta
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from application.settings import HOUR, MINUTE, REPORT_START_TIME
from core.logger import logger
from model.driver.main import get_driver_report
from model.route.main_route_risk_score import get_route_report, generate_reports_limited
from model.route.route_profile_scheduler import scheduled_task_route_score
from model.vehicle.app_score_update import vehicle_score_main
from model.vehicle.app_weight_update import vehicle_weight_main
from utils.tools import get_last_month_day


def start_scheduler_gen_report():
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

# 星期一‌	0
# ‌星期二‌	1
# ‌星期三‌	2
# ‌星期四‌	3
# ‌星期五‌	4
# ‌星期六‌	5
# ‌星期日‌	6
    scheduler.add_job(
        scheduled_route_report,
        trigger=CronTrigger(day_of_week=3, hour=REPORT_START_TIME, minute=17),
        misfire_grace_time=300,
        id='gen_route_report_week',
        name=f'线路总结报告生成任务-每周三{REPORT_START_TIME}点0分'
    )

    # 生成驾驶员报告- 每周1号晚上10点执行
    # scheduler.add_job(
    #     scheduled_drivers_report,
    #     trigger=CronTrigger(day_of_week=0,hour=REPORT_START_TIME,minute=0),
    #     misfire_grace_time=300,
    #     id='gen_drivers_report_week',
    #     name=f'驾驶员每周生成任务-每周一{REPORT_START_TIME}点0分'
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

#每周一
def scheduled_drivers_report():
    """
    驾驶员画像定时器 - 同步包装器
    用于在同步环境（如定时任务线程）中运行异步任务
    """
    start_time = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now()

    try:
        # asyncio.run 是 Python 3.7+ 推荐的方式
        # 它会自动创建新的事件循环，运行协程，然后关闭循环并清理资源
        result = asyncio.run(get_driver_report(start_time))
        return result

    except Exception as e:
        # 修正日志描述，并打印堆栈跟踪以便调试
        logger.error(f"驾驶员小时风险分数计算任务失败: {e}", exc_info=True)

        # 重要：重新抛出异常
        # 这样 APScheduler 等调度框架才能捕获到错误，进行重试或记录失败状态
        raise

def scheduled_route_report():
    """
    驾驶员画像定时器 - 同步包装器
    用于在同步环境（如定时任务线程）中运行异步任务
    """
    # 获取上周日
    last_sunday = datetime.now() - timedelta(days=(datetime.now().isoweekday() % 7))
    # 格式化输出
    start_time = last_sunday.strftime('%Y-%m-%d')

    try:
        # asyncio.run 是 Python 3.7+ 推荐的方式
        # 它会自动创建新的事件循环，运行协程，然后关闭循环并清理资源
        result = asyncio.run(generate_reports_limited(start_time))
        return result

    except Exception as e:
        # 修正日志描述，并打印堆栈跟踪以便调试
        logger.error(f"驾驶员小时风险分数计算任务失败: {e}", exc_info=True)

        # 重要：重新抛出异常
        # 这样 APScheduler 等调度框架才能捕获到错误，进行重试或记录失败状态
        raise

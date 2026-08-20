# @File           : event.py
# @IDE            : PyCharm
# @desc           : 全局事件
import asyncio
import multiprocessing
import time

import clickhouse_driver
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from application.settings import REDIS_DB_URL, MONGO_DB_URL, MONGO_DB_NAME, EVENTS, CLICKHOUSE_HOST, CLICKHOUSE_PORT, \
    CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE, CLICKHOUSE_NAME
from config import config
from model.company.company_profile_scheduler import start_scheduler_sync_company
from model.driver.driver_profile_scheduler import start_scheduler_sync_driver
from model.route.route_profile_scheduler import start_scheduler_sync_route
from model.vehicle.vehicle_profile_scheduler import start_scheduler_sync_vehicle
from services.ocr_engine import get_ocr_engine
from utils.cache import Cache
from redis import asyncio as aioredis
from redis.exceptions import AuthenticationError, TimeoutError, RedisError
from contextlib import asynccontextmanager

from utils.optimizedScheduler import start_scheduler_sync
from utils.scheduler_manager import SchedulerManager
from utils.tools import import_modules_async
from sqlalchemy.exc import ProgrammingError
from core.logger import logger

# 全局调度器进程列表
scheduler_processes = []

@asynccontextmanager
async def lifespan(app: FastAPI):

    await import_modules_async(EVENTS, "全局事件", app=app, status=True)
    # """应用生命周期管理"""
    # # 启动调度器进程


    yield  # 应用运行期间保持调度器运行

    await import_modules_async(EVENTS, "全局事件", app=app, status=False)

    # # 清理资源
    # for process in scheduler_processes:
    #     if process.is_alive():
    #         process.terminate()
    # print("已清理所有调度器进程")

async def connect_redis(app: FastAPI, status: bool):
    """
    把 redis 挂载到 app 对象上面

    博客：https://blog.csdn.net/wgPython/article/details/107668521
    博客：https://www.cnblogs.com/emunshe/p/15761597.html
    官网：https://aioredis.readthedocs.io/en/latest/getting-started/
    Github: https://github.com/aio-libs/aioredis-py

    aioredis.from_url(url, *, encoding=None, parser=None, decode_responses=False, db=None, password=None, ssl=None,
    connection_cls=None, loop=None, **kwargs) 方法是 aioredis 库中用于从 Redis 连接 URL 创建 Redis 连接对象的方法。

    以下是该方法的参数说明：
    url：Redis 连接 URL。例如 redis://localhost:6379/0。
    encoding：可选参数，Redis 编码格式。默认为 utf-8。
    parser：可选参数，Redis 数据解析器。默认为 None，表示使用默认解析器。
    decode_responses：可选参数，是否将 Redis 响应解码为 Python 字符串。默认为 False。
    db：可选参数，Redis 数据库编号。默认为 None。
    password：可选参数，Redis 认证密码。默认为 None，表示无需认证。
    ssl：可选参数，是否使用 SSL/TLS 加密连接。默认为 None。
    connection_cls：可选参数，Redis 连接类。默认为 None，表示使用默认连接类。
    loop：可选参数，用于创建连接对象的事件循环。默认为 None，表示使用默认事件循环。
    **kwargs：可选参数，其他连接参数，用于传递给 Redis 连接类的构造函数。

    aioredis.from_url() 方法的主要作用是将 Redis 连接 URL 转换为 Redis 连接对象。
    除了 URL 参数外，其他参数用于指定 Redis 连接的各种选项，例如 Redis 数据库编号、密码、SSL/TLS 加密等等。可以根据需要选择使用这些选项。

    health_check_interval 是 aioredis.from_url() 方法中的一个可选参数，用于设置 Redis 连接的健康检查间隔时间。
    健康检查是指在 Redis 连接池中使用的连接对象会定期向 Redis 服务器发送 PING 命令来检查连接是否仍然有效。
    该参数的默认值是 0，表示不进行健康检查。如果需要启用健康检查，则可以将该参数设置为一个正整数，表示检查间隔的秒数。
    例如，如果需要每隔 5 秒对 Redis 连接进行一次健康检查，则可以将 health_check_interval 设置为 5
    :param app:
    :param status:
    :return:
    """
    if status:
        rd = aioredis.from_url(REDIS_DB_URL, decode_responses=True, health_check_interval=1)
        app.state.redis = rd
        try:
            response = await rd.ping()
            if response:
                print("Redis 连接成功")
            else:
                print("Redis 连接失败")
        except AuthenticationError as e:
            raise AuthenticationError(f"Redis 连接认证失败，用户名或密码错误: {e}")
        except TimeoutError as e:
            raise TimeoutError(f"Redis 连接超时，地址或者端口错误: {e}")
        except RedisError as e:
            raise RedisError(f"Redis 连接失败: {e}")
        try:
            await Cache(app.state.redis).cache_tab_names()
        except ProgrammingError as e:
            logger.error(f"sqlalchemy.exc.ProgrammingError: {e}")
            print(f"sqlalchemy.exc.ProgrammingError: {e}")
    else:
        print("Redis 连接关闭")
        await app.state.redis.close()


async def connect_mongo(app: FastAPI, status: bool):
    """
    把 mongo 挂载到 app 对象上面

    博客：https://www.cnblogs.com/aduner/p/13532504.html
    mongodb 官网：https://www.mongodb.com/docs/drivers/motor/
    motor 文档：https://motor.readthedocs.io/en/stable/
    :param app:
    :param status:
    :return:
    """
    if status:
        client: AsyncIOMotorClient = AsyncIOMotorClient(
            MONGO_DB_URL,
            maxPoolSize=10,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000
        )
        app.state.mongo_client = client
        app.state.mongo = client[MONGO_DB_NAME]
        # 尝试连接并捕获可能的超时异常
        try:
            # 触发一次服务器通信来确认连接
            data = await client.server_info()
            print("MongoDB 连接成功", data)
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise ValueError(f"MongoDB 连接失败: {e}")
    else:
        print("MongoDB 连接关闭")
        app.state.mongo_client.close()



async def connect_clickhouse(app: FastAPI, status: bool):
    """
    异步连接或关闭ClickHouse数据库

    Args:
        app: FastAPI应用实例
        status: True为连接，False为关闭
    """
    if status:
        try:
            # 创建ClickHouse客户端
            client = clickhouse_driver.Client(
                host=CLICKHOUSE_HOST,
                port=CLICKHOUSE_PORT,
                database=CLICKHOUSE_DATABASE,
                user=CLICKHOUSE_USER,
                password=CLICKHOUSE_PASSWORD
            )

            # 将客户端存储到应用状态中
            app.state.clickhouse = client

            # 异步测试连接
            loop = asyncio.get_event_loop()
            server_info = await loop.run_in_executor(None, client.execute, "SELECT version()")

            print(f"CK 连接成功: {server_info}")
            logger.info(f"ClickHouse连接成功: {server_info}")

        except Exception as e:
            error_msg = f"CK 连接失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    else:
        # 关闭连接
        if hasattr(app.state, 'clickhouse'):
            try:
                # ClickHouse客户端没有close方法，只需清理引用
                delattr(app.state, 'clickhouse')
                print("CK 连接关闭")
                logger.info("ClickHouse连接已关闭")
            except Exception as e:
                logger.error(f"关闭CK连接时出错: {str(e)}")
        else:
            print("CK 连接未初始化")
            logger.warning("尝试关闭未初始化的ClickHouse连接")

async def multiprocessing_can_decrypt_event(app: FastAPI, status: bool):
    # 使用多进程隔离 can数据解密
    scheduler_process = multiprocessing.Process(target=start_scheduler_sync)
    scheduler_process.daemon = True  # 设置为守护进程
    scheduler_process.start()

async def multiprocessing_driver_event(app: FastAPI, status: bool):
    # 使用多进程隔离 驾驶员画像
    scheduler_process = multiprocessing.Process(target=start_scheduler_sync_driver)
    scheduler_process.daemon = True  # 设置为守护进程
    scheduler_process.start()

async def start_scheduler_process(target_func):
    """启动守护进程运行调度器"""
    process = multiprocessing.Process(target=target_func, daemon=False)
    process.start()
    scheduler_processes.append(process)
    return process


def start_scheduler_sync_weights():
    """权重同步调度器"""
    import time
    while True:
        print("执行权重同步任务...")
        time.sleep(300)  # 每5分钟执行一次


def start_scheduler_sync_week():
    """数据同步调度器"""
    import time
    while True:
        print("执行每周同步任务...")
        time.sleep(60)  # 每分钟执行一次


def start_scheduler_sync_day():

    start_scheduler_sync_driver()

def start_scheduler_process():
    # 创建调度器管理器
    manager = SchedulerManager()

    # 设置信号处理器
    manager.setup_signal_handlers()
    try:
        #驾驶员权重（一月一次）驾驶员分数（一周一次）
        manager.start_scheduler_process(start_scheduler_sync_driver)
        manager.start_scheduler_process(start_scheduler_sync_route)
        manager.start_scheduler_process(start_scheduler_sync_vehicle)
        manager.start_scheduler_process(start_scheduler_sync_company)
        print(f"已启动 {len(scheduler_processes)} 个调度器进程")
      # 主进程保持运行
        while manager.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n接收到键盘中断信号")
    finally:
        # 确保资源被清理
        manager.cleanup_resources()





# @File           : main.py
# @IDE            : PyCharm
# @desc           : 主程序入口

import multiprocessing
from urllib.request import Request

from fastapi import FastAPI
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from application import settings
from application import urls
from starlette.staticfiles import StaticFiles  # 依赖安装：pip install aiofiles
from core.docs import custom_api_docs
from core.exception import register_exception
import typer

from model.company.company_profile_scheduler import start_scheduler_sync_company
from model.driver.driver_hour_profile_scheduler import start_scheduler_sync_hour_driver
from model.driver.driver_profile_scheduler import start_scheduler_sync_driver
from model.driver.driver_week_profile_scheduler import start_scheduler_sync_week_driver
from model.route.route_profile_scheduler import start_scheduler_sync_route, start_scheduler_sync_black_route
from model.station.station_profile_scheduler import start_scheduler_sync_station
from model.vehicle.vehicle_profile_scheduler import start_scheduler_sync_vehicle
from core.event import lifespan, start_scheduler_sync_week
from scripts.create_app.main import CreateApp
from utils.logger import logger
from utils.tools import import_modules
from contextlib import asynccontextmanager
#
# shell_app = typer.Typer()
#
#
# def create_app():
#     """
#     启动项目
#
#     docs_url：配置交互文档的路由地址，如果禁用则为None，默认为 /docs
#     redoc_url： 配置 Redoc 文档的路由地址，如果禁用则为None，默认为 /redoc
#     openapi_url：配置接口文件json数据文件路由地址，如果禁用则为None，默认为/openapi.json
#     """
#     app = FastAPI(
#         title="BusAi",
#         description="公交驾驶员行车安全AI模型研究与应用项目",
#         version=settings.VERSION,
#         lifespan=lifespan,
#         docs_url=None,
#         redoc_url=None
#     )
#
#
#     import_modules(settings.MIDDLEWARES, "中间件", app=app)
#     # 全局异常捕捉处理
#     register_exception(app)
#     # 跨域解决
#     if settings.CORS_ORIGIN_ENABLE:
#         app.add_middleware(
#             CORSMiddleware,
#             allow_origins=settings.ALLOW_ORIGINS,
#             allow_credentials=settings.ALLOW_CREDENTIALS,
#             allow_methods=settings.ALLOW_METHODS,
#             allow_headers=settings.ALLOW_HEADERS
#         )
#     # 挂在静态目录
#     if settings.STATIC_ENABLE:
#         print(settings.STATIC_ROOT)
#         app.mount(settings.STATIC_URL, app=StaticFiles(directory=settings.STATIC_ROOT))
#     # 引入应用中的路由
#     for url in urls.urlpatterns:
#         app.include_router(url["ApiRouter"], prefix=url["prefix"], tags=url["tags"])
#         # app.include_router(health.router, tags=["Health"])
#         # app.include_router(ocr.router, tags=["OCR"])
#     # 配置接口文档静态资源
#     custom_api_docs(app)
#
#
#     return app
#
#
# def start_all_schedulers():
#     """集中管理所有调度器进程"""
#     # 定义所有需要启动的调度器目标函数
#     import os
#     print(f"[DEBUG] start_all_schedulers called in PID: {str(os.getpid())}")  # 检查这里是否打印了多次
#
#     targets = [
#         start_scheduler_sync_driver,
#         start_scheduler_sync_route,
#         start_scheduler_sync_station,
#         start_scheduler_sync_vehicle,
#         start_scheduler_sync_company,
#         start_scheduler_sync_black_route,
#         start_scheduler_sync_hour_driver
#         # start_scheduler_gen_report
#     ]
#
#     # targets = [
#     #     start_scheduler_sync_route,
#     #     start_scheduler_sync_company,
#     #     start_scheduler_sync_black_route
#     # ]
#
#     processes = []
#     for target_func in targets:
#         p = multiprocessing.Process(target=target_func)
#         # p.daemon = False  # 非守护进程，主进程退出时子进程继续运行（通常建议设为True以便随主进程退出，视业务需求而定）
#         p.daemon = True
#         p.start()
#         processes.append(p)
#         print(f"进程 {target_func} 已启动, PID: {p.pid}")
#
#     return processes
#
#
# @shell_app.command()
# def run(
#         host: str = typer.Option(default='0.0.0.0', help='监听主机IP，默认开放给本网络所有主机'),
#         port: int = typer.Option(default=9000, help='监听端口')
# ):
#
#
#     # 1. 启动所有调度器进程
#     scheduler_processes = start_all_schedulers()
#
#     uvicorn.run(app='main:create_app', host=host, port=port, workers=1,lifespan="on", factory=True,reload=False)
#
#
#
# @shell_app.command()
# def init_app(path: str):
#     """
#     自动创建初始化 APP 结构
#
#     命令例子：python main.py init-app vadmin/test
#
#     :param path: app 路径，根目录为apps，填写apps后面路径即可，例子：vadmin/auth
#     """
#     print(f"开始创建并初始化 {path} APP")
#     app = CreateApp(path)
#     app.run()
#
#
# if __name__ == '__main__':
#     shell_app()






shell_app = typer.Typer()

# 全局变量用于存储进程引用，以便在 shutdown 时清理
scheduler_processes = []


def start_all_schedulers():
    """启动所有调度器进程，并返回进程列表"""
    targets = [
        start_scheduler_sync_driver,
        start_scheduler_sync_route,
        start_scheduler_sync_station,
        start_scheduler_sync_vehicle,
        start_scheduler_sync_company,
        start_scheduler_sync_black_route,
        start_scheduler_sync_hour_driver,
        start_scheduler_sync_week_driver
    ]

    processes = []
    for target_func in targets:
        # 确保每个子进程独立初始化，避免共享状态问题
        p = multiprocessing.Process(target=target_func, daemon=True)
        p.start()
        processes.append(p)
        print(f"[INFO] 调度器进程已启动: {target_func.__name__}, PID: {p.pid}")

    return processes


def stop_all_schedulers(processes):
    """优雅停止所有调度器进程"""
    print("[INFO] 正在停止调度器进程...")
    for p in processes:
        if p.is_alive():
            p.terminate()  # 发送 SIGTERM
            p.join(timeout=5)  # 等待最多5秒
            if p.is_alive():
                p.kill()  # 如果还没停，强制杀死
                print(f"[WARN] 进程 {p.pid} 被强制杀死")
    print("[INFO] 所有调度器进程已停止")


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     FastAPI 生命周期管理：
#     1. 启动时开启调度器
#     2. 关闭时清理调度器
#     """
#     # Startup
#     global scheduler_processes
#     scheduler_processes = start_all_schedulers()
#     yield
#     # Shutdown
#     stop_all_schedulers(scheduler_processes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理：
    1. 启动时开启调度器
    2. 关闭时清理调度器
    """
    # --- Startup 阶段 ---
    global scheduler_processes
    try:
        logger.info("🚀 正在启动后台调度器进程...")
        scheduler_processes = start_all_schedulers()

        # 可选：简单验证进程是否成功创建并存活
        for p in scheduler_processes:
            if not p.is_alive():
                raise RuntimeError(f"进程 {p.name} (PID: {p.pid}) 启动后立即退出，请检查目标函数逻辑。")

        logger.info(f"✅ 所有调度器进程已启动，共 {len(scheduler_processes)} 个进程。")

    except Exception as e:
        # 记录严重错误
        logger.critical(f"❌ 调度器启动失败: {str(e)}", exc_info=True)

        # 决策点：
        # 选项 A: 阻止应用启动（推荐用于核心依赖）
        # 注意：在 lifespan 中抛出异常会导致 Uvicorn 退出
        raise SystemExit(1)


    yield

    # --- Shutdown 阶段 ---
    logger.info("🛑 应用关闭，正在清理调度器进程...")
    try:
        if scheduler_processes:
            stop_all_schedulers(scheduler_processes)
            logger.info("✅ 调度器进程清理完成。")
    except Exception as e:
        logger.error(f"⚠️ 清理调度器进程时发生错误: {str(e)}", exc_info=True)


def create_app():
    app = FastAPI(
        title="BusAi",
        description="公交驾驶员行车安全AI模型研究与应用项目",
        version=getattr(settings, 'VERSION', '1.0.0'),  # 增加容错
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None
    )

    # 中间件注册
    if hasattr(settings, 'MIDDLEWARES'):
        import_modules(settings.MIDDLEWARES, "中间件", app=app)

    register_exception(app)

    if getattr(settings, 'CORS_ORIGIN_ENABLE', False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=getattr(settings, 'ALLOW_ORIGINS', ["*"]),
            allow_credentials=getattr(settings, 'ALLOW_CREDENTIALS', True),
            allow_methods=getattr(settings, 'ALLOW_METHODS', ["*"]),
            allow_headers=getattr(settings, 'ALLOW_HEADERS', ["*"])
        )

    if getattr(settings, 'STATIC_ENABLE', False):
        print(getattr(settings, 'STATIC_ROOT', ''))
        app.mount(getattr(settings, 'STATIC_URL', '/static'), app=StaticFiles(directory=settings.STATIC_ROOT))

    # 路由注册
    if hasattr(urls, 'urlpatterns'):
        for url in urls.urlpatterns:
            app.include_router(url["ApiRouter"], prefix=url["prefix"], tags=url["tags"])

    custom_api_docs(app)
    return app


@shell_app.command()
def run(
        host: str = typer.Option(default='0.0.0.0', help='监听主机IP'),
        port: int = typer.Option(default=9000, help='监听端口')
):
    """
    启动服务。
    注意：调度器的启动/停止现在由 FastAPI 的 lifespan 自动管理，
    不需要在这里手动调用 start_all_schedulers。
    """
    # 使用 factory 模式启动，确保每次 reload 或启动时都创建新的 app 实例
    # 如果是生产环境，建议 workers > 1，但要注意多进程下调度器会重复启动。
    # 如果 workers > 1，上面的 lifespan 会在每个 worker 中执行，导致调度器重复启动。
    # 解决方案见下方的“重要提示”。

    uvicorn.run(
        "main:create_app",  # 确保这里的模块名正确，如果是当前文件，可能是 "__main__:create_app" 或具体文件名
        host=host,
        port=port,
        workers=1,  # 保持为1，因为调度器不适合在多worker模式下简单运行
        lifespan="on",
        factory=True,
        reload=False
    )

@shell_app.command()
def init_app(path: str):
    """
    自动创建初始化 APP 结构

    命令例子：python main.py init-app vadmin/test

    :param path: app 路径，根目录为apps，填写apps后面路径即可，例子：vadmin/auth
    """
    print(f"开始创建并初始化 {path} APP")
    app = CreateApp(path)
    app.run()

if __name__ == '__main__':
    shell_app()

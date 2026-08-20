# import os
# from loguru import logger
# from application.settings import BASE_DIR
#
# # 1. 移除默认控制台输出
# logger.remove()
#
# # 2. 确保日志目录存在
# log_path = os.path.join(BASE_DIR, 'logs')
# os.makedirs(log_path, exist_ok=True)
#
# # 3. 定义通用配置
# # 注意：路径中直接使用 {time:YYYY-MM-DD}，Loguru 会自动替换为当前时间
# # 当 rotation="00:00" 触发时，Loguru 会关闭当前文件，并根据新的时间生成新文件名
# common_config = {
#     "rotation": "00:00",       # 每天午夜轮转
#     "retention": "3 days",     # 保留3天
#     "enqueue": True,           # 异步写入，线程安全
#     "encoding": "UTF-8",       # 中文支持
#     "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
# }
#
# # 4. 添加 INFO 级别日志处理器
# logger.add(
#     os.path.join(log_path, "info_{time:YYYY-MM-DD}.log"),
#     level="INFO",
#     **common_config
# )
#
# # 5. 添加 ERROR 级别日志处理器
# logger.add(
#     os.path.join(log_path, "error_{time:YYYY-MM-DD}.log"),
#     level="ERROR",
#     **common_config
# )

import os
from loguru import logger
from application.settings import BASE_DIR

# 1. 移除默认控制台输出
logger.remove()

# 2. 确保日志目录存在
log_path = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_path, exist_ok=True)

# 3. 定义通用配置
common_config = {
    "rotation": "00:00",       # 每天午夜轮转
    "retention": "3 days",     # 保留3天
    "enqueue": True,           # 【关键】启用异步队列，解决多进程/多线程写入冲突
    "encoding": "UTF-8",       # 中文支持
    "catch": True,             # 【新增】捕获内部异常，防止日志系统崩溃导致主程序退出
    "backtrace": True,         # 【建议】记录异常回溯
    "diagnose": False,         # 【建议】生产环境关闭诊断模式，避免敏感信息泄露和性能开销
    "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
}

# 4. 添加 INFO 级别日志处理器
# 注意：compression="zip" 可以节省磁盘空间，但会增加CPU开销，可视情况开启
logger.add(
    os.path.join(log_path, "info_{time:YYYY-MM-DD}.log"),
    level="INFO",
    compression="zip",         # 【新增】自动压缩旧日志，减少磁盘占用
    **common_config
)

# 5. 添加 ERROR 级别日志处理器
logger.add(
    os.path.join(log_path, "error_{time:YYYY-MM-DD}.log"),
    level="ERROR",
    compression="zip",         # 【新增】自动压缩旧日志
    **common_config
)

# 【可选】如果需要在控制台也看到日志（调试用），可以添加以下配置
# logger.add(sys.stderr, level="INFO", colorize=True)

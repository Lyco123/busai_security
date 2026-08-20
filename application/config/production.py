# @File           : production.py
# @IDE            : PyCharm
# @desc           : 数据库开发配置文件

# ClickHouse数据库连接配置
CLICKHOUSE_DB_ENABLE = True
CLICKHOUSE_NAME = "busai"
CLICKHOUSE_PORT = "9000"
# CLICKHOUSE_HOST = "117.72.212.82"
# CLICKHOUSE_USER = "default"
# CLICKHOUSE_PASSWORD = "Zhongda@84"
# CLICKHOUSE_DATABASE = "ai_security"

CLICKHOUSE_HOST = "10.181.90.128"
CLICKHOUSE_USER = "ai_u"
CLICKHOUSE_PASSWORD = "7U8rzi8P4LUhJ7@l"
CLICKHOUSE_DATABASE = "ai_security"



REDIS_DB_ENABLE = False
REDIS_DB_URL = "redis://:jinqi2016@127.0.0.1:6379/1"

"""
MongoDB 数据库配置
格式：mongodb://用户名:密码@地址:端口/?authSource=数据库名称
"""
MONGO_DB_ENABLE = False
MONGO_DB_NAME = "kinit"
MONGO_DB_URL = f"mongodb://kinit:jinqi2016@127.0.0.1:27017/?authSource={MONGO_DB_NAME}"


"""
获取IP地址归属地
文档：https://user.ip138.com/ip/doc
"""
IP_PARSE_ENABLE = False
IP_PARSE_TOKEN = "IP_PARSE_TOKEN"

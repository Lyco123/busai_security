import clickhouse_driver
from typing import Optional
from application.settings import CLICKHOUSE_HOST,CLICKHOUSE_PORT,CLICKHOUSE_USER,CLICKHOUSE_PASSWORD,CLICKHOUSE_DATABASE,CLICKHOUSE_NAME

class ClickHouseClient:
    """ClickHouse数据库连接管理器"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self._client: Optional[clickhouse_driver.Client] = None
        # self.settings = {
        #     'max_block_size': 100000,
        #     'max_threads': 2,
        #     'max_memory_usage': 5000000000,  # 5GB内存限制
        #     'max_bytes_before_external_group_by': 1000000000,
        #     'max_bytes_before_external_sort': 1000000000,
        # }

    async def connect(self) -> clickhouse_driver.Client:
        """建立数据库连接"""
        if self._client is None:
            self._client = clickhouse_driver.Client(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
        return self._client

    async def close(self):
        """关闭数据库连接"""
        if self._client is not None:
            # clickhouse-driver的Client没有异步close方法，直接设为None
            # 如果需要执行清理操作，可以在这里添加
            self._client = None

    async def __aenter__(self) -> clickhouse_driver.Client:
        """异步上下文管理器入口"""
        return await self.connect()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


async def connect_to_clickhouse() -> ClickHouseClient:
    """
    建立ClickHouse数据库连接
    """
    client = ClickHouseClient(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DATABASE,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    await client.connect()
    return client

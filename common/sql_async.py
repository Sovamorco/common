from time import time

from aiomysql import Pool, create_pool
from aiomysql.cursors import DictCursor

from .sql import SQLClient


class AsyncSQLClient(SQLClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool: Pool = None

    async def init_pool(self):
        self.pool = await create_pool(**self.config)

    async def refresh(self):
        if not self.time_to_refresh:
            if self.pool is None:
                await self.init_pool()
            return
        lease_started = time()
        credentials, lease_duration = await self.vault_client.get_database_connection_profile(self.role_name)
        self.config['user'] = credentials['username']
        self.config['password'] = credentials['password']
        self.expires_at = lease_started + lease_duration
        old_pool = self.pool
        await self.init_pool()
        if old_pool is not None:
            old_pool.close()

    async def sql_req(self, query, *params, fetch_one=False, fetch_all=False, last_row_id=False):
        await self.refresh()
        async with self.pool.acquire() as conn:
            async with conn.cursor(DictCursor) as cur:
                await cur.execute(query, params)
                if fetch_one:
                    return await cur.fetchone()
                elif fetch_all:
                    return await cur.fetchall()
                elif last_row_id:
                    return cur.lastrowid

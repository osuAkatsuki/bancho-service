from __future__ import annotations

from typing import cast
from typing import Optional

import aiomysql

import settings


class DBPool:
    def __init__(self) -> None:
        self._pool: Optional[aiomysql.Pool] = None

    async def start(self):
        self._pool = cast(
            aiomysql.Pool,
            await aiomysql.create_pool(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASS,
                db=settings.DB_NAME,
                maxsize=settings.DB_WORKERS,
                autocommit=True,
            ),
        )

    async def stop(self):
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()

    async def fetchAll(self, *args, **kwargs):
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                return await cur.fetchall()

    async def fetch(self, *args, **kwargs):
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                return await cur.fetchone()

    async def execute(self, *args, **kwargs):
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                await conn.commit()
                return cur.lastrowid

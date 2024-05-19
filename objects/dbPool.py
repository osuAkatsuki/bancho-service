from __future__ import annotations

from typing import Any
from typing import cast

import aiomysql

import settings


class DBPool:
    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None

    async def start(self) -> None:
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

    async def stop(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()

    async def fetchAll(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                return [dict(rec) for rec in await cur.fetchall()]

    async def fetch(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                rec = await cur.fetchone()
                return dict(rec) if rec is not None else None

    async def execute(self, *args: Any, **kwargs: Any) -> int:
        assert self._pool is not None, "DBPool not started"

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(*args, **kwargs)
                await conn.commit()
                # TODO: can this return None?
                return int(cur.lastrowid)

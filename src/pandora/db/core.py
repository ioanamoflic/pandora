import asyncpg
from typing import Optional


class PandoraDB:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
        )

    async def close(self):
        if self.pool:
            await self.pool.close()

    def acquire(self):
        """
        Convenience wrapper to avoid repeating `pool.acquire()`
        """
        return self.pool.acquire()
    
import json

import asyncpg
from typing import Optional


class PandoraDB:
    def __init__(self, config: str | dict = None, min_size: int = 1, max_size: int = 32):
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None

        if config is None:
            self.config = {}
        elif isinstance(config, str):
            self.config = self._config_from_json(config)
        else:
            self.config = config

    async def connect(self):
        """
        If anything is missing in configs or the config is not specified, Postgres should use defaults.
        """
        self.pool = await asyncpg.create_pool(
            host=self.config.get("host") or "localhost",
            port=self.config.get("port") or 5432,
            user=self.config.get("user") or None,
            password=self.config.get("password") or None,
            database=self.config.get("database") or "postgres",
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

    @staticmethod
    def _config_from_json(config_file_path):
        with open(config_file_path, "r") as f:
            return json.load(f)


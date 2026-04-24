import asyncpg
from typing import Optional


class PandoraDB:
    def __init__(self, config: str | dict, dsn: str = None, min_size: int = 1, max_size: int = 10):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None

        if not dsn and isinstance(config, str):
            self.dsn = self._dsn_from_json(config)
        elif not dsn and isinstance(config, dict):
            self.dsn = self._dsn_from_dict(config)

        assert self.dsn is not None

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

    def _dsn_from_json(self, config_file_path):
        import json

        with open(config_file_path, "r") as f:
            data = json.load(f)

        return self._dsn_from_dict(data)

    @staticmethod
    def _dsn_from_dict(data):
        return (
            f"postgresql://{data['user']}:{data['password']}"
            f"@{data.get('host', 'localhost')}:{data.get('port', 5432)}"
            f"/{data.get('database', 'postgres')}"
        )

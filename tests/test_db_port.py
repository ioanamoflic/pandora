"""Check database port selection without connecting to PostgreSQL."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


fake_asyncpg = types.ModuleType("asyncpg")
fake_asyncpg.Pool = object
spec = importlib.util.spec_from_file_location(
    "pandora_db_core_port_test",
    Path(__file__).resolve().parents[1] / "src/pandora/db/core.py",
)
core = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"asyncpg": fake_asyncpg}):
    spec.loader.exec_module(core)


class DatabasePortTests(unittest.TestCase):
    def assert_port(self, config, environment, expected):
        create_pool = AsyncMock(return_value=object())
        with patch.dict(os.environ, environment, clear=True), patch.object(
            core.asyncpg, "create_pool", create_pool, create=True
        ):
            asyncio.run(core.PandoraDB(config).connect())
        actual = create_pool.call_args.kwargs["port"]
        self.assertEqual(actual, expected)
        self.assertIsInstance(actual, int)

    def test_default_port_without_config_or_environment(self):
        self.assert_port(None, {}, 5432)

    def test_launcher_port_without_config(self):
        self.assert_port(None, {"PGPORT": "15432"}, 15432)

    def test_explicit_config_takes_priority(self):
        self.assert_port({"port": 25432}, {"PGPORT": "15432"}, 25432)

    def test_string_config_is_converted_to_integer(self):
        self.assert_port({"port": "25432"}, {"PGPORT": "15432"}, 25432)

    def test_empty_config_port_uses_launcher_port(self):
        for value in [None, "", 0]:
            with self.subTest(value=value):
                self.assert_port({"port": value}, {"PGPORT": "15432"}, 15432)

    def test_empty_environment_port_uses_default(self):
        self.assert_port({}, {"PGPORT": ""}, 5432)


if __name__ == "__main__":
    unittest.main()

"""CLI/distribution checks without loading the quantum simulation stack."""
import argparse
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "pandora_main_cli_test", Path(__file__).resolve().parents[1] / "main.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class RsaDistributionTests(unittest.TestCase):
    def test_single_node_needs_no_rank(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.rsa_node_id(1), 0)

    def test_multinode_requires_launcher(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "launcher"):
                cli.rsa_node_id(3)

    def test_every_node_gets_a_distinct_valid_chunk(self):
        for rank in range(3):
            with self.subTest(rank=rank), patch.dict(
                os.environ,
                {"PANDORA_NODE_ID": str(rank), "PANDORA_NODE_COUNT": "3"},
                clear=True,
            ):
                self.assertEqual(cli.rsa_node_id(3), rank)

    def test_rejects_inconsistent_or_out_of_range_assignments(self):
        for rank, count in [("0", "2"), ("3", "3"), ("-1", "3"), ("x", "3")]:
            with self.subTest(rank=rank, count=count), patch.dict(
                os.environ,
                {"PANDORA_NODE_ID": rank, "PANDORA_NODE_COUNT": count},
                clear=True,
            ):
                with self.assertRaises(ValueError):
                    cli.rsa_node_id(3)

    def test_rejects_incomplete_assignment(self):
        with patch.dict(os.environ, {"PANDORA_NODE_ID": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "both"):
                cli.rsa_node_id(1)

    def test_positive_resource_counts(self):
        self.assertEqual(cli.positive_int("4"), 4)
        for value in ["0", "-2"]:
            with self.assertRaises(argparse.ArgumentTypeError):
                cli.positive_int(value)

    def test_rsa_passes_world_size_and_rank_to_decomposition(self):
        calls = []

        class Database:
            def __init__(self, config):
                pass

            async def connect(self):
                calls.append("connect")

            async def close(self):
                calls.append("close")

        class Service:
            def __init__(self, **kwargs):
                pass

            async def build_pandora(self):
                calls.append("build")

            def parallel_decompose(self, **kwargs):
                calls.append(kwargs)

        modules = {}
        for name, attrs in {
            "pandora.db.core": {"PandoraDB": Database},
            "pandora.db.repository": {"GateRepository": lambda db: object()},
            "pandora.db.service": {"PandoraService": Service},
        }.items():
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            modules[name] = module
        with patch.dict(sys.modules, modules), patch.dict(
            os.environ,
            {"PANDORA_NODE_ID": "2", "PANDORA_NODE_COUNT": "3"},
            clear=True,
        ):
            asyncio.run(cli.run_rsa(None, 64, 4, 3))
        self.assertEqual(calls[:3], ["connect", "build", "close"])
        self.assertEqual(calls[3]["container_id"], 2)
        self.assertEqual(calls[3]["n_containers"], 3)
        self.assertEqual(calls[3]["nprocs"], 4)


if __name__ == "__main__":
    unittest.main()

"""Exercise decomposition coordination without importing optional quantum packages."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def source_definition(relative_path, name, *, member=None, namespace=None):
    tree = ast.parse((ROOT / relative_path).read_text())
    node = next(item for item in tree.body if getattr(item, 'name', None) == name)
    if member:
        node = next(item for item in node.body if getattr(item, 'name', None) == member)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {} if namespace is None else namespace
    exec(compile(module, relative_path, 'exec'), namespace)
    return namespace[member or name]


Builder = source_definition('src/pandora/translation/circuit_to_dag.py', 'PandoraWindowedBuilder')


class ParallelExecutionTests(unittest.TestCase):
    def test_builders_allocate_disjoint_gate_ids_for_every_worker(self):
        for workers in (1, 2, 12):
            allocated = []
            for worker in range(workers):
                builder = Builder(label=str(worker), id_start=worker, id_step=workers)
                allocated.extend(builder._new_id() for _ in range(25))
            self.assertEqual(sorted(allocated), list(range(workers * 25)))

    def test_default_builder_ids_remain_sequential(self):
        builder = Builder()
        self.assertEqual([builder._new_id() for _ in range(4)], [0, 1, 2, 3])

    def test_invalid_id_ranges_are_rejected(self):
        for settings in ({'id_start': -1}, {'id_step': 0}):
            with self.assertRaises(ValueError):
                Builder(**settings)

    def test_worker_partitions_cover_every_operation_once(self):
        for operation_count, nodes, workers in ((23, 3, 4), (2, 4, 3)):
            seen = []
            builder_settings = []

            class Database:
                def __init__(self, config):
                    pass
                async def connect(self):
                    pass
                async def close(self):
                    pass

            class WorkerBuilder:
                def __init__(self, **kwargs):
                    builder_settings.append(kwargs)
                def consume(self, batch):
                    seen.extend(batch)
                    return []
                def finalize(self):
                    return []

            worker_main = source_definition(
                'src/pandora/multithreading/parallel_decompose.py', '_worker_main',
                namespace={
                    'get_RSA': lambda **kwargs: object(),
                    'circuit_decompose_multi': lambda *args, **kwargs: [list(range(operation_count))],
                    'PandoraDB': Database,
                    'GateRepository': lambda db: object(),
                    'PandoraWindowedBuilder': WorkerBuilder,
                    'get_RSA_batch': lambda circuit, **kwargs: [([circuit], 0)],
                },
            )
            for rank in range(nodes):
                for worker in range(workers):
                    asyncio.run(worker_main(worker, workers, rank, nodes, 100, 64))
            self.assertEqual(sorted(seen), list(range(operation_count)))
            self.assertEqual([s['id_start'] for s in builder_settings], list(range(workers)) * nodes)
            self.assertTrue(all(s['id_step'] == workers for s in builder_settings))

    def test_worker_failures_reach_parent(self):
        for exitcodes in ([0, 0], [0, 1], [-9, 0]):
            processes = []

            class FakeProcess:
                def __init__(self, **kwargs):
                    self.exitcode = exitcodes[len(processes)]
                    self.joined = False
                    processes.append(self)
                def start(self):
                    pass
                def join(self):
                    self.joined = True

            decompose = source_definition(
                'src/pandora/db/service.py', 'PandoraService', member='parallel_decompose',
                namespace={'Process': FakeProcess, 'worker_entry': object()},
            )
            service = SimpleNamespace(window_size=100)
            if any(exitcodes):
                with self.assertRaisesRegex(RuntimeError, 'RSA decomposition failed'):
                    decompose(service, nprocs=2)
            else:
                decompose(service, nprocs=2)
            self.assertTrue(all(p.joined for p in processes))


if __name__ == '__main__':
    unittest.main()

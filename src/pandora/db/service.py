import time
from multiprocessing import Process
from pathlib import Path
from typing import Any, List, Optional

from pandora.db.core import PandoraDB
from pandora.db.repository import (
    GateRepository,
    GateLayerRepository
)
from pandora.multithreading.parallel_decompose import worker_entry
from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pandora.translation.translator import GLOBAL_IN_ID
from pandora.widgetization.union_find import UnionFindWidgetizer

BASE_DIR = Path(__file__).resolve().parent  # pandora/db/


class PandoraService:
    def __init__(
            self,
            db: PandoraDB,
            repo: GateRepository,
            repo_layered: GateLayerRepository = None,
            decomposition_window_size: int = 1_000_000,
    ):
        self.db = db
        self.repo = repo
        self.repo_layered = repo_layered
        self.window_size = decomposition_window_size

    async def build_pandora(self):
        await self._drop_tables()
        await self._build_schema()
        await self._refresh_procedures()
        await self._reset_sequence(table_names=['linked_circuit',
                                                'layered_lscom'])

    async def build_circuit(self, circuit: Any):
        await self.build_pandora()

        builder = PandoraWindowedBuilder(window_size=self.window_size)

        start = time.time()

        for batch in builder.consume(circuit):
            await self.repo.insert_copy(batch)

        final = builder.finalize()
        if final:
            await self.repo.insert_copy(final)

        print(f"Decomposition took {time.time() - start:.2f}s")

    def parallel_decompose(
            self,
            nprocs: int,
            container_id: int = 0,
            n_containers: int = 1,
            config_file: str = None,
            window_size: Optional[int] = None,
            N: Optional[int] = None,
    ) -> None:
        """
        Launch parallel decomposition workers.

        Each worker:
        - builds its assigned shard of the circuit
        - converts batches to Pandora gates
        - inserts batches into the database via async repository calls
        """
        if nprocs < 1:
            raise ValueError("nprocs must be >= 1")
        if n_containers < 1:
            raise ValueError("n_containers must be >= 1")
        if not (0 <= container_id < n_containers):
            raise ValueError("container_id must satisfy 0 <= container_id < n_containers")

        effective_window_size = window_size or self.window_size

        processes: list[Process] = []

        for worker_id in range(nprocs):
            p = Process(
                target=worker_entry,
                args=(
                    worker_id,
                    nprocs,
                    container_id,
                    n_containers,
                    effective_window_size,
                    N,
                    config_file,
                ),
            )
            processes.append(p)

        for p in processes:
            p.start()

        for p in processes:
            p.join()

    async def load_circuit(self, circuit_type, label: int | None = None):
        if label is None:
            gates = await self.repo.fetch_all()
        else:
            gates = await self.repo.fetch_by_label(label)

        from pandora.translation.dag_to_circuit import pandora_to_circuit
        return pandora_to_circuit(gates, circuit_type)

    async def load_circuit_into_layered(self):
        gates = await self.repo.fetch_all()  # will have to stream these in batches later

        from pandora.translation.dag_to_circuit import pandora_to_circuit
        layered_gates = pandora_to_circuit(gates, "lscom")

        await self.repo_layered.insert_copy(layered_gates)

    async def load_circuit_from_layered(self):
        return await self.repo_layered.fetch_all()  # will have to stream these later

    async def get_edge_list(self):
        async with self.db.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM edge_list")

    async def get_gates(self, ids):
        return await self.repo.fetch_by_ids(ids)

    async def get_batched_edge_list(self, batch_size):
        async for batch in self.repo.stream_edge_batches(batch_size):
            yield batch

    async def widgetize(
            self,
            max_t: int,
            max_d: int,
            batch_size: int,
            add_gin_per_widget: bool
    ):
        i = 0

        async for edges in self.get_batched_edge_list(batch_size):
            if i != 0 and add_gin_per_widget:
                edges = self._add_inputs(edges)

            node_ids = {n for edge in edges for n in edge}

            gates = await self.get_gates(list(node_ids))
            gate_map = {g.id: g for g in gates}

            uf = UnionFindWidgetizer(edges, gates, max_t, max_d)

            for u, v in edges:
                uf.union(u, v)

            widgets = {}
            for node_id, parent in uf.parent.items():
                root = parent.root.id
                widgets.setdefault(root, []).append(gate_map[node_id])

            for widget in widgets.values():
                yield widget

            i += 1

    async def _drop_tables(self):
        tables = [
            'linked_circuit',
            'batched_circuit',
            'linked_circuit_test',
            'stop_condition',
            'edge_list',
            'mem_cx',
            'rewrite_count',
            'max_missed_rounds',
            'benchmark_results',
            'optimization_results',
            'gate_types',
            'layered_lscom'
        ]
        async with self.db.pool.acquire() as conn:
            for t in tables:
                await conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE")

    async def _build_schema(self):
        path = "generic_procedures/_sql_generate_table.sql"
        full_path = BASE_DIR / path
        sql = full_path.read_text()
        async with self.db.pool.acquire() as conn:
            await conn.execute(sql)

    async def _refresh_procedures(self):
        procedures: List[str] = [
            # equivalence benchmark
            'generic_procedures/cancel_two_qubit_equiv.sql',

            # sequential
            'generic_procedures/cancel_single_qubit.sql',
            'generic_procedures/cancel_two_qubit.sql',
            'generic_procedures/commute_single_control_left.sql',
            'generic_procedures/replace_two_sq_with_one.sql',
            'generic_procedures/toffoli_decomposition.sql',
            'generic_procedures/cx_to_hhcxhh.sql',
            'generic_procedures/hhcxhh_to_cx.sql',

            # worker procedures
            'generic_procedures/generate_edge_list.sql',

            # benchmarking only
            'generic_procedures/hhcxhh_to_cx_seq.sql',
            'generic_procedures/_generate_optimisation_stats.sql',
        ]
        async with self.db.pool.acquire() as conn:
            for path in procedures:
                full_path = BASE_DIR / path
                sql = full_path.read_text()
                await conn.execute(sql)

    async def _reset_sequence(
            self,
            table_names: List[str],
            value: int = int(1e6),
    ):
        for table_name in table_names:
            query = f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH {value}"

            async with self.db.pool.acquire() as conn:
                await conn.execute(query)

    @staticmethod
    def _add_inputs(edge_records):
        edges_to_append: list[tuple[int, int]] = []
        targets = [edge_record[1] for edge_record in edge_records]
        for (s, t) in edge_records:
            if s not in targets:
                edges_to_append.append((GLOBAL_IN_ID, s))
        return edges_to_append + edge_records

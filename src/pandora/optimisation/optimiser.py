import asyncio
import csv
from pathlib import Path

from pandora.db.core import PandoraDB
from pandora.translation.translator import PandoraGateTranslator


class PandoraOptimiser:
    """
    Async optimizer for stored procedure rewrites.
    """

    LARGE_RUN_NR = int(1e9)
    RESET_ID = int(5e6)
    LOG_SLEEP_FOR = 1

    def __init__(
        self,
        db: PandoraDB,
        timeout: int = 100,
        pass_count: int = 10,
        logger_id: int | None = None,
        max_concurrency: int | None = None,
    ):
        self.db = db
        self.timeout = timeout
        self.pass_count = pass_count
        self.logger_id = logger_id
        self.max_concurrency = max_concurrency or 8

        self._thread_proc: list[str] = []

    async def _execute(self, query: str) -> None:
        async with self.db.pool.acquire() as conn:
            await conn.execute(query)

    async def _execute_many(self, queries: list[str]) -> None:
        sem = asyncio.Semaphore(self.max_concurrency)

        async def _run_one(query: str):
            async with sem:
                async with self.db.pool.acquire() as conn:
                    await conn.execute(query)

        await asyncio.gather(*(_run_one(q) for q in queries))

    def _call_thread_proc(self, thread_proc: str) -> None:
        self._thread_proc.append(thread_proc)

    async def _reset_table_id(self) -> None:
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence($1, 'id'),
                    $2,
                    false
                )
                """,
                "linked_circuit",
                self.RESET_ID,
            )

    async def start(self) -> None:
        """
        Execute all queued stored procedures concurrently.
        """
        assert len(self._thread_proc) > 0

        await self._reset_table_id()
        await self._execute_many(self._thread_proc)
        self.clear()

    def clear(self) -> None:
        self._thread_proc.clear()

    def add_stopper(self) -> None:
        stopper = f"call stopper({self.timeout})"
        self._call_thread_proc(stopper)

    def log(self) -> None:
        logger_proc = (
            f"call generate_optimisation_stats("
            f"{self.LOG_SLEEP_FOR}, {self.logger_id}, {self.timeout})"
        )
        self._call_thread_proc(logger_proc)

    async def generate_csv(self, logger_id: int, out_path: str | None = None) -> Path:
        """
        Export optimization_results for a given logger_id to CSV.
        """
        out_file = Path(out_path or f"adder_{logger_id}.csv")

        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select *
                from optimization_results
                where logger_id = $1
                order by id
                """,
                logger_id,
            )

        with out_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "logger_id",
                    "total_count",
                    "t_count",
                    "s_count",
                    "h_count",
                    "cx_count",
                    "x_count",
                ]
            )
            for row in rows:
                writer.writerow(row)

        return out_file

    def cancel_single_qubit_gates(
        self,
        gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator],
        gate_params: tuple[float, float] = (1.0, 1.0),
        dedicated_nproc: int | None = None,
    ) -> None:
        type_left, type_right = gate_types
        param_left, param_right = gate_params

        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call cancel_single_qubit("
                f"{type_left.value}, {type_right.value}, "
                f"{param_left}, {param_right}, "
                f"{self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def cancel_two_qubit_gates(
        self,
        gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator],
        gate_param: float = 1.0,
        dedicated_nproc: int | None = None,
    ) -> None:
        type_left, type_right = gate_types

        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call cancel_two_qubit("
                f"{type_left.value}, {type_right.value}, "
                f"{gate_param}, {gate_param}, "
                f"{self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def cancel_two_qubit_gates_equiv(
        self,
        gate_types: tuple[PandoraGateTranslator, PandoraGateTranslator],
        dedicated_nproc: int | None = None,
        num_qubits: int | None = None,
    ) -> None:
        type_left, type_right = gate_types

        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call cancel_two_qubit_equiv("
                f"{type_left.value}, "
                f"{type_right.value}, "
                f"{num_qubits}, "
                f"{self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def hhcxhh_to_cx(self, dedicated_nproc: int | None = None) -> None:
        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call linked_hhcxhh_to_cx({self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def cx_to_hhcxhh(self, dedicated_nproc: int | None = None) -> None:
        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call linked_cx_to_hhcxhh({self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def fuse_single_qubit_gates(
        self,
        gate_types: tuple[
            PandoraGateTranslator,
            PandoraGateTranslator,
            PandoraGateTranslator,
        ],
        gate_params: tuple[float, float, float] = (1.0, 1.0, 1.0),
        dedicated_nproc: int | None = None,
    ) -> None:
        type_left, type_right, type_result = gate_types
        param_left, param_right, param_result = gate_params

        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call fuse_single_qubit("
                f"{type_left.value}, {type_right.value}, {type_result.value}, "
                f"{param_left}, {param_right}, {param_result}, "
                f"{self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

    def commute_rotation_with_control_left(
        self,
        gate_type: PandoraGateTranslator,
        gate_param: float = 1.0,
        dedicated_nproc: int | None = None,
    ) -> None:
        for _ in range(dedicated_nproc or 0):
            stored_procedure = (
                f"call commute_single_control_left("
                f"{gate_type.value}, {gate_param}, "
                f"{self.pass_count}, {self.timeout})"
            )
            self._call_thread_proc(stored_procedure)

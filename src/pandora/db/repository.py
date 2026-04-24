from typing import List, AsyncIterator

from pandora.db.core import PandoraDB
from pandora.translation.gates import PandoraGate


class GateRepository:
    def __init__(self, db: PandoraDB, table: str = "linked_circuit"):
        self.db = db
        self.table = table

        self.columns = [
            "id", "prev_q1", "prev_q2", "prev_q3",
            "type", "param", "global_shift", "switch",
            "next_q1", "next_q2", "next_q3",
            "visited", "label", "cl_ctrl", "meas_key"
        ]

    async def insert_copy(self, gates: List[PandoraGate]):
        if not gates:
            return

        records = [g.to_tuple() for g in gates]

        async with self.db.pool.acquire() as conn:
            await conn.copy_records_to_table(
                self.table,
                records=records,
                columns=self.columns,
            )

    async def fetch_all(self) -> List[PandoraGate]:
        query = f"SELECT * FROM {self.table}"

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query)

        return [PandoraGate.from_db_row(row) for row in rows]

    async def fetch_by_label(self, label: int) -> List[PandoraGate]:
        query = f"SELECT * FROM {self.table} WHERE label = $1"

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, label)

        return [PandoraGate.from_db_row(row) for row in rows]

    async def fetch_by_ids(self, ids: list[int]) -> List[PandoraGate]:
        # TODO add GIN/GOUT
        if not ids:
            return []

        query = f"SELECT * FROM {self.table} WHERE id = ANY($1)"

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, ids)

        return [PandoraGate.from_db_row(row) for row in rows]

    async def stream_edge_batches(self, batch_size: int):
        query = "SELECT * FROM edge_list ORDER BY source, target"

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                cursor = await conn.cursor(query)

                batch = []
                async for row in cursor:
                    batch.append(row)

                    if len(batch) >= batch_size:
                        yield batch
                        batch = []

                if batch:
                    yield batch

    async def stream(self, batch_size: int = 1000) -> AsyncIterator[List[PandoraGate]]:
        query = f"SELECT * FROM {self.table}"

        async with self.db.acquire() as conn:
            async with conn.transaction():
                cursor = await conn.cursor(query)

                batch = []
                async for row in cursor:
                    batch.append(PandoraGate.from_db_row(row))

                    if len(batch) >= batch_size:
                        yield batch
                        batch = []

                if batch:
                    yield batch

    async def delete_batched_table(self, table_name: str):
        query = f"DROP TABLE IF EXISTS {table_name}"

        async with self.db.pool.acquire() as conn:
            await conn.execute(query)

    async def create_batched_table(
            self,
            node_id: int,
            proc_id: int,
    ):
        table_name = f"batched_circuit_{node_id}_{proc_id}"

        await self.delete_batched_table(table_name)

        query = f"""
        CREATE TABLE {table_name} (
            id bigint,
            prev_q1 bigint,
            prev_q2 bigint,
            prev_q3 bigint,
            type smallint,
            param float4,
            global_shift float4,
            switch boolean,
            next_q1 bigint,
            next_q2 bigint,
            next_q3 bigint,
            visited int default -1,
            label serial,
            cl_ctrl boolean,
            meas_key smallint
        );
        """

        async with self.db.pool.acquire() as conn:
            await conn.execute(query)

        self.table = table_name

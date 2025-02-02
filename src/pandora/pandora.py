import time
import datetime

import cirq
import psycopg2

from pandora.pyliqtr_to_pandora_util import make_transverse_ising_circuit, make_fh_circuit, make_mg_coating_walk_op, \
    make_cyclic_o3_circuit, make_hc_circuit
from pandora.qualtran_to_pandora_util import *
from pandora.benchmarking.benchmark_adders import get_maslov_adder

from pandora.connection_util import *
from pandora.widgetization.union_find import UnionFindWidgetizer


class PandoraConfig:
    def __init__(
        self,
        database = "postgres",
        user = None,
        host = "localhost",
        port = 5432,
        password = "1234"
    ):
        self.database = database
        self.user = user
        self.host = host
        self.port = port
        self.password = password


    def update_from_file(self, path):
        import json
        with open(path, "r") as file:
            data = json.load(file)

            self.database = data["database"]
            self.user = data["user"]
            self.host = data["host"]
            self.port = int(data["port"])
            self.password = data["password"]
        CRED = '\033[91m'
        CEND = '\033[0m'
        print(f"{CRED}Loaded Pandora config from file: {path}", self.__dict__, f"{CEND}")


class Pandora:

    def __init__(self, pandora_config=PandoraConfig(), max_time=3600, decomposition_window_size=1000000):
        self.pandora_config = pandora_config

        # Connection should be None if failed
        self.connection = None
        self.connection = self.get_connection()
        self.stop_after = max_time
        self.decomposition_window_size = decomposition_window_size

    def __del__(self):
        if self.connection is not None:
            self.connection.close()

    def get_connection(self):
        """
        Creates and returns a database connection object.
        """
        connection = psycopg2.connect(
            database=self.pandora_config.database,
            user=self.pandora_config.user,
            host=self.pandora_config.host,
            port=self.pandora_config.port,
            password=self.pandora_config.password)

        connection.set_session(autocommit=True)

        if connection:
            print("Connection to the PostgreSQL established successfully.")
        else:
            print("Connection to the PostgreSQL encountered and error.")

        return connection

    def build_pandora(self):
        """
        Creates the Pandora database table from scratch and updates all stored procedures.
        """
        drop_and_replace_tables(self.connection,
                                clean=True,
                                verbose=True)
        refresh_all_stored_procedures(self.connection,
                                      verbose=True)

    def build_dedicated_table(self, table_name: str):
        """
        Creates the Pandora database table from scratch and updates all stored procedures.
        """
        create_named_table(connection=self.connection,
                           table_name=table_name)

    def build_edge_list(self) -> None:
        self.connection.cursor().execute("call generate_edge_list()")

    def get_edge_list(self) -> list[tuple[int, int]]:
        edges = get_edge_list(connection=self.connection)
        return edges

    def get_batched_edge_list(self, batch_size) -> Iterator[list[tuple[int, int]]]:
        return get_edge_list_in_batches(connection=self.connection,
                                        batch_size=batch_size)

    def get_pandora_gates_by_id(self, ids: list[int]) -> list[PandoraGate]:
        """
            Returns the Pandora gates with id in ids.
        """
        return get_gates_by_id_fast(connection=self.connection, ids=ids)

    def decompose_toffolis(self):
        """
        Decomposes all existing Toffoli gates in the Pandora into Clifford+T.
        """
        self.connection.cursor().execute("call linked_toffoli_decomp()")

    def build_qualtran_adder(self, bitsize):
        """
        Inserts a Qualtran adder bloq of bitsize=bits decomposed into
        Clifford+T into a fresh Pandora table instance.
        """
        CRED = '\033[91m'
        CEND = '\033[0m'

        self.build_pandora()
        adder_batches = get_adder(n_bits=bitsize,
                                  window_size=1000000)

        for i, (batch, _) in enumerate(adder_batches):
            insert_single_batch(connection=self.connection,
                                batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

    def build_example(self, repeat=100):
        self.build_pandora()
        q1, q2, q3, q4 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2'), cirq.NamedQubit('q3'), cirq.NamedQubit('q4')
        initial_circuit = cirq.Circuit([cirq.CX(q1, q2),
                                        cirq.CX(q2, q3),
                                        cirq.CX(q3, q4),
                                        cirq.CX(q2, q3),
                                        cirq.CX(q1, q2)])
        big_circuit = initial_circuit * repeat
        pandora_gates, _ = cirq_to_pandora(cirq_circuit=big_circuit,
                                           last_id=0,
                                           add_margins=True,
                                           label='t')
        insert_in_batches(pandora_gates=pandora_gates,
                          connection=self.connection,
                          table_name='linked_circuit')

    def build_qualtran_qrom(self, data):
        """
        Inserts a Qualtran QROM bloq of bitsize=bits decomposed into
        Clifford+T into a fresh Pandora table instance.
        """
        self.build_pandora()
        qrom_batches = get_qrom(data=data)

        for _, (batch, decomp_time) in enumerate(qrom_batches):
            insert_single_batch(connection=self.connection,
                                batch=batch)

        self.decompose_toffolis()

    def build_qualtran_qpe(self, num_sites=2, eps=1e-5, m_bits=1):
        self.build_pandora()
        qpe_batches = get_qpe_of_1d_ising_model(num_sites=num_sites,
                                                eps=eps,
                                                m_bits=m_bits)

        for _, (batch, decomp_time) in enumerate(qpe_batches):
            insert_single_batch(connection=self.connection,
                                batch=batch)

    def build_qualtran_hubbard_2d(self,
                                  dim=(2, 2),
                                  t=1,
                                  u=4):
        self.build_pandora()
        qpe_batches = get_2d_hubbard_model(dim=dim,
                                           t=t,
                                           u=u)

        for _, (batch, decomp_time) in enumerate(qpe_batches):
            insert_single_batch(connection=self.connection,
                                batch=batch)

    def build_maslov_adder(self, m_bits):
        self.build_pandora()

        db_tuples = get_maslov_adder(conn=self.connection,
                                     n_bits=m_bits)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=self.decomposition_window_size,
                          table_name='linked_circuit',
                          reset_id=False)

        self.decompose_toffolis()

    def build_fh_circuit(self, N, times, p_algo):
        CRED = '\033[91m'
        CEND = '\033[0m'

        print(f"Making FERMI-HUBBARD circuit...with window_size = {self.decomposition_window_size}")
        start_make = time.time()
        fh_circuit = make_fh_circuit(N=N,
                                     times=times,
                                     p_algo=p_algo)
        total_pyliqtr = time.time() - start_make
        print(f"Building pyliqtr circuit took: {total_pyliqtr}")
        pyliqtr_count = len(list(fh_circuit.all_operations()))

        self.build_pandora()
        reset_database_id(self.connection,
                          table_name='linked_circuit',
                          large_buffer_value=100000)

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=fh_circuit,
                                           window_size=self.decomposition_window_size)

        total_decomp_time = 0
        total_insert_times = 0
        pandora_count = 0

        for i, (batch, decomposition_time) in enumerate(batches):
            start_insert = time.time()
            insert_single_batch(connection=self.connection,
                                batch=batch)
            pandora_count += len(batch)
            total_insert_times += (time.time() - start_insert)
            total_decomp_time += decomposition_time

            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        insert_benchmark_row(connection=self.connection, benchmark_tuple=(N,
                                                                          total_pyliqtr,
                                                                          pyliqtr_count,
                                                                          total_decomp_time,
                                                                          total_insert_times,
                                                                          pandora_count,
                                                                          None,
                                                                          None,
                                                                          None
                                                                          ))

        print(f"DB insert took: {total_insert_times}")
        print(f"Decomposing circuit took: {time.time() - start_decomp}")
        print('Building edge list...')
        self.build_edge_list()

    def build_mg_coating_walk_op(self, data_path="."):
        CRED = '\033[91m'
        CEND = '\033[0m'

        print(f"Making MG circuit...with window_size = {self.decomposition_window_size}")
        start_make = time.time()
        mg_circuit = make_mg_coating_walk_op(EC=13, data_path=data_path)
        print(f"Building pyliqtr circuit took: {time.time() - start_make}")

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=mg_circuit,
                                           window_size=self.decomposition_window_size)
        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=100000)

        for i, (batch, decomposition_time) in enumerate(batches):
            insert_single_batch(connection=self.connection, batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        print(f"Decomposing circuit took: {time.time() - start_decomp}")

    def build_cyclic_o3(self, data_path="."):
        CRED = '\033[91m'
        CEND = '\033[0m'

        print(f"Making o3 circuit...with window_size = {self.decomposition_window_size}")
        start_make = time.time()
        o3_circuit = make_cyclic_o3_circuit(data_path=data_path)
        print(f"Building pyliqtr circuit took: {time.time() - start_make}")

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=o3_circuit,
                                           window_size=self.decomposition_window_size)
        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=100000)

        for i, (batch, decomposition_time) in enumerate(batches):
            insert_single_batch(connection=self.connection, batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        print(f"Decomposing circuit took: {time.time() - start_decomp}")

    def build_hc_circuit(self, data_path='.'):
        CRED = '\033[91m'
        CEND = '\033[0m'

        print(f"Making hc circuit...with window_size = {self.decomposition_window_size}")
        start_make = time.time()
        hc_circuit = make_hc_circuit(data_path=data_path)
        print(f"Building pyliqtr circuit took: {time.time() - start_make}")

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=hc_circuit,
                                           window_size=self.decomposition_window_size)
        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=100000)

        for i, (batch, decomposition_time) in enumerate(batches):
            insert_single_batch(connection=self.connection, batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        print(f"Decomposing circuit took: {time.time() - start_decomp}")

    def build_traverse_ising(self, N=2):
        CRED = '\033[91m'
        CEND = '\033[0m'

        print(f"Making ISING circuit...with window_size = {self.decomposition_window_size}")
        start_make = time.time()
        ti_circuit = make_transverse_ising_circuit(N=N)
        print(f"Building pyliqtr circuit took: {time.time() - start_make}")

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=ti_circuit,
                                           window_size=self.decomposition_window_size)
        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=100000)

        for i, (batch, decomposition_time) in enumerate(batches):
            insert_single_batch(connection=self.connection, batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        print(f"Decomposing circuit took: {time.time() - start_decomp}")

    def widgetize(self, max_t: int, max_d: int, batch_size: int, add_gin_per_widget: bool) -> Iterator[list[PandoraGate]]:
        """
        Widgetizes the circuit stored in the linked_list table. Note that it also builds the edge list.
        Args:
            add_gin_per_widget: adds the global in gate per widget
            batch_size: batch size of edges read from the edge_list table
            max_t: max nr. of T gates per widget
            max_d: max gate count per widget

        Returns:
            Generator over the widget list
        """
        batch_edges = self.get_batched_edge_list(batch_size=batch_size)

        for i, batch_of_edges in enumerate(batch_edges):
            if i != 0 and add_gin_per_widget:
                batch_of_edges = add_inputs(batch_of_edges)
            id_set = []
            for (s, t) in batch_of_edges:
                id_set.append(s)
                id_set.append(t)

            pandora_gates = self.get_pandora_gates_by_id(list(set(id_set)))
            pandora_gate_dict = dict([(pandora_gate.id, pandora_gate) for pandora_gate in pandora_gates])

            uf = UnionFindWidgetizer(edges=batch_of_edges,
                                     pandora_gates=pandora_gates,
                                     max_t=max_t,
                                     max_d=max_d)

            for node1, node2 in batch_of_edges:
                ret = uf.union(node1, node2)

            # once union-find call is done, compute the pandora gate list of each widget
            widgets = {}
            for node_id in uf.parent.keys():
                root_id = uf.parent[node_id].root.id
                if root_id not in widgets.keys():
                    widgets[root_id] = []
                widgets[root_id].append(pandora_gate_dict[node_id])

            for (root_id, widget_pandora_gates) in widgets.items():
                yield widget_pandora_gates



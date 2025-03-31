import time
import datetime

import psycopg2

from .parallel_decompose import parallel_decompose_and_insert
from .qualtran_to_pandora_util import *
from benchmarking.benchmark_adders import get_maslov_adder

from pandora.connection_util import *
from .widgetization.union_find import UnionFindWidgetizer


class PandoraConfig:
    database = "postgres"
    user = None
    host = "localhost"
    port = 5432
    password = "1234"

    def __init__(self):
        pass

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
        if self.pandora_config.database != 'postgres':
            self.create_database()
        self.connection = self.get_connection()
        self.stop_after = max_time
        self.decomposition_window_size = decomposition_window_size

    def __del__(self):
        self.connection.close()

    def create_database(self):
        """
        This gets you a connection to the postgres default database. Using this connection, you can then create a new
        named database.
        """
        try:
            connection_to_default = psycopg2.connect(
                database='postgres',
                user=self.pandora_config.user,
                host=self.pandora_config.host,
                port=self.pandora_config.port,
                password=self.pandora_config.password)

            connection_to_default.set_session(autocommit=True)
            connection_to_default.cursor().execute(f'create database {self.pandora_config.database}')
            connection_to_default.close()
        except psycopg2.errors.DuplicateDatabase as e:
            print(e)

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
        create_named_circuit_table(connection=self.connection,
                                   table_name=table_name)

    def build_edge_list(self) -> None:
        self.connection.cursor().execute(f"call generate_edge_list()")

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
        return get_gates_by_id_fast(connection=self.connection,
                                    ids=ids)

    def decompose_toffolis(self):
        """
        Decomposes all existing Toffoli gates in the Pandora into Clifford+T.
        """
        self.connection.cursor().execute("call linked_toffoli_decomp()")

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

    def build_pyliqtr_circuit(self,
                              pyliqtr_circuit: Any) -> None:
        """
        This method tries to build an arbitrary pyLIQTR circuit into Pandora. Note that the pyLIQTR decomposition
        might fail due to missing decompositions.
        Args:
            pyliqtr_circuit: the pyLIQTR circuit object
        """
        CRED = '\033[91m'
        CEND = '\033[0m'

        self.build_pandora()

        print("Decomposing circuit for pandora...")
        start_decomp = time.time()
        batches = windowed_cirq_to_pandora(circuit=pyliqtr_circuit,
                                           window_size=self.decomposition_window_size)

        for i, (batch, decomposition_time) in enumerate(batches):
            insert_single_batch(connection=self.connection, batch=batch)
            ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{CRED}Done inserting batch {i} at {ts}{CEND}")

        print(f"Decomposing circuit took: {time.time() - start_decomp}")
        print("Building edge list...")

        self.build_edge_list()

    def parallel_build_pyliqtr_circuit(self,
                                       nprocs: int,
                                       N: int,
                                       config_file_path: str = None) -> None:
        """
        This method tries to build an arbitrary pyLIQTR circuit into Pandora. Note that the pyLIQTR decomposition
        might fail due to missing decompositions.

        This is a parallel version of the building method, meaning that the decomposition of the circuit is performed
        in parallel. This implies that the pyLIQTR decomposition is performed only two levels, and then bloqs such as
        QubitizedRotation or PauliStringLCU ae decomposed in parallel. The circuit is divided into nprocs parts, and
        each process deals with its targeted region of the circuit.

        Only for the Fermi-Hubbard circuits for now.

        Args:
            nprocs: the number of parallel workers
            N: N parameter of the Feri-Hubbard circuit instance
            config_file_path: config file name. If None, will use defaults from PandoraConfig.
        """
        self.build_pandora()
        print("Decomposing circuit for pandora...")

        start_decomp = time.time()
        process_list = []
        for i in range(nprocs):
            p = Process(target=parallel_decompose_and_insert, args=(N,
                                                                    i,
                                                                    nprocs,
                                                                    config_file_path,
                                                                    self.decomposition_window_size))
            process_list.append(p)

        for i in range(nprocs):
            process_list[i].start()
        for i in range(nprocs):
            process_list[i].join()

        print(f"Decomposing circuit took: {time.time() - start_decomp}")

    def widgetize(self,
                  max_t: int,
                  max_d: int,
                  batch_size: int,
                  add_gin_per_widget: bool) -> Iterator[list[PandoraGate]]:
        """
        Widgetizes the circuit stored in the linked_list table. Note that this method assumes
        the edge list is pre-built.
        Args:
            add_gin_per_widget: if True, adds the global in gate per widget
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

            pandora_gates = self.get_pandora_gates_by_id(ids=list(set(id_set)))

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

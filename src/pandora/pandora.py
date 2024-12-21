from .pyliqtr_to_pandora_util import make_transverse_ising_circuit, make_fh_circuit, make_mg_coating_walk_op, \
    make_cyclic_o3_circuit, make_hc_circuit
from .qualtran_to_pandora_util import *
from benchmarking.benchmark_adders import get_maslov_adder

from pandora.connection_util import *
from pandora.qualtran_to_pandora_util import get_pandora_compatible_circuit


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
            self.port = data["port"]
            self.password = data["password"]
        CRED = '\033[91m'
        CEND = '\033[0m'
        print(f"{CRED}Loaded Pandora config from file: {path}", self.__dict__, f"{CEND}")


class Pandora:

    def __init__(self, pandora_config=PandoraConfig(), max_time=3600):
        self.connection = self.get_connection()
        self.stop_after = max_time

        self.pandora_config = pandora_config

    def __del__(self):
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
        drop_and_replace_tables(self.connection, clean=True, verbose=True)
        refresh_all_stored_procedures(self.connection, verbose=True)

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
        self.build_pandora()
        cirq_adder: cirq.Circuit() = get_adder(n_bits=bitsize)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=cirq_adder,
                                       last_id=0,
                                       label=f'a',
                                       add_margins=True)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          table_name='linked_circuit',
                          batch_size=1000000,
                          reset_id=True)

        self.decompose_toffolis()

    def build_qualtran_qrom(self, data):
        """
        Inserts a Qualtran QROM bloq of bitsize=bits decomposed into
        Clifford+T into a fresh Pandora table instance.
        """
        self.build_pandora()
        cirq_qrom = get_qrom(data=data)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=cirq_qrom,
                                       last_id=0,
                                       label=f'r',
                                       add_margins=True)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          table_name='linked_circuit',
                          batch_size=1000000,
                          reset_id=True)

        self.decompose_toffolis()

    def build_maslov_adder(self, m_bits):
        self.build_pandora()

        db_tuples = get_maslov_adder(conn=self.connection, n_bits=m_bits)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit',
                          reset_id=False)

        self.decompose_toffolis()

        # TODO: This should be cleaned
        #  There is a collector.py the results branch
        # proc = subprocess.Popen([f'./readout_epyc.sh results_{m_bits}.csv'], shell=True, executable="/bin/bash")
        # db_multi_threaded(thread_proc=thread_procedures)
        # subprocess.Popen.kill(proc)

    def build_fh_circuit(self, N=10, p_algo=0.9999999904, times=0.01):
        print("Making fh circuit...")
        fh_circuit = make_fh_circuit(N=N, p_algo=p_algo, times=times)

        self.build_pandora()
        decomposed_circuit = get_pandora_compatible_circuit(circuit=fh_circuit, decompose_from_high_level=True)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='f', add_margins=True)

        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=1000)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit')

        print('Done fh_circuit!')

    def build_mg_coating_walk_op(self, data_path="."):
        print("Making mg circuit...")
        mg_circuit = make_mg_coating_walk_op(EC=13, data_path=data_path)
        print(type(mg_circuit))

        decomposed_circuit = get_pandora_compatible_circuit(circuit=mg_circuit, decompose_from_high_level=True)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='m', add_margins=True)

        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=1000)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit')
        print('Done mg_circuit!')

    def build_cyclic_o3(self):
        print("Making o3 circuit...")
        o3_circuit = make_cyclic_o3_circuit()

        decomposed_circuit = get_pandora_compatible_circuit(circuit=o3_circuit, decompose_from_high_level=True)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='o', add_margins=True)

        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=1000)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit')

        print('Done o3_circuit!')

    def build_hc_circuit(self):
        print("Making hc circuit...")
        hc_circuit = make_hc_circuit()

        decomposed_circuit = get_pandora_compatible_circuit(circuit=hc_circuit, decompose_from_high_level=True)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='h', add_margins=True)

        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=1000)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit')

        print('Done hc_circuit!')

    def build_traverse_ising(self, N=2):
        print("Making ti circuit...")
        ti_circuit = make_transverse_ising_circuit(N=N)
        print(type(ti_circuit))

        decomposed_circuit = get_pandora_compatible_circuit(circuit=ti_circuit, decompose_from_high_level=True)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='i', add_margins=True)

        self.build_pandora()
        reset_database_id(self.connection, table_name='linked_circuit', large_buffer_value=1000)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit')
        print('Done ti_circuit!')

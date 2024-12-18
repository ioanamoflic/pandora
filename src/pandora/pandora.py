import subprocess

import cirq

from .cirq_to_pandora_util import *
from .qualtran_to_pandora_util import *
from benchmarking.benchmark_adders import get_maslov_adder
from .connection_util import db_multi_threaded, refresh_all_stored_procedures, drop_and_replace_tables, insert_in_batches, \
    get_connection

class Pandora:

    def __init__(self, max_time):
        self.connection = get_connection()
        self.cursor = self.connection.cursor()
        self.stop_after = max_time

    def __del__(self):
        self.connection.close()

    def build_pandora(self):
        """
        Creates the Pandora database table from scratch and updates all stored procedures.
        """
        drop_and_replace_tables(self.connection, clean=True)
        refresh_all_stored_procedures(self.connection)

    def decompose_toffolis(self):
        """
        Decomposes all existing Toffoli gates in the Pandora into Clifford+T.
        """
        self.cursor.execute("call linked_toffoli_decomp()")

    def build_qualtran_adder(self, bitsize):
        """
        Inserts a Qualtran adder bloq of bitsize=bits decomposed into
        Clifford+T into a fresh Pandora table instance.
        """
        self.build_pandora()
        cirq_adder: cirq.Circuit() = get_adder(n_bits=bitsize)
        db_tuples, _ = cirq_to_pandora(cirq_circuit=cirq_adder,
                                       last_id=0,
                                       label=f'Adder{bitsize}',
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
                                       label=f'QROM',
                                       add_margins=True)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          table_name='linked_circuit',
                          batch_size=1000000,
                          reset_id=True)

        self.decompose_toffolis()

    def benchmark_maslov_adder(self, m_bits):
        self.build_pandora()

        db_tuples = get_maslov_adder(conn=self.connection, n_bits=m_bits)
        insert_in_batches(pandora_gates=db_tuples,
                          connection=self.connection,
                          batch_size=1000000,
                          table_name='linked_circuit',
                          reset_id=True)

        self.decompose_toffolis()

        myH = PandoraGateTranslator.HPowGate.value
        myCX = PandoraGateTranslator.CXPowGate.value
        myZPow = PandoraGateTranslator.ZPowGate.value
        myPauliX = PandoraGateTranslator._PauliX.value
        myPauliZ = PandoraGateTranslator._PauliZ.value

        print('...running optimization')
        thread_procedures = [
            (8, f"CALL cancel_single_qubit_bernoulli({myH}, {myH}, 1, 1, 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli({myPauliZ}, {myPauliZ}, 1, 1, 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli({myZPow}, {myZPow}, 0.25, -0.25, 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli({myPauliX}, {myPauliX}, 1, 1, 10, 10000000)"),
            (4, f"CALL cancel_two_qubit_bernoulli({myCX}, {myCX}, 1, 10, 10000000)"),
            (4, f"CALL replace_two_qubit_bernoulli({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, 10, 10000000)"),
            (
                4,
                f"CALL replace_two_qubit_bernoulli({myZPow}, {myZPow}, {myPauliZ}, -0.5, -0.5, -1.0, 10, 10000000)"),
            (
                4,
                f"CALL replace_two_qubit_bernoulli({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli({myZPow}, 0.25, 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli({myZPow}, -0.25, 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli({myZPow}, 0.5, 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli({myZPow}, -0.5, 10, 10000000)"),
            (4, f"CALL linked_hhcxhh_to_cx_bernoulli(10, 10000000)"),
            (4, f"CALL linked_cx_to_hhcxhh_bernoulli(10, 10000000)"),
            (1, f"CALL stopper({self.stop_after})")
        ]

        # TODO: This should be cleaned
        #  There is a collector.py the results branch
        proc = subprocess.Popen([f'./readout_epyc.sh results_{m_bits}.csv'], shell=True, executable="/bin/bash")
        db_multi_threaded(thread_proc=thread_procedures)
        subprocess.Popen.kill(proc)

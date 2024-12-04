import subprocess
from benchmarking.benchmark_adders import get_maslov_adder
from qualtran2db import *

class Pandora:

    def __init__(self):
        self.connection = get_connection()
        self.cursor = self.connection.cursor()

    def __del__(self):
        self.connection.close()

    def benchmark_adder(self, bits):
        self.refresh_pandora()

        db_tuples = get_maslov_adder(conn=self.connection, n_bits=bits)
        insert_in_batches(db_tuples=db_tuples, connection=self.connection, batch_size=1000000, reset_id=100000)

        print('...decomposing Toffolis')
        self.cursor.execute("call linked_toffoli_decomp()")

        print('...running optimization')
        stop_after = 3600
        thread_procedures = [
            (1, f"CALL stopper({stop_after});"),
            (8, f"CALL cancel_single_qubit_bernoulli('HPowGate', 'HPowGate', 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli('ZPowGate**0.25', 'ZPowGate**-0.25', 10, 10000000)"),
            (4, f"CALL cancel_single_qubit_bernoulli('_PauliX', '_PauliX', 10, 10000000)"),
            (4, f"CALL cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', 10, 10000000)"),
            (4, f"CALL replace_two_qubit_bernoulli('ZPowGate**0.25', 'ZPowGate**0.25', 'ZPowGate**0.5', 0.5, 10, "
                f"10000000)"),
            (4, f"CALL replace_two_qubit_bernoulli('ZPowGate**-0.25', 'ZPowGate**-0.25', 'ZPowGate**-0.5', 0.5, 10, "
                f"10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**0.25', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**-0.25', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**0.5', 10, 10000000)"),
            (4, f"CALL commute_single_control_left_bernoulli('ZPowGate**-0.5', 10, 10000000)"),
            (4, f"CALL linked_hhcxhh_to_cx_bernoulli(10, 10000000);"),
            (1, f"CALL linked_cx_to_hhcxhh_bernoulli(10, 10000000);"),
        ]

        # TODO: This should be cleaned
        #  There is a collector.py the results branch
        proc = subprocess.Popen([f'./readout_epyc.sh results_{bits}.csv'], shell=True, executable="/bin/bash")
        db_multi_threaded(thread_proc=thread_procedures)
        subprocess.Popen.kill(proc)

    def refresh_pandora(self):
        print('...refreshing table')
        create_linked_table(self.connection, clean=True)
        refresh_all_stored_procedures(self.connection)


if __name__ == "__main__":

    mypandora = Pandora()

    import sys

    if len(sys.argv) == 1:
        sys.exit(0)

    if sys.argv[1] == "adder":
        # n_bits = [8, 16, 32, 64, 128, 256, 512, 1024, 2048]
        n_bits = int(sys.argv[2])
        for bits in n_bits:
            mypandora.benchmark_adder(bits)

    elif sys.argv[1] == "tket":
        print("tket")





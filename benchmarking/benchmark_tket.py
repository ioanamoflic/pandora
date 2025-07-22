import random
import sys
import time
import csv

import qiskit
from pytket import Circuit
from pytket._tket.passes import RemoveRedundancies

from pandora.connection_util import get_connection, drop_and_replace_tables, refresh_all_stored_procedures, \
    insert_in_batches, reset_database_id, db_multi_threaded
from pandora.gate_translator import PandoraGateTranslator
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def generate_random_CX_circuit(n_templates, n_qubits):
    circ_tket = Circuit(n_qubits)
    circ_qiskit = qiskit.QuantumCircuit(n_qubits, n_qubits)

    for t in range(n_templates):
        q1, q2 = random.choices(range(0, n_qubits), k=2)
        while q1 == q2:
            q1, q2 = random.choices(range(0, n_qubits), k=2)

        circ_tket.CX(q1, q2, opgroup=str(t))
        circ_qiskit.cx(q1, q2)

    return circ_tket, circ_qiskit


def generate_random_HH_circuit(n_templates, n_qubits):
    circ_tket = Circuit(n_qubits)
    circ_pandora = qiskit.QuantumCircuit(n_qubits, n_qubits)

    for t in range(n_templates):
        q1 = random.choice(range(0, n_qubits))

        circ_tket.H(qubit=q1)
        circ_tket.H(qubit=q1)

        circ_pandora.h(q1)
        circ_pandora.h(q1)

    return circ_tket, circ_pandora


def optimize_circuit(circuit):
    RemoveRedundancies().apply(circuit)
    return circuit.get_commands()


def cx_to_hhcxhh_transform_random(circ: Circuit) -> Circuit:
    template = Circuit(2).H(0).H(1).CX(0, 1).H(0).H(1)

    gate_list = list(circ.get_commands())
    gate_count_circ = len(gate_list)
    data = list(range(0, gate_count_circ))
    random.shuffle(data)
    i = 0

    nr_success = 0
    while nr_success < gate_count_circ:
        random_position = data[i]
        i += 1
        x = circ.substitute_named(template, str(random_position))
        if x is True:
            nr_success += 1
    return circ


def test_cancel_hh(connection,
                   initial_circuit: qiskit.QuantumCircuit,
                   repetitions: int,
                   nprocs: int = 1,
                   bernoulli_percentage=10):
    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    myH = PandoraGateTranslator.HPowGate.value
    thread_procedures = [
        (nprocs - 1,
         f"call cancel_single_qubit({myH}, {myH}, {0}, {0}, {bernoulli_percentage}, {repetitions // nprocs})"),
        (1,
         f"call cancel_single_qubit({myH}, {myH}, {0}, {0}, {bernoulli_percentage}, {repetitions - (nprocs - 1) * (repetitions // nprocs)})"),
    ]

    start_pandora = time.time()
    db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])
    return time.time() - start_pandora


def test_cx_to_hhcxhh_visit_all(connection,
                                initial_circuit: qiskit.QuantumCircuit,
                                repetitions: int,
                                nprocs: int = 1,
                                bernoulli_percentage=10):

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    thread_procedures = [
        (nprocs - 1, f"call linked_cx_to_hhcxhh_batched({bernoulli_percentage}, {repetitions // nprocs})"),
        (1,
         f"call linked_cx_to_hhcxhh_batched({bernoulli_percentage}, {repetitions - (nprocs - 1) * (repetitions // nprocs)})"),
    ]

    start_pandora = time.time()
    db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])
    return time.time() - start_pandora


if __name__ == "__main__":
    random.seed(0)

    # n_CX = [1000, 10000, 100000, 1000000, 10000000]
    n_gates = [1000000]

    FILENAME = None
    EQUIV = 0
    BENCH = None
    conn = None
    NPROCS = 1
    TYPE = None

    if len(sys.argv) == 3:
        FILENAME = sys.argv[1]
        BENCH = sys.argv[2]
    elif len(sys.argv) == 5:
        FILENAME = sys.argv[1]
        BENCH = sys.argv[2]
        NPROCS = int(sys.argv[3])
        TYPE = sys.argv[4]

    for gate_count in n_gates:
        if BENCH.startswith('pandora'):
            conn = get_connection(config_file_path=FILENAME)
            print(f"Running config file {FILENAME}")

        print('Testing template count:', gate_count)

        if TYPE == 'h':
            tket_circ, pandora_circ = generate_random_HH_circuit(n_templates=gate_count,
                                                                 n_qubits=50)
        else:
            tket_circ, pandora_circ = generate_random_CX_circuit(n_templates=gate_count,
                                                                 n_qubits=50)

        if BENCH.startswith('pandora'):
            start_time = time.time()
            if TYPE == 'h':
                op_time = test_cancel_hh(connection=conn,
                                         initial_circuit=pandora_circ,
                                         nprocs=NPROCS,
                                         bernoulli_percentage=100,
                                         repetitions=gate_count)
            else:
                op_time = test_cx_to_hhcxhh_visit_all(connection=conn,
                                                      initial_circuit=pandora_circ,
                                                      nprocs=NPROCS,
                                                      bernoulli_percentage=100,
                                                      repetitions=gate_count)
            print('Pandora time: ', op_time)
        else:
            start_time = time.time()
            if TYPE == 'h':
                tket_circ_commands = optimize_circuit(circuit=tket_circ)
            else:
                tket_circ = cx_to_hhcxhh_transform_random(tket_circ)

            op_time = time.time() - start_time
            print('TKET time:', op_time)

        with open(f'{BENCH}_{TYPE}_rma_{NPROCS}.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((gate_count, op_time, BENCH, NPROCS))

    if BENCH.startswith('pandora'):
        conn.close()

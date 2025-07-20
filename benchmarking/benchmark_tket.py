import random
import sys
import time
import csv

import qiskit
from pytket import Circuit
from pytket._tket.passes import RemoveRedundancies

from pandora.connection_util import get_connection, drop_and_replace_tables, refresh_all_stored_procedures, \
    insert_in_batches, reset_database_id, db_multi_threaded
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def generate_random_CX_circuit(n_templates, n_qubits):
    circ_tket = Circuit(n_qubits)
    circ_pandora = qiskit.QuantumCircuit(n_qubits, n_qubits)

    for t in range(n_templates):
        q1, q2 = random.choices(range(0, n_qubits), k=2)
        while q1 == q2:
            q1, q2 = random.choices(range(0, n_qubits), k=2)

        circ_tket.CX(q1, q2, opgroup=str(t))
        circ_pandora.cx(q1, q2)

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


def test_cx_to_hhcxhh_visit_all(connection,
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

    thread_procedures = [
        (nprocs - 1, f"call linked_cx_to_hhcxhh_visit({bernoulli_percentage}, {repetitions // nprocs})"),
        (1,
         f"call linked_cx_to_hhcxhh_visit({bernoulli_percentage}, {repetitions - (nprocs - 1) * (repetitions // nprocs)})"),
    ]

    start_pandora = time.time()
    db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])
    return time.time() - start_pandora


if __name__ == "__main__":
    random.seed(0)

    # n_CX = [1000, 10000, 100000, 1000000, 10000000]
    n_CX = [1000000]

    FILENAME = None
    EQUIV = 0
    BENCH = None
    conn = None
    NPROCS = 1

    if len(sys.argv) == 3:
        FILENAME = sys.argv[1]
        BENCH = sys.argv[2]
    elif len(sys.argv) == 4:
        FILENAME = sys.argv[1]
        BENCH = sys.argv[2]
        NPROCS = int(sys.argv[3])

    if BENCH.startswith('pandora'):
        conn = get_connection(config_file_path=FILENAME)
        print(f"Running config file {FILENAME}")

    times = []
    for cx_count in n_CX:
        print('Testing CX count:', cx_count)

        tket_circ, pandora_circ = generate_random_CX_circuit(n_templates=cx_count,
                                                             n_qubits=50)

        if BENCH.startswith('pandora'):
            start_time = time.time()
            op_time = test_cx_to_hhcxhh_visit_all(connection=conn,
                                                  initial_circuit=pandora_circ,
                                                  nprocs=NPROCS,
                                                  bernoulli_percentage=1000,
                                                  repetitions=cx_count)
            # op_time = time.time() - start_time
            print('Pandora time: ', op_time)
        else:
            start_time = time.time()
            tket_circ = cx_to_hhcxhh_transform_random(tket_circ)
            op_time = time.time() - start_time
            print('TKET time:', op_time)

        times.append((cx_count, op_time, BENCH, NPROCS))

    with open(f'{BENCH}_rma_{NPROCS}.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    if BENCH.startswith('pandora'):
        conn.close()

import csv

import qiskit
from qiskit.converters import circuit_to_dag
from qiskit.quantum_info import random_clifford
from qiskit.dagcircuit import DAGCircuit

from pandora.connection_util import *
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def test_cx_to_hhcxhh_bernoulli(connection,
                                initial_circuit: qiskit.QuantumCircuit,
                                repetitions: int,
                                bernoulli_percentage=0.1):
    cursor = connection.cursor()

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

    print('I started optimizing...')

    st_time = time.time()
    cursor.execute(f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {repetitions})")

    return time.time() - st_time


def test_cx_to_hhcxhh_visit(connection,
                            initial_circuit: qiskit.QuantumCircuit,
                            sys_percentage=10,
                            nr_passes=1):

    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    dag: DAGCircuit = circuit_to_dag(initial_circuit)

    op_count = dag.count_ops()
    cx_count = op_count['cx']

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

    print('I started optimizing...')
    st_time = time.time()
    # cursor.execute(f"call linked_cx_to_hhcxhh_visit({sys_percentage}, {cx_count // ratio})")
    cursor.execute(f"call linked_cx_to_hhcxhh_seq({sys_percentage}, {nr_passes})")

    return time.time() - st_time


def test_cx_to_hhcxhh_cached_ids(connection,
                                 initial_circuit: qiskit.QuantumCircuit):
    cursor = connection.cursor()

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

    # get all ids of all CNOTs
    cursor.execute(f"call memorize_cx_ids()")

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)

    st_time = time.time()

    print('I started optimizing...')
    cursor.execute(f"call linked_cx_to_hhcxhh_cached()")
    print('I finished optimizing...')

    return time.time() - st_time


if __name__ == "__main__":
    conn = get_connection()

    # n_qub = [10, 100, 1000]
    # ratios = [8, 4, 2, 1]

    n_qub = [1000]
    ratios = [1]

    times = []

    for nq in range(10000, 100001, 10000):
        for ratio in ratios:
            print('Number of qubits:', nq)
            # print('Ratio:', ratio)

            from benchmark_tket import generate_random_CX_circuit
            qc = generate_random_CX_circuit(n_templates=nq, n_qubits=50)[1]

            # qc = random_clifford(num_qubits=nq, seed=0).to_circuit()
            # qc = qiskit.qasm3.load(f"qiskit_{nq}.qasm")

            tot_time = test_cx_to_hhcxhh_visit(connection=conn, initial_circuit=qc, sys_percentage=0.1, nr_passes=100)
            times.append((nq, ratio, tot_time))
            print('time to optimize:', tot_time)

    with open('pandora_cx_flip.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    conn.close()

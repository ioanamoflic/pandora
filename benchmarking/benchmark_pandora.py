import random
import csv

import qiskit
from qiskit.converters import circuit_to_dag
from qiskit.quantum_info import random_clifford
from qiskit.dagcircuit import DAGCircuit

from pandora.connection_util import *
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def generate_random_CX_circuit(n_templates, n_qubits=50):
    qubits = [cirq.LineQubit(i) for i in range(n_qubits)]
    c = cirq.Circuit()
    for _ in range(n_templates):
        q1, q2 = random.choices(qubits, k=2)
        while q1 == q2:
            q1, q2 = random.choices(qubits, k=2)
        c.append(cirq.CNOT.on(q1, q2))

    return c


def gate_count(circuit):
    cnt = 0
    for mom in circuit:
        cnt += len(mom)
    return cnt


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

    st_time = time.time()
    print('I started optimizing...')
    cursor.execute(f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {repetitions})")
    print('I finished optimizing...')

    return time.time() - st_time


def test_cx_to_hhcxhh_visit(connection,
                            initial_circuit: qiskit.QuantumCircuit,
                            n_qubits: int):
    # make sure you use the right sampling method
    if n_qubits < 1000:
        sys_percent = 1
    else:
        sys_percent = 0.1

    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)

    dag: DAGCircuit = circuit_to_dag(initial_circuit)

    op_count = dag.count_ops()
    cx_count = op_count['cx']
    total_gate_count = sum(op_count.values())

    sys_percentage = int(total_gate_count * sys_percent)

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

    st_time = time.time()
    print('I started optimizing...')
    cursor.execute(f"call linked_cx_to_hhcxhh_visit({sys_percentage}, {cx_count})")
    print('I finished optimizing...')

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
    n_qub = [10, 100, 1000, 10000, 100000]

    times = []

    for nq in n_qub:
        print('number of qubits:', nq)
        qc = random_clifford(num_qubits=nq, seed=0).to_circuit()

        start_time = time.time()
        tot_time = test_cx_to_hhcxhh_cached_ids(connection=conn,
                                                initial_circuit=qc)
        print('time to optimize:', tot_time)
        times.append(tot_time)

    rows = zip(n_qub, times)

    with open('results/db_random.csv', 'w') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

    conn.close()

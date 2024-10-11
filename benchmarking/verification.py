import csv
import time
from benchmarking.benchmark_db import generate_random_CX_circuit
from cirq2db import *
from qualtran2db import *


def concatenate(connection, initial_circuit, cnt):
    create_linked_table(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=initial_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, connection=connection, reset_id=10000000)

    thread_procedures = [
        (1, f"call linked_cx_to_hhcxhh_bernoulli(50, {cnt})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    extracted_circuit_reversed = extracted_circuit[::-1]
    qubit_map = dict(
        zip(
            sorted(initial_circuit.all_qubits()),
            sorted(extracted_circuit_reversed.all_qubits())
        )
    )
    initial_circuit = initial_circuit.transform_qubits(qubit_map=qubit_map)
    concatenated_circuit = cirq.Circuit(initial_circuit.moments + extracted_circuit_reversed.moments)

    return concatenated_circuit


def verify_C_Ct_eq_I(connection, concatenated_circuit, cnt):
    create_linked_table(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = cirq_to_db(cirq_circuit=concatenated_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(db_tuples=db_tuples, connection=connection, reset_id=10000000)

    thread_procedures = [
        (1, f"call linked_hhcxhh_to_cx_bernoulli(50, {cnt})"),
        (1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', 50, {cnt})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    assert len(extracted_circuit) == 0


if __name__ == "__main__":
    conn = get_connection()
    times = []
    for cx_count in range(2, 100):
        init_circuit = generate_random_CX_circuit(n_templates=cx_count, n_qubits=cx_count)
        concatenated = concatenate(connection=conn, initial_circuit=init_circuit, cnt=cx_count)
        start_time = time.time()
        verify_C_Ct_eq_I(connection=conn, concatenated_circuit=concatenated, cnt=cx_count)
        times.append((cx_count, time.time() - start_time))
        print(cx_count)
    conn.close()

    with open('results/verification.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

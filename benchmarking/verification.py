import csv
import time
from benchmarking.benchmark_db import generate_random_CX_circuit
from pandora.connection_util import *

TIMEOUT_VAL = 10000000


def concatenate(connection, init_circ, cnt, bernoulli_percentage=10):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = cirq_to_pandora(cirq_circuit=init_circ, last_id=0, add_margins=True, label='verification')
    insert_in_batches(pandora_gates=db_tuples, connection=connection, reset_id=True, table_name='linked_circuit')

    thread_procedures = [
        (1, f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {cnt})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)

    extracted_circuit_reversed = extracted_circuit[::-1]
    qubit_map = dict(
        zip(
            sorted(init_circ.all_qubits()),
            sorted(extracted_circuit_reversed.all_qubits())
        )
    )
    init_circ = init_circ.transform_qubits(qubit_map=qubit_map)
    concatenated_circuit = cirq.Circuit(init_circ.moments + extracted_circuit_reversed.moments)

    return concatenated_circuit


def verify_C_Ct_eq_I(connection, concatenated_circuit, cnt, bernoulli_percentage, max_thr, single_threaded=False, stop_after=10):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = cirq_to_pandora(cirq_circuit=concatenated_circuit, last_id=0, add_margins=True, label='verification')
    insert_in_batches(pandora_gates=db_tuples, connection=connection, reset_id=True, table_name='linked_circuit')

    if single_threaded is True:
        thread_procedures = [
            (1, f"call stopper({stop_after});"),
            (1, f"call linked_hhcxhh_to_cx_bernoulli({bernoulli_percentage}, {cnt})"),
            (1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', {bernoulli_percentage}, {cnt})"),
        ]
    else:
        thread_procedures = [(1, f"call stopper({stop_after});")]
        for _ in range(max_thr):
            thread_procedures.append((1, f"call linked_hhcxhh_to_cx_bernoulli({bernoulli_percentage}, 1)"))
            thread_procedures.append((1, f"call cancel_two_qubit_bernoulli('CXPowGate', 'CXPowGate', "
                                         f"{bernoulli_percentage}, 1)"))

    start_time = time.time()
    db_multi_threaded(thread_proc=thread_procedures)
    total_time = time.time() - start_time
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=f'verification',
                                             remove_io_gates=True)
    if len(extracted_circuit) != 0:
        return TIMEOUT_VAL
    return total_time


if __name__ == "__main__":
    single_thr = False
    bp = 25
    repetitions = 10
    max_threads = 32
    cx_count = [1000, 10000, 100000, 1000000, 10000000]
    circuits = [generate_random_CX_circuit(n_templates=cnt, n_qubits=cnt) for cnt in cx_count]

    conn = get_connection()

    for stop in [100, 1000, 10000]:
        print(stop)
        for i in range(repetitions):
            print(i)
            times = []
            for j, cxc in enumerate(cx_count):
                print(cxc)
                concatenated = concatenate(connection=conn,
                                           init_circ=circuits[j],
                                           cnt=cxc,
                                           bernoulli_percentage=bp)
                time_val = verify_C_Ct_eq_I(connection=conn,
                                            concatenated_circuit=concatenated,
                                            cnt=cxc,
                                            single_threaded=single_thr,
                                            bernoulli_percentage=bp,
                                            stop_after=stop,
                                            max_thr=max_threads
                                            )

                times.append((cxc, time_val))
                print(f"Iteration {i} for circuit with {cxc} gates took {time_val}s.")

            with open(f'results/verification_st_is_{str(single_thr)}_{stop}_{i}.csv', 'w') as f:
                writer = csv.writer(f)
                for row in times:
                    writer.writerow(row)
    conn.close()


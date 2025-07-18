import csv
import sys
import time

import qiskit.qasm3
from mqt.qcec import verify

from qiskit import QuantumCircuit

from pandora.connection_util import *

import random

from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def generate_random_cnot_circuit(num_qubits=2, num_gates=8):
    if num_qubits < 2:
        print("Warning: num_qubits must be at least 2 for a CNOT gate. Setting to 2.")
        num_qubits = 2

    qc = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(num_gates):
        control_qubit = random.randint(0, num_qubits - 1)
        target_qubit = control_qubit
        while target_qubit == control_qubit:
            target_qubit = random.randint(0, num_qubits - 1)

        qc.cx(control_qubit, target_qubit)

    return qc


def remove_random_gate(circuit: QuantumCircuit) -> QuantumCircuit:
    if not circuit.data:
        print("Circuit has no gates to remove.")
        return circuit

    gate_index_to_remove = random.randint(0, len(circuit.data) - 1)
    # print(f"Removing gate at index: {gate_index_to_remove}")

    new_qc = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

    for i, instruction in enumerate(circuit.data):
        if i != gate_index_to_remove:
            new_qc.append(instruction.operation, instruction.qubits, instruction.clbits)

    return new_qc


def pandora_verify(connection,
                   circ1: QuantumCircuit,
                   circ2: QuantumCircuit):
    concatenated = circ1.compose(circ2.inverse())
    nr_cnots = concatenated.count_ops()['cx'] // 2
    print(nr_cnots)

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=concatenated,
                                             add_margins=True,
                                             label='q')
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    CX = PandoraGateTranslator.CXPowGate.value

    st_time = time.time()
    nr_rewrites = nr_cnots
    nr_procs = 24
    window = 1000
    thread_procedures = [
        (nr_procs - 1, f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, {nr_rewrites // nr_procs})"),
        (1,
         f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, {nr_rewrites - (nr_procs - 1) * (nr_rewrites // nr_procs)})"),
    ]

    db_multi_threaded(thread_proc=thread_procedures, config_file_path=sys.argv[1])

    end_time = time.time() - st_time

    circuit = extract_cirq_circuit(connection=connection,
                                   table_name='linked_circuit',
                                   circuit_label=None,
                                   is_test=False,
                                   remove_io_gates=True)
    is_equivalent = False
    if len(circuit) == 0:
        is_equivalent = True

    return end_time, is_equivalent


if __name__ == "__main__":
    # watch "psql -p 5432 postgres -c \"select count(*) from linked_circuit;\""

    FILENAME = None
    EQUIV = 0

    if len(sys.argv) == 1:
        sys.exit(0)
    elif len(sys.argv) == 2:
        EQUIV = int(sys.argv[1])
    elif len(sys.argv) == 3:
        FILENAME = sys.argv[1]
        EQUIV = int(sys.argv[2])

    conn = get_connection(config_file_path=FILENAME)
    print(f"Running config file {FILENAME}")

    benchmark_equiv = EQUIV
    times = []

    for q in range(20, 21, 2):
        total = 0
        nr_runs = 10

        for i in range(nr_runs):
            circ1 = generate_random_cnot_circuit(q, q ** 3)

            # circ1 = qiskit.qasm3.load(f"circ1_{q}_{0}.qasm")

            # with open(f"circ1_{q}_{i}.qasm", "w") as f:
            #     qiskit.qasm3.dump(circ1, f)

            if benchmark_equiv == 0:
                print(q, i, "correct ", end="")

                circ2 = circ1.copy()
                check_time, equiv = pandora_verify(connection=conn,
                                                   circ1=circ1,
                                                   circ2=circ2)
                print('Pandora time: ', check_time)
                print('Equiv: ', equiv)

                # result = verify(circ1, circ2)
                # check_time = result.check_time
                # print('MQT time: ', check_time)

                total = total + check_time
                times.append((q, i, equiv, check_time))

            elif benchmark_equiv == 1:
                print(q, i, "wrong ", end="")

                circ2 = circ1.copy()
                # remove one gate
                circ2 = remove_random_gate(circ2)

                check_time, equiv = pandora_verify(connection=conn,
                                                   circ1=circ1,
                                                   circ2=circ2)
                print('Pandora time: ', check_time)
                print('Equiv: ', equiv)

                # result = verify(circ1, circ2)
                # time = result.check_time
                # print('MQT time: ', time)

                total = total + check_time
                times.append((q, i, equiv, check_time))

        print("----- ", total / nr_runs)

    with open('mqt_verification.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    conn.close()

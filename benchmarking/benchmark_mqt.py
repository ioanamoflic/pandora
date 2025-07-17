import csv

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
                   circ2: QuantumCircuit,
                   one_missing=False):
    """

    """
    concatenated = circ1.compose(circ2.inverse())
    nr_cnots = concatenated.count_ops()['cx'] // 2
    print(nr_cnots)

    cursor = connection.cursor()
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

    nr_rewrites = nr_cnots - (1 if one_missing else 0)
    nr_procs = 4
    window = 1000
    thread_procedures = [
        #(1, f"call stopper({600});"),
        (nr_procs - 1, f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, {nr_rewrites // nr_procs})"),
        (1, f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, {nr_rewrites - (nr_procs - 1) * (nr_rewrites // nr_procs)})"),

        # (nr_procs - 1, f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, 500)"),
        # (1, f"call cancel_two_qubit_equiv({CX}, {CX}, 0, {window}, 500)"),
    ]

    db_multi_threaded(thread_proc=thread_procedures)

    return time.time() - st_time


if __name__ == "__main__":

    # in case shit happens!
    # pg_ctl - D /opt/homebrew/var/postgresql@14 restart

    # watch
    # watch "psql -p 5432 postgres -c \"select count(*) from linked_circuit;\""

    conn = get_connection()
    times = []

    for q in range(30, 31, 2):

        total = 0
        nr_runs = 3
        for i in range(nr_runs):
            circ1 = generate_random_cnot_circuit(q, q ** 3)

            # circ1 = qiskit.qasm3.load(f"circ1_{q}_{0}.qasm")

            print(q, i, "correct ", end="")

            with open(f"circ1_{q}_{i}.qasm", "w") as f:
                qiskit.qasm3.dump(circ1, f)

            circ2 = circ1.copy()
            pandora_time_1 = pandora_verify(connection=conn,
                                            circ1=circ1,
                                            circ2=circ2)
            print('Pandora time: ', pandora_time_1)
            total = total + pandora_time_1

            # result_1 = verify(circ1, circ2)
            # print('MQT: ', result_1.check_time)
            # total = total + result_1.check_time

            # print(q, i, "wrong ", end="")
            # circ2 = remove_random_gate(circ1)
            # # result_2 = verify(circ1, circ2)
            # # print('MQT: ', result_2.check_time)
            #
            # pandora_time_2 = pandora_verify(connection=conn,
            #                                 circ1=circ1,
            #                                 circ2=circ2,
            #                                 one_missing=True)
            # print('Pandora time: ', pandora_time_2)

            # times.append((q, i, result_1, pandora_time_1, result_2, pandora_time_2))
        print("----- ", total / nr_runs)

    # with open('pandora_mqt_verification.csv', 'w') as f:
    #     writer = csv.writer(f)
    #     for row in times:
    #         writer.writerow(row)

    conn.close()

import csv

from mqt.qcec import verify

from qiskit import QuantumCircuit

from pandora.connection_util import *

import random

from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def generate_random_cnot_circuit(num_qubits=2, num_gates=8):
    """
    Generates a quantum circuit with a random CNOT gate.

    Args:
        num_qubits (int): The number of qubits in the circuit.
                          Must be at least 2 for a CNOT gate.
        num_gates (int): The number of gates in the circuit.

    Returns:
        QuantumCircuit: The generated Qiskit quantum circuit.
    """
    if num_qubits < 2:
        print("Warning: num_qubits must be at least 2 for a CNOT gate. Setting to 2.")
        num_qubits = 2

    # Create a quantum circuit with num_qubits quantum registers
    # and num_qubits classical registers (for measurement if needed)
    qc = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(num_gates):
        # Randomly select control and target qubits for the CNOT gate
        # Ensure control and target are different
        control_qubit = random.randint(0, num_qubits - 1)
        target_qubit = control_qubit
        while target_qubit == control_qubit:
            target_qubit = random.randint(0, num_qubits - 1)

        # Apply the CNOT (controlled-NOT) gate
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
    nr_cnots = concatenated.count_ops()['cx']
    print(nr_cnots)

    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection,
                            clean=True)
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

    if one_missing:
        cursor.execute(f"call cancel_two_qubit_bernoulli({CX}, {CX}, 0, 10, {nr_cnots - 1})")
    else:
        cursor.execute(f"call cancel_two_qubit_bernoulli({CX}, {CX}, 0, 10, {nr_cnots})")

    return time.time() - st_time


if __name__ == "__main__":
    conn = get_connection()
    times = []

    for q in range(10, 101, 10):
        for i in range(3):
            circ1 = generate_random_cnot_circuit(q, q ** 3)

            print(q, i, "correct ", end="")
            circ2 = circ1.copy()
            result_1 = verify(circ1, circ2)
            pandora_time_1 = pandora_verify(connection=conn,
                                            circ1=circ1,
                                            circ2=circ2)
            print('MQT: ', result_1.check_time)
            print('Pandora time: ', pandora_time_1)

            print(q, i, "wrong ", end="")
            circ2 = remove_random_gate(circ1)
            result_2 = verify(circ1, circ2)
            pandora_time_2 = pandora_verify(connection=conn,
                                            circ1=circ1,
                                            circ2=circ2,
                                            one_missing=True)
            print('MQT: ', result_2.check_time)
            print('Pandora time: ', pandora_time_2)

            times.append((q, i, result_1, pandora_time_1, result_2, pandora_time_2))

    with open('pandora_mqt_verification.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    conn.close()

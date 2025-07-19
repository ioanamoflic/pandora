import random
import sys
import time
import csv

import qiskit
from pytket import Circuit, OpType
from pytket._tket.passes import RemoveRedundancies

from pandora.connection_util import get_connection, drop_and_replace_tables, refresh_all_stored_procedures, \
    insert_in_batches, reset_database_id
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


def cx_to_hhcxhh_transform_append(circ: Circuit) -> Circuit:
    n_qubits = circ.n_qubits
    circ_prime = Circuit(n_qubits)  # Define a replacement circuit

    # The original gate count
    gate_list = list(circ.get_commands())
    gate_count_circ = len(gate_list)
    # The gate count for the new circuit
    gate_count_circ_prime = 0

    while gate_count_circ_prime <= 5 * gate_count_circ:
        random_position = random.randint(0, gate_count_circ - 1)
        cmd = gate_list[random_position]
        qubit_list = cmd.qubits

        if cmd.op.type == OpType.CX:
            gate_count_circ_prime += 5
            circ_prime.add_gate(OpType.H, qubit_list[0].index)
            circ_prime.add_gate(OpType.H, qubit_list[1].index)
            circ_prime.add_gate(OpType.CX, qubit_list[::-1])
            circ_prime.add_gate(OpType.H, qubit_list[0].index)
            circ_prime.add_gate(OpType.H, qubit_list[1].index)
        else:
            circ_prime.add_gate(cmd.op.type, cmd.op.params, qubit_list)

    return circ_prime


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


def cx_to_hhcxhh_transform_blocked(circ: Circuit, block_size=1000) -> Circuit:
    gate_list = list(circ.get_commands())
    gate_count_circ = len(gate_list)

    assert (gate_count_circ % block_size == 0)

    template = Circuit(2).H(0).H(1).CX(0, 1).H(0).H(1)
    gate_list_blocked = []
    i = 0
    while i < gate_count_circ:
        gate_block = []
        for j in range(block_size):
            gate_block.append(gate_list[i])
            i += 1
        gate_list_blocked.append(gate_block)

    n_blocks = len(gate_list_blocked)
    visited = [False] * gate_count_circ

    nr_success = 0
    while nr_success < gate_count_circ:
        cx_id = None
        while cx_id is None:
            random_block_id = random.randint(0, n_blocks - 1)
            block = gate_list_blocked[random_block_id]
            for cx in block:
                if not visited[int(cx.opgroup)]:
                    cx_id = int(cx.opgroup)
                    visited[cx_id] = True
                    break

        x = circ.substitute_named(template, str(cx_id))
        if x is True:
            nr_success += 1
    return circ


def z_to_hxh(circ: Circuit) -> Circuit:
    n_qubits = circ.n_qubits
    circ_prime = Circuit(n_qubits)  # Define a replacement circuit

    while len(circ_prime.get_commands()) <= 3 * len(circ.get_commands()):
        random_position = random.randint(0, len(circ.get_commands()) - 1)
        cmd = circ.get_commands()[random_position]
        qubit_list = cmd.qubits
        if cmd.op.type == OpType.Z:
            circ_prime.add_gate(OpType.H, qubit_list)
            circ_prime.add_gate(OpType.X, qubit_list)
            circ_prime.add_gate(OpType.H, qubit_list)
        else:
            circ_prime.add_gate(cmd.op.type, cmd.op.params, qubit_list)

    return circ_prime


def x_to_hzh(circ: Circuit) -> Circuit:
    n_qubits = circ.n_qubits
    circ_prime = Circuit(n_qubits)  # Define a replacement circuit

    while len(circ_prime.get_commands()) <= 3 * len(circ.get_commands()):
        random_position = random.randint(0, len(circ.get_commands()) - 1)
        cmd = circ.get_commands()[random_position]
        qubit_list = cmd.qubits
        if cmd.op.type == OpType.X:
            circ_prime.add_gate(OpType.H, qubit_list)
            circ_prime.add_gate(OpType.Z, qubit_list)
            circ_prime.add_gate(OpType.H, qubit_list)
        else:
            circ_prime.add_gate(cmd.op.type, cmd.op.params, qubit_list)

    return circ_prime


def test_cx_to_hhcxhh_bernoulli(connection,
                                initial_circuit: qiskit.QuantumCircuit,
                                repetitions: int,
                                bernoulli_percentage=10):
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

    cursor.execute(f"call linked_cx_to_hhcxhh_bernoulli({bernoulli_percentage}, {repetitions})")


if __name__ == "__main__":
    random.seed(0)

    n_CX = [1000, 10000, 100000, 1000000, 10000000]

    FILENAME = None
    EQUIV = 0
    BENCH = None
    conn = None

    if len(sys.argv) != 3:
        sys.exit(0)
    elif len(sys.argv) == 3:
        FILENAME = sys.argv[1]
        BENCH = sys.argv[2]

    if BENCH == 'pandora':
        conn = get_connection(config_file_path=FILENAME)
        print(f"Running config file {FILENAME}")

    times = []
    for cx_count in n_CX:
        print('Testing CX count:', cx_count)

        tket_circ, pandora_circ = generate_random_CX_circuit(n_templates=cx_count, n_qubits=50)

        if BENCH == 'pandora':
            start_time = time.time()
            test_cx_to_hhcxhh_bernoulli(connection=conn,
                                        initial_circuit=pandora_circ,
                                        repetitions=cx_count)
            op_time = time.time() - start_time
            print('Pandora time: ', op_time)
        else:
            start_time = time.time()
            tket_circ = cx_to_hhcxhh_transform_random(tket_circ)
            op_time = time.time() - start_time
            print('TKET time:', op_time)

        times.append((cx_count, op_time, BENCH))

    with open(f'{BENCH}_rma.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    if BENCH == 'pandora':
        conn.close()

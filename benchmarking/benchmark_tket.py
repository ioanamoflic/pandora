import random
import time
import csv
import pytket.passes
from pytket import Circuit, OpType
from pytket._tket.passes import RemoveRedundancies
from pytket.passes import CliffordSimp


def generate_random_CX_circuit(n_templates, n_qubits):
    circ = Circuit(n_qubits)
    for t in range(n_templates):
        q1, q2 = random.choices(range(0, n_qubits), k=2)
        while q1 == q2:
            q1, q2 = random.choices(range(0, n_qubits), k=2)

        circ.CX(q1, q2, opgroup=str(t))

    return circ


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


if __name__ == "__main__":

    n_CX = [1000, 10000, 100000, 1000000, 10000000]

    times = []
    for cx_count in n_CX:

        input_circ = generate_random_CX_circuit(n_templates=cx_count, n_qubits=50)
        start_time = time.time()
        print('cx count:', cx_count)
        circuit = cx_to_hhcxhh_transform_random(input_circ)
        # circuit = cx_to_hhcxhh_transform_append(input_circ)
        # circuit = cx_to_hhcxhh_transform_blocked(input_circ, block_size=n_t//10)
        print('time to optimize:', time.time() - start_time)

        times.append(time.time() - start_time)

    rows = zip(n_CX, times)
    with open('results/tket_random.csv', 'w') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

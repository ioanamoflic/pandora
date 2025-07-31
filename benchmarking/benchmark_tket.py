import random
import time
import csv

import qiskit
from pytket import Circuit
from pytket._tket.passes import RemoveRedundancies


def generate_random_CX_circuit(n_templates, n_qubits):
    circ_tket = Circuit(n_qubits)
    circ_qiskit = qiskit.QuantumCircuit(n_qubits, n_qubits)

    for t in range(n_templates):
        q1, q2 = random.choices(range(0, n_qubits), k=2)
        while q1 == q2:
            q1, q2 = random.choices(range(0, n_qubits), k=2)

        circ_tket.CX(q1, q2, opgroup=str(t))
        circ_qiskit.cx(q1, q2)

    return circ_tket, circ_qiskit


def generate_random_HH_circuit(n_templates, n_qubits):
    circ_tket = Circuit(n_qubits)
    circ_pandora = qiskit.QuantumCircuit(n_qubits, n_qubits)

    for t in range(n_templates):
        q1 = random.choice(range(0, n_qubits))

        circ_tket.H(qubit=q1)
        circ_tket.H(qubit=q1)

        circ_pandora.h(q1)
        circ_pandora.h(q1)

    return circ_tket, circ_pandora


def optimize_circuit(circuit):
    RemoveRedundancies().apply(circuit)
    return circuit.get_commands()


def get_random_seq_gates_from_circuit(circ: Circuit, percentage):
    for i, node in enumerate(circ.get_commands()):
        if random.uniform(0, 1) > percentage / 100:
            continue

        yield str(i)


def compute_best_possible_time(nr_nodes, nr_qubits):
    t = time.time()
    generate_random_CX_circuit(nr_nodes, nr_qubits)
    print("best possible TKET time", time.time() - t)


def cx_to_hhcxhh_transform_seq(circ: Circuit, nodes) -> Circuit:
    template = Circuit(2).H(0).H(1).CX(0, 1).H(0).H(1)

    for node_name in nodes:
        x = circ.substitute_named(template, node_name)

    return circ


if __name__ == "__main__":
    for nq in range(10000, 100001, 10000):
        tket_circ, _ = generate_random_CX_circuit(n_templates=nq,
                                                  n_qubits=50)

        start_time = time.time()

        nr_rewrite_passes = 100
        percent_rewrite_per_pass = 0.1
        for i in range(nr_rewrite_passes):
            cx_to_hhcxhh_transform_seq(tket_circ,
                                       get_random_seq_gates_from_circuit(tket_circ, percent_rewrite_per_pass))

        op_time = time.time() - start_time
        print('TKET_time: ', op_time)

        with open(f'TKET_template_search.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((nq, op_time))

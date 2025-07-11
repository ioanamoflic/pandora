import csv
import time
import random

from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate
from qiskit.converters import circuit_to_dag

from qiskit.dagcircuit import DAGCircuit
from qiskit.quantum_info import random_clifford


def cx_to_hhcxhh_transform_random(n_qub: int):
    qc = random_clifford(num_qubits=n_qub, seed=0).to_circuit()
    input_dag = circuit_to_dag(qc)

    random_nodes = input_dag.op_nodes()
    random.shuffle(random_nodes)

    random_CXs = [node for node in random_nodes if isinstance(node.op, CXGate)]

    def get_replacement():
        replacement = QuantumCircuit(2)
        replacement.h(0)
        replacement.h(1)

        replacement.cx(1, 0)

        replacement.h(0)
        replacement.h(1)

        return circuit_to_dag(replacement)

    start_time = time.time()

    for random_node in random_CXs:
        input_dag.substitute_node_with_dag(random_node, get_replacement())

    return time.time() - start_time


def cx_to_hhcxhh_transform_repeated(input_dag: DAGCircuit,
                                    repetitions: int):
    sample_percentage = 0.2

    total_sample_time = 0

    def get_replacement():
        replacement = QuantumCircuit(2)
        replacement.h(0)
        replacement.h(1)

        replacement.cx(0, 1)

        replacement.h(0)
        replacement.h(1)

        dag = circuit_to_dag(replacement)

        return dag

    start_time = time.time()

    for i in range(repetitions):
        all_node_ops = input_dag.op_nodes()

        cx_node = None
        while cx_node is None:
            local_time = time.time()
            sample = random.sample(all_node_ops, k=round(len(all_node_ops) * sample_percentage))
            total_sample_time = total_sample_time + time.time() - local_time

            cx_node = next(node for node in sample if isinstance(node.op, CXGate))

        input_dag.substitute_node_with_dag(cx_node, get_replacement())

    return (time.time() - start_time) - total_sample_time


if __name__ == "__main__":
    n_rep = [10, 100, 1000, 10000, 100000]

    times = []
    for repetitions in n_rep:
        print('N_qubits:', repetitions)

        # qc = random_clifford(num_qubits=1000, seed=0).to_circuit()
        # total_time = cx_to_hhcxhh_transform_repeated(circuit_to_dag(qc), repetitions=repetitions)

        total_time = cx_to_hhcxhh_transform_random(n_qub=repetitions)

        print('Time to optimize:', total_time)

        times.append(total_time)

    rows = zip(n_rep, times)

    with open('results/qiskit_repeated.csv', 'w') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

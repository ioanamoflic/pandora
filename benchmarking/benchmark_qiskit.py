import csv
import sys
import time
import random

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate

from qiskit.dagcircuit import DAGCircuit
from qiskit.quantum_info import random_clifford


def get_replacement():
    replacement = QuantumCircuit(2)

    replacement.h(0)
    replacement.h(1)
    replacement.cx(1, 0)
    replacement.h(0)
    replacement.h(1)

    dag = qiskit.converters.circuit_to_dag(replacement)

    return dag


def get_random_gate_from_dag_visit_once(op_nodes, visited, sample_size=100, gate_type=None):
    while True:
        # Bernoulli sampling of sample_size from the entire circuit
        sample_ind = random.sample(range(len(op_nodes)), k=sample_size)

        for node_ind in sample_ind:
            node = op_nodes[node_ind]

            # if cnot and not visited
            if visited[node] is False and isinstance(node.op, gate_type):
                visited[node] = True
                return node


def run_benchmark(input_dag: DAGCircuit,
                  sample_percentage=0.1,
                  nr_rewrites=10):
    op_nodes = input_dag.op_nodes()
    op_nodes_length = len(op_nodes)
    sample_size = round(op_nodes_length * sample_percentage)

    visit_dict = dict(zip(op_nodes, [False] * len(op_nodes)))

    search_times = []
    rewrite_times = []

    for i in range(nr_rewrites):
        t0 = time.time()

        cx_node = get_random_gate_from_dag_visit_once(op_nodes, visit_dict, sample_size, CXGate)

        t1 = time.time()

        replacement = get_replacement()
        input_dag.substitute_node_with_dag(cx_node, replacement)

        t2 = time.time()

        search_times.append(t1 - t0)
        rewrite_times.append(t2 - t1)

    return search_times, rewrite_times


"""
  Benchmarking Qiskit
"""

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(0)

    next_arg = 0

    N_QUB = int(sys.argv[next_arg + 1])
    RATIO = int(sys.argv[next_arg + 2])

    print(f'Benchmark for ... N_QUB = {N_QUB} and RATIO = {RATIO}')

    times = []

    qc = random_clifford(num_qubits=N_QUB, seed=0).to_circuit()
    qc_dag = qiskit.converters.circuit_to_dag(qc)
    nr_cnots = qc.count_ops()['cx']

    total_times = run_benchmark(qc_dag,
                                sample_percentage=0.1,
                                nr_rewrites=nr_cnots // RATIO)
    # Merge the times
    total_search = sum(total_times[0])
    total_rewrite = sum(total_times[1])

    print('Time to optimize S+R=T:', total_search, total_rewrite, total_search + total_rewrite, flush=True)

    times.append((N_QUB, RATIO, total_search, total_rewrite))

    with open('qiskit_cx_flip.csv', 'a') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

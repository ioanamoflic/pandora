import csv
import time
import random

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit.library import HGate

from qiskit.dagcircuit import DAGCircuit
from qiskit.quantum_info import random_clifford


def get_replacement_hh():
    replacement = QuantumCircuit(1)

    replacement.h(0)
    replacement.h(0)

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


def replace_h_with_hh_all(input_dag):
    """
    Replace all H gates with HH.
    """
    op_nodes = input_dag.op_nodes()
    for node in op_nodes:
        if isinstance(node.op, HGate):
            replacement = get_replacement_hh()
            input_dag.substitute_node_with_dag(node, replacement)

    return input_dag


def find_hh_pair(input_dag, visit_dict, sample_size):
    op_nodes = input_dag.op_nodes()
    while True:
        h_node = get_random_gate_from_dag_visit_once(op_nodes, visit_dict, sample_size, HGate)

        if h_node is not None:
            left_h = list(input_dag.predecessors(h_node))[0]
            if left_h is not None and not isinstance(left_h, qiskit._accelerate.circuit.DAGInNode) \
                    and isinstance(left_h.op, HGate):
                return left_h, h_node
            right_h = list(input_dag.successors(h_node))[0]
            if right_h is not None and isinstance(right_h.op, HGate):
                return h_node, right_h


def run_benchmark(input_dag: DAGCircuit,
                  sample_percentage=0.1,
                  nr_rewrites=10):

    # replace all H with HH
    input_dag = replace_h_with_hh_all(input_dag=input_dag)

    op_nodes = input_dag.op_nodes()
    op_nodes_length = len(op_nodes)
    sample_size = round(op_nodes_length * sample_percentage)

    visit_dict = dict(zip(op_nodes, [False] * len(op_nodes)))

    search_times = []
    rewrite_times = []

    for i in range(nr_rewrites):
        t0 = time.time()

        h_left, h_right = find_hh_pair(input_dag=input_dag,
                                       visit_dict=visit_dict,
                                       sample_size=sample_size)

        assert isinstance(h_left.op, HGate) and isinstance(h_right.op, HGate)

        visit_dict[h_left] = True
        visit_dict[h_right] = True

        t1 = time.time()

        input_dag.remove_op_node(h_left)
        input_dag.remove_op_node(h_right)

        t2 = time.time()

        search_times.append(t1 - t0)
        rewrite_times.append(t2 - t1)

    return search_times, rewrite_times


"""
  Benchmarking Qiskit
"""

if __name__ == "__main__":
    n_qubits = [10, 100, 1000]
    n_ratios = [8, 4, 2, 1]

    times = []
    for qubits in n_qubits:
        print('N_qubits...', qubits)

        qc = random_clifford(num_qubits=qubits, seed=0).to_circuit()
        qc_dag = qiskit.converters.circuit_to_dag(qc)
        nr_hadamards = qc.count_ops()['h']

        rtimes = []
        for ratio in n_ratios:
            print('Ratio... ', ratio)

            total_times = run_benchmark(qc_dag,
                                        sample_percentage=0.1,
                                        nr_rewrites=nr_hadamards // ratio)
            # Merge the times
            total_search = sum(total_times[0])
            total_rewrite = sum(total_times[1])

            print('Time to optimize S+R=T:', total_search, total_rewrite, total_search + total_rewrite, flush=True)

            times.append((qubits, ratio, total_search, total_rewrite))

    with open('qiskit_hh_removal.csv', 'w') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

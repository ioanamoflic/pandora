import csv
import time
import random

from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGCircuit

from benchmark_tket import generate_random_CX_circuit


def get_replacement():
    replacement = QuantumCircuit(2)

    replacement.h(0)
    replacement.h(1)
    replacement.cx(1, 0)
    replacement.h(0)
    replacement.h(1)

    dag = circuit_to_dag(replacement)

    return dag


def get_random_seq_gates_from_circuit(op_nodes, percentage):
    """
        Assume that the search criteria is randomly true in sample_size of the circuit
        Get the nodes in sequential order
    """
    sample_size = int(len(op_nodes) * percentage)
    sample_ind = random.sample(range(len(op_nodes)), k=sample_size)

    for node_ind in sample_ind:
        node = op_nodes[node_ind]
        if isinstance(node.op, CXGate):
            yield node


def get_random_gate_from_dag_visit_once(op_nodes, visited, sample_size=100, gate_type=None):
    while True:
        # Bernoulli sampling of sample_size from the entire circuit
        sample_ind = list(random.sample(range(len(op_nodes)), k=sample_size))
        sample_ind.sort()

        for node_ind in sample_ind:
            node = op_nodes[node_ind]

            # if cnot and not visited
            if visited[node] is False and isinstance(node.op, gate_type):
                visited[node] = True
                return node


def run_benchmark_seq(input_dag: DAGCircuit, sample_percentage=0.1, nr_passes=1):
    print(".")

    search_times = []
    rewrite_times = []

    for pass_i in range(nr_passes):

        t0 = time.time()
        # nodes = get_random_seq_gates_from_circuit(input_dag.op_nodes(), sample_percentage)
        t1 = time.time()

        # random.shuffle(nodes)
        replacement = get_replacement()
        for node in get_random_seq_gates_from_circuit(input_dag.op_nodes(), sample_percentage):
            input_dag.substitute_node_with_dag(node, replacement)

        t2 = time.time()

        search_times.append(t1 - t0)
        rewrite_times.append(t2 - t1)

    return search_times, rewrite_times


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
    for nq in range(100000, 1000001, 100000):
        print('Number of qubits:', nq)
        _, qc = generate_random_CX_circuit(n_templates=nq, n_qubits=50)

        qc_dag = circuit_to_dag(qc)

        total_times = run_benchmark_seq(qc_dag, sample_percentage=0.001, nr_passes=100)

        total_search = sum(total_times[0])
        total_rewrite = sum(total_times[1])

        print('Time to optimize S+R=T:', total_search, total_rewrite, total_search + total_rewrite, flush=True)

        with open('qiskit_template_search.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((nq, total_search, total_rewrite))

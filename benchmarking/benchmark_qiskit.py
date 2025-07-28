import csv
import sys
import time
import random

from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate, HGate
from qiskit.converters import circuit_to_dag

from benchmark_tket import generate_random_CX_circuit, generate_random_HHCXHH_circuit, get_replacement, \
    generate_random_HHCXHH_circuit_occasionally_flipped


def get_replacement_2():
    replacement = QuantumCircuit(2)

    replacement.cx(1, 0)

    dag = circuit_to_dag(replacement)

    return dag


def get_random_seq_gates_from_circuit(op_nodes, percentage, visited):
    """
        Assume that the search criteria is randomly true in sample_size of the circuit
        Get the nodes in sequential order
    """
    sample_size = int(len(op_nodes) * (percentage / 100))
    sample_ind = random.sample(range(len(op_nodes)), k=sample_size)
    sample_ind.sort()

    for node_ind in sample_ind:
        node = op_nodes[node_ind]
        if node in visited.keys() and visited[node] is False and isinstance(node.op, CXGate):
            visited[node] = True
            yield node


def is_hhcxhh_template(possibly_cx_node, circuit_dag):
    # if isinstance(possibly_cx_node, CXGate):
    pred = list(circuit_dag.predecessors(possibly_cx_node))
    succ = list(circuit_dag.successors(possibly_cx_node))

    if isinstance(pred[0].op, HGate) and isinstance(pred[1].op, HGate) \
            and isinstance(succ[0].op, HGate) and isinstance(succ[1].op, HGate):
        return pred[0], pred[1], succ[0], succ[1]

    return None


"""
  Benchmarking Qiskit
"""

if __name__ == "__main__":
    DIR = int(sys.argv[1])

    nr_passes = 1
    sample_percentage = 0.1

    for nq in range(100000, 1000001, 100000):
        print(f'Number of qubits: {nq} for {nr_passes} passes and {sample_percentage} probability')

        if DIR == 0:
            _, qc = generate_random_CX_circuit(n_templates=nq, n_qubits=50)
        else:
            # _, qc = generate_random_HHCXHH_circuit(n_templates=nq, n_qubits=50)
            qc = generate_random_HHCXHH_circuit_occasionally_flipped(n_templates=nq, n_qubits=50, proba=0.9)

        qc_dag = circuit_to_dag(qc)
        op_nodes = qc_dag.op_nodes()
        op_nodes_length = len(op_nodes)
        visit_dict = dict(zip(op_nodes, [False] * len(op_nodes)))

        search_times = []
        rewrite_times = []

        for pass_i in range(nr_passes):

            t0 = time.time()
            # nodes = get_random_seq_gates_from_circuit(input_dag.op_nodes(), sample_percentage)
            t1 = time.time()

            # random.shuffle(nodes)

            if DIR == 0:
                replacement = get_replacement()
                for node in get_random_seq_gates_from_circuit(qc_dag.op_nodes(), sample_percentage, visit_dict):
                    qc_dag.substitute_node_with_dag(node, replacement)
            else:
                replacement_2 = get_replacement_2()
                # for node in get_random_seq_gates_from_circuit(qc_dag.op_nodes(), sample_percentage, visit_dict):
                for node in op_nodes:
                    if isinstance(node, CXGate):
                        ret = is_hhcxhh_template(node, qc_dag)
                        if ret:
                            (h1, h2, h3, h4) = ret
                            qc_dag.remove_op_node(h1)
                            qc_dag.remove_op_node(h2)
                            qc_dag.remove_op_node(h3)
                            qc_dag.remove_op_node(h4)

                            qc_dag.substitute_node_with_dag(node, replacement_2)

            t2 = time.time()

            search_times.append(t1 - t0)
            rewrite_times.append(t2 - t1)

        total_search = sum(search_times)
        total_rewrite = sum(rewrite_times)

        print('Time to optimize S+R=T:', total_search, total_rewrite, total_search + total_rewrite, flush=True)

        with open('qiskit_template_search_random_flip.csv', 'a') as f:
            writer = csv.writer(f)
            writer.writerow((nq, total_search, total_rewrite, DIR))

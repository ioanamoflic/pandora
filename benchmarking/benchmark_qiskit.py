import csv
import random
import sys
import time

from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate, HGate
from qiskit.converters import circuit_to_dag
from qiskit.dagcircuit import DAGOpNode

from benchmark_tket import (
    generate_random_CX_circuit,
    generate_random_HHCXHH_circuit_occasionally_flipped,
    get_replacement_hhcxhh,
)


def get_cx_replacement_dag():
    circuit = QuantumCircuit(2)
    circuit.cx(1, 0)
    return circuit_to_dag(circuit)


def sample_cx_nodes_in_order(op_nodes, percentage, visited):
    """
    Sample a percentage of CX nodes and yield them in circuit order.
    """
    sample_size = int(len(op_nodes) * (percentage / 100))
    if sample_size == 0:
        return

    sampled_indices = sorted(random.sample(range(len(op_nodes)), k=sample_size))

    for idx in sampled_indices:
        node = op_nodes[idx]
        if isinstance(node, DAGOpNode) and isinstance(node.op, CXGate):
            if visited.get(node) is False:
                visited[node] = True
                yield node


def match_hhcxhh_template(cx_node, dag):
    """
    Check whether a CX node is surrounded by four H gates in the HH-CX-HH pattern.
    Returns the matching predecessor/successor H nodes if found.
    """
    if not isinstance(cx_node, DAGOpNode) or not isinstance(cx_node.op, CXGate):
        return None

    preds = list(dag.predecessors(cx_node))
    succs = list(dag.successors(cx_node))

    if len(preds) < 2 or len(succs) < 2:
        return None

    if all(isinstance(n, DAGOpNode) for n in preds[:2] + succs[:2]) and \
       all(isinstance(n.op, HGate) for n in preds[:2] + succs[:2]):
        return preds[0], preds[1], succs[0], succs[1]

    return None


def rewrite_hhcxhh_to_cx(dag, cx_node, h_nodes, replacement_dag):
    """
    Remove the four surrounding H gates and replace the CX node with the replacement DAG.
    """
    h1, h2, h3, h4 = h_nodes
    dag.remove_op_node(h1)
    dag.remove_op_node(h2)
    dag.remove_op_node(h3)
    dag.remove_op_node(h4)
    dag.substitute_node_with_dag(cx_node, replacement_dag)


def run_cx_to_hhcxhh_pass(dag, sample_percentage):
    """
    Randomly replace a sample of CX gates with HH-CX-HH.
    """
    op_nodes = dag.op_nodes()
    visited = {node: False for node in op_nodes}
    replacement_dag = get_replacement_hhcxhh()

    for node in sample_cx_nodes_in_order(op_nodes, sample_percentage, visited):
        dag.substitute_node_with_dag(node, replacement_dag)


def run_hhcxhh_to_cx_pass(dag):
    """
    Replace every HH-CX-HH template with a reversed CX.
    """
    replacement_dag = get_cx_replacement_dag()

    for node in list(dag.op_nodes()):
        match = match_hhcxhh_template(node, dag)
        if match is not None:
            rewrite_hhcxhh_to_cx(dag, node, match, replacement_dag)


def generate_benchmark_circuit(direction, n_templates, n_qubits, sample_percentage):
    """
    direction == 0: start from CX-only circuit
    direction != 0: start from HH-CX-HH circuit with occasional flips
    """
    if direction == 0:
        _, circuit = generate_random_CX_circuit(
            n_templates=n_templates,
            n_qubits=n_qubits,
        )
    else:
        _, circuit = generate_random_HHCXHH_circuit_occasionally_flipped(
            n_templates=n_templates,
            n_qubits=n_qubits,
            proba=sample_percentage / 100,
        )

    return circuit


def benchmark_rewrite(direction, n_templates, n_qubits, nr_passes, sample_percentage):
    circuit = generate_benchmark_circuit(
        direction=direction,
        n_templates=n_templates,
        n_qubits=n_qubits,
        sample_percentage=sample_percentage,
    )

    dag = circuit_to_dag(circuit)
    rewrite_times = []

    for _ in range(nr_passes):
        start = time.time()

        if direction == 0:
            run_cx_to_hhcxhh_pass(dag, sample_percentage)
        else:
            run_hhcxhh_to_cx_pass(dag)

        rewrite_times.append(time.time() - start)

    return sum(rewrite_times)


def append_result(csv_path, n_templates, total_time, sample_percentage):
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow((n_templates, total_time, sample_percentage))


def main():
    if len(sys.argv) != 2:
        sys.exit(0)

    direction = int(sys.argv[1])

    nr_passes = 1
    n_qubits = 50
    
    for sample_percentage in [0.1, 1, 10]:
        
        out_file = f"qiskit_template_search_random_flip_{sample_percentage}.csv"

        for n_templates in range(10_000, 100_001, 10_000):
            print(
                f"Number of templates: {n_templates} "
                f"for {nr_passes} passes and {sample_percentage} probability"
            )

            total_rewrite_time = benchmark_rewrite(
                direction=direction,
                n_templates=n_templates,
                n_qubits=n_qubits,
                nr_passes=nr_passes,
                sample_percentage=sample_percentage,
            )

            print("Time to rewrite:", total_rewrite_time, flush=True)

            append_result(
                csv_path=out_file,
                n_templates=n_templates,
                total_time=total_rewrite_time,
                sample_percentage=sample_percentage,
            )


if __name__ == "__main__":
    main()

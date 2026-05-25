import itertools
import math

import cirq
from qiskit import QuantumCircuit


def assert_same_up_to_qubit_permutation(expected: cirq.Circuit, actual: cirq.Circuit):
    """
    Obviously this has horrendous time complexity.
    """
    expected_qubits = sorted(expected.all_qubits())
    actual_qubits = sorted(actual.all_qubits())

    assert len(expected_qubits) == len(actual_qubits), (
        f"Different qubit counts: {len(expected_qubits)} != {len(actual_qubits)}"
    )

    for perm in itertools.permutations(actual_qubits):
        qubit_map = dict(zip(perm, expected_qubits))
        remapped = actual.transform_qubits(qubit_map)
        try:
            cirq.testing.assert_same_circuits(expected, remapped)
            return
        except AssertionError:
            pass

    raise AssertionError("Circuits are not equal up to qubit permutation")


def assert_logically_equivalent_up_to_qubit_permutation(
    expected: cirq.Circuit,
    actual: cirq.Circuit,
):
    """
    Obviously this has horrendous time complexity.
    """
    expected_qubits = list(sorted(expected.all_qubits(), key=str))
    actual_qubits = list(sorted(actual.all_qubits(), key=str))

    assert len(expected_qubits) == len(actual_qubits), (
        f"Different qubit counts: {len(expected_qubits)} != {len(actual_qubits)}"
    )

    expected_u = expected.unitary()

    for perm in itertools.permutations(actual_qubits):
        qubit_map = dict(zip(perm, expected_qubits))
        remapped = actual.transform_qubits(qubit_map)

        if cirq.linalg.allclose_up_to_global_phase(expected_u, remapped.unitary()):
            return

    raise AssertionError("Circuits are not logically equivalent up to qubit permutation")


def count_t_gates(circuit, tol=1e-8):
    def is_t_like(op):
        # Only care about Z rotations
        if not isinstance(op.gate, cirq.ZPowGate):
            return False

        # Normalize exponent into [0, 1)
        exp = op.gate.exponent % 1

        # T = 1/4, T† = 3/4 (mod 1)
        return (
                math.isclose(exp, 0.25, abs_tol=tol) or
                math.isclose(exp, 0.75, abs_tol=tol)
        )

    return sum(
        1
        for moment in circuit
        for op in moment
        if is_t_like(op)
    )


def permute_qiskit_circuit(circuit: QuantumCircuit, permutation) -> QuantumCircuit:
    new_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

    old_to_new = {
        circuit.qubits[old_idx]: new_circuit.qubits[new_idx]
        for new_idx, old_idx in enumerate(permutation)
    }
    old_clbit_to_new = {
        circuit.clbits[i]: new_circuit.clbits[i]
        for i in range(circuit.num_clbits)
    }

    for inst in circuit.data:
        new_qargs = [old_to_new[q] for q in inst.qubits]
        new_cargs = [old_clbit_to_new[c] for c in inst.clbits]
        new_circuit.append(inst.operation, new_qargs, new_cargs)

    return new_circuit


def assert_same_up_to_qubit_permutation_qiskit(
    expected: QuantumCircuit,
    actual: QuantumCircuit,
):
    """
    Obviously this has horrendous time complexity.
    """
    assert expected.num_qubits == actual.num_qubits, (
        f"Different qubit counts: {expected.num_qubits} != {actual.num_qubits}"
    )
    assert expected.num_clbits == actual.num_clbits, (
        f"Different clbit counts: {expected.num_clbits} != {actual.num_clbits}"
    )

    n = actual.num_qubits

    for permutation in itertools.permutations(range(n)):
        remapped = permute_qiskit_circuit(actual, permutation)

        if expected == remapped:
            return

    raise AssertionError("Circuits are not equal up to qubit permutation")

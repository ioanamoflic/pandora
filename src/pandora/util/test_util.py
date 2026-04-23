import itertools
import math

import cirq


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
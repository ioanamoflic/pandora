'''
    Tests for the Repeat Bloq
'''
import types
import unittest

import cirq
from qualtran import CompositeBloq
from pyLIQTR.utils.repeat import Repeat
from pyLIQTR.utils.repeat import circuit_to_quregs

from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pyLIQTR.utils.tests.test_helpers import TestHelpers, extract_and_run_tests


class TestRepeatBloq(unittest.TestCase, TestHelpers):
    '''
        Tests for the Repeat Bloq
    '''

    @staticmethod
    def generate_circuit(
            *,
            n_repetitions: int = 1,
            n_qubits: int = 2
    ) -> cirq.Circuit:
        '''
        Generates a simple circuit to test on
        '''
        circ = cirq.Circuit()
        q = [cirq.LineQubit(i) for i in range(n_qubits)]

        for _ in range(n_repetitions):
            for i in range(n_qubits - 1):
                circ.append(cirq.H(q[i]))
                circ.append(cirq.CNOT(q[i], q[i + 1]))

        return circ

    def test_bloq(self, n_qubits: int = 5, n_repetitions: int = 7):
        '''
            Tests wrapping a CompositeBloq in a Repeat
        '''

        circ = self.generate_circuit(n_qubits=n_qubits)
        repeated_circuit = self.generate_circuit(
            n_repetitions=n_repetitions,
            n_qubits=n_qubits
        )

        quregs = circuit_to_quregs(circ)
        bloq = CompositeBloq.from_cirq_circuit(circ)
        repeat_bloq = Repeat(
            bloq,
            n_repetitions=n_repetitions,
            cirq_quregs=quregs
        )

        # Test generator_decompose and circuit_decompose_multi
        assert self.generator_commutative_equality(
            repeated_circuit,
            repeat_bloq
        )
        assert self.circuit_equality(
            repeated_circuit,
            repeat_bloq
        )

    def test_gate(self, n_repetitions: int = 9):
        '''
            Tests wrapping a gate in a Repeat
        '''

        gate = cirq.X
        qubits = cirq.GridQubit.square(2)

        op = gate(qubits[0])

        repeat_bloq = Repeat(
            gate,
            qubits[0],
            n_repetitions=n_repetitions
        )

        repeated_circuit = cirq.Circuit()
        for _ in range(n_repetitions):
            repeated_circuit.append(op)

        # Test generator_decompose and circuit_decompose_multi
        for generated_op in generator_decompose(repeat_bloq):
            assert op == generated_op
        assert self.circuit_equality(repeated_circuit, repeat_bloq)

    def test_circuit(self, n_repetitions: int = 2, n_qubits: int = 3):
        '''
            Test wrapping a cirq.Circuit in a Repeat
        '''

        # Single instance of the circuit
        circ = self.generate_circuit(n_qubits=n_qubits)

        # Baseline repeated circuit to test against
        repeated_circuit = self.generate_circuit(
            n_repetitions=n_repetitions,
            n_qubits=n_qubits
        )

        # Repeated circuit representation
        repeat_bloq = Repeat(circ, n_repetitions=n_repetitions)

        # Test generator_decompose and circuit_decompose_multi
        assert self.generator_commutative_equality(
            repeated_circuit,
            repeat_bloq
        )
        assert self.circuit_equality(
            repeated_circuit,
            repeat_bloq
        )


# Test runner without invoking subprocesses
# Used for interactive and pdb hooks
if __name__ == '__main__':
    extract_and_run_tests(TestRepeatBloq())

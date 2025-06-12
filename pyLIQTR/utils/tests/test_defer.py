'''
    Tests for the Deferred Bloq
'''
import types
import unittest

from functools import partial

import cirq
from qualtran import CompositeBloq
from pyLIQTR.utils.deferred import Deferred
from pyLIQTR.utils.repeat import circuit_to_quregs

from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pyLIQTR.utils.tests.test_helpers import TestHelpers, extract_and_run_tests

from qualtran.bloqs.basic_gates import CNOT, Hadamard
from qualtran import BloqBuilder


class TestDeferredBloq(unittest.TestCase, TestHelpers):
    '''
        Tests for the Deferred Bloq
        Delays instantiation of sub-bloq's initialisers
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

    def test_cirq_unary_gate(self, n_qubits=10):

        q = [cirq.LineQubit(i) for i in range(n_qubits)]
        target_gate = cirq.H

        for i in range(n_qubits):
            gate = Deferred(target_gate, q[i])
            assert next(gate.compose()) == target_gate(q[i])

    def test_cirq_binary_gate(self, n_qubits=10):
        '''
            Tests multiple arguments
        '''
        q = [cirq.LineQubit(i) for i in range(n_qubits)]
        target_gate = cirq.CNOT

        for i in range(n_qubits - 1):
            gate = Deferred(target_gate, q[i], q[i + 1])
            assert next(gate.compose()) == target_gate(q[i], q[i] + 1)

    def test_composite_bloq(self, n_qubits=10, seed=0):
        '''
            Tests deferring a bloq
        '''
        bloqs = [Hadamard()] * 5 + [CNOT()] * 5
        cbloq = TestHelpers.randomly_compose_bloqs(n_qubits, *bloqs, seed=seed)

        bloqs_deferred = [Hadamard()] * 5 + [CNOT()] * 5
        cbloq_deferred = TestHelpers.randomly_compose_bloqs(n_qubits, *bloqs, seed=seed)

        for bloq, d_bloq in zip(
                circuit_decompose_multi(cbloq, 1),
                circuit_decompose_multi(cbloq, 1),
        ):
            assert bloq == d_bloq


# Test runner without invoking subprocesses
# Used for interactive and pdb hooks
if __name__ == '__main__':
    extract_and_run_tests(TestDeferredBloq())

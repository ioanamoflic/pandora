'''
    Tests for the Deferred Bloq
'''
import types
import unittest

from functools import partial

import cirq
from qualtran import CompositeBloq
from pyLIQTR.utils.deferred import Cached
from pyLIQTR.utils.repeat import circuit_to_quregs

from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pyLIQTR.utils.tests.test_helpers import TestHelpers, extract_and_run_tests

from qualtran.bloqs.basic_gates import CNOT, Hadamard
from qualtran import BloqBuilder


class TestDeferredBloq(unittest.TestCase, TestHelpers):
    '''
        Tests for the Deferred Bloq
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

    @staticmethod
    def generate_bloqs(
            *,
            n_repetitions: int = 1,
            n_qubits: int = 2
    ) -> None:

        CX = CNOT()
        H = Hadamard()

        bb = BloqBuilder()

        qubits = [
            bb.add_register(f'q{i}', 1)
            for i in range(n_qubits)
        ]

        for _ in range(n_repetitions):
            for i in range(n_qubits - 1):
                qubits[i] = bb.add(H, q=qubits[i])
                qubits[i], qubits[i + 1] = bb.add(CX, ctrl=qubits[i], target=qubits[i + 1])
        cbloq = bb.finalize(**{f'q{i}': qubits[i] for i in range(len(qubits))})
        return cbloq

    def test_cirq_unary_gate(self, n_qubits=10):

        q = [cirq.LineQubit(i) for i in range(n_qubits)]
        target_gate = cirq.H

        gate = Cached('tag', target_gate, q[0])
        assert next(gate.compose()) == target_gate(q[0])

        # Tag is already set, the cache should return a non-0 qubit object here
        for i in range(1, n_qubits):
            assert not (next(gate.compose()) == target_gate(q[i]))

        # Tag is already set, the cache should return a non-0 qubit object here
        for i in range(1, n_qubits):
            gate = Cached(f'tag_{i}', target_gate, q[0])

            assert not (next(gate.compose()) == target_gate(q[i]))

        #    def test_cirq_binary_gate(self, n_qubits=10):
        #        '''
        #            Tests multiple arguments
        #        '''
        #        q = [cirq.LineQubit(i) for i in range(n_qubits)]
        #        target_gate = cirq.CNOT
        #
        #        for i in range(n_qubits - 1):
        #            gate = Cached('tag', target_gate, q[i], q[i + 1])
        #            assert next(gate.compose()) == target_gate(q[i], q[i] + 1)
        #
        #    def test_bloq(self, n_qubits=10):
        '''
            Tries to add deferred gates to a larger bloq
        '''
        # TODO: Generic kwargs for qubit arguments
        # CX = CNOT()
        # bb = BloqBuilder()

        # qubits = [
        #    bb.add_register(f'q{i}', 1)
        #    for i in range(n_qubits)
        # ]
        #
        # for _ in range(n_repetitions):
        #    for i in range(n_qubits - 1):
        #        qubits[i] = bb.add(Deferred(H, qubits[i]), q=qubits[i])

        #        qubits[i] = bb.add(Deferred(H, qubits[i + 1]), q=qubits[:])

        #        qubits[i], qubits[i + 1] = bb.add(CX, ctrl=qubits[i], target=qubits[i + 1])

        # cbloq=bb.finalize(**{f'q{i}':qubits[i] for i in range(len(qubits))})


# Test runner without invoking subprocesses
# Used for interactive and pdb hooks
if __name__ == '__main__':
    extract_and_run_tests(TestDeferredBloq())

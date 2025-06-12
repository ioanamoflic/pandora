'''
    Common helper methods for tests
'''

import types
import typing
import unittest

import numpy
import cirq
from qualtran import CompositeBloq, BloqBuilder
from qualtran._infra.gate_with_registers import GateWithRegisters

from pyLIQTR.utils.meta import MetaBloq
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
from pyLIQTR.utils.circuit_decomposition import generator_decompose


def extract_and_run_tests(tst: unittest.TestCase):
    '''
        Test runner without invoking subprocesses
    '''
    # Extract test functions from tst object
    for prop in dir(tst):
        if prop[:4] == 'test':
            obj = getattr(tst, prop)
            if issubclass(type(obj), types.MethodType):
                obj()


class TestHelpers():
    '''
        Class containing static methods for comparisons between decomposed
        bloqs and circuits
    '''

    @staticmethod
    def consume(iterable: typing.Iterable):
        '''
            Forces evaluation of all elements in an iterable
            Useful for stateful map operations without allocating memory
        '''
        for _ in iterable:
            pass

    @staticmethod
    def non_empty(iterable: typing.Iterable) -> bool:
        try:
            next(iterable)
            return True
        except StopIteration:
            return False

    @staticmethod
    def generator_equality(
            circuit: cirq.Circuit,
            bloq: CompositeBloq
    ) -> bool:
        '''
            Tests equality for generator decompose
        '''
        # Test that the bloq is not empty
        assert TestHelpers.non_empty(generator_decompose(bloq))

        # Test that all decomposition objects match
        return all(
            map(
                lambda x: x[0] == x[1],
                zip(
                    generator_decompose(bloq),
                    generator_decompose(circuit)
                )
            )
        )

    @staticmethod
    def circuit_equality(
            circuit: cirq.Circuit,
            bloq: CompositeBloq,
            decomp: int = 1
    ) -> bool:
        '''
            Tests circuits for equality, moment by moment
            :: circuit : cirq.Circuit :: Repeated Circuit Object
            :: bloq : Repeat :: Repeating Bloq Object
            :: decomp : int :: Number of decompositions for the decomp_multi
        '''
        # Test that the bloq is not empty
        assert TestHelpers.non_empty(iter(circuit_decompose_multi(bloq, decomp)))

        # Test that all decomposition objects match
        return all(
            map(
                lambda x: x[0] == x[1],
                zip(
                    circuit,
                    circuit_decompose_multi(bloq, decomp)
                )
            )
        )

    @staticmethod
    def generator_commutative_equality(
            circuit: cirq.Circuit,
            bloq: CompositeBloq
    ) -> bool:
        '''
            Tests equality for generator decompose
            This resolves issues where the gates are out of order but commute
            :: circuit : cirq.Circuit :: Repeated Circuit Object
            :: bloq : Repeat :: Repeating Bloq Object
        '''

        # Test that the bloq is not empty
        assert TestHelpers.non_empty(generator_decompose(bloq))

        backlog = []
        # Tracks the iterator for the decomposition of the circuit
        gen = generator_decompose(circuit)

        # Tracks the iterator for the decomposition of the repeating bloq
        # Not the happiest with the amount of GOTO-like structures here;
        # Python for loops lack grace
        for bloq_gate in generator_decompose(bloq):

            qubits = bloq_gate.qubits
            found = False

            # First check any backlogged gates
            for cmp in backlog:
                if any(i in cmp.qubits for i in qubits):
                    # Gate resolution is out of order, bail
                    if cmp != bloq_gate:
                        return False
                    found = cmp
                    break

            # Gate was in commutative order in the backlog, continue
            if found is not False:
                backlog.remove(found)
                continue

            # Gate was not in the backlog
            # Traverse the generator until we find the appropriate gate
            for cmp in gen:

                # Gate resolution is out of order, bail
                if any(i in cmp.qubits for i in qubits):
                    if cmp != bloq_gate:
                        return False
                    found = True
                    break

                # Append non-matching gates to the backlog
                backlog.append(cmp)

            if not found:
                return False

        # All gates were matched in order
        return True

    @staticmethod
    def randomly_compose_bloqs(
            n_registers: int,
            *bloqs,
            seed: int = None
    ) -> "CompositeBloq":
        '''
            Composes a collection of bloqs
            Joins edges at random
            :: n_registers : int :: Number of registers
            :: *bloqs :: Ordered list of bloqs to compose
            :: seed = None : int :: prng seed
            Returns a composite bloq object
        '''

        # seed=None is the default argument in the generator constructor

        class RandomBloq(MetaBloq):

            # Simple gate
            gate = None

            def __init__(self, *args, seed=None, **kwargs):
                self.seed = seed

            def compose(self, *args, **kwargs):
                generator = numpy.random.default_rng(seed=seed)
                yield from bloqs

            def build_composite_bloq(self, bb, soqs):

                generator = numpy.random.default_rng(seed=seed)

                # List of registers
                regs = [i for i in soqs.values()]
                n_registers = len(regs)

                # Index listing of registers, useful for indirection later
                indices = list(range(n_registers))

                for bloq in bloqs:
                    # Number of arguments for this bloq
                    n_args = sum(map(lambda x: 1, bloq.signature.lefts()))
                    if n_args > n_registers:
                        raise IndexError('Too few registers for this circuit')

                        # Random indices
                    args_idx = generator.choice(indices, size=n_args, replace=False)

                    # Bind indices to signature arguments
                    args = {sig.name: regs[i] for sig, i in zip(bloq.signature.lefts(), args_idx)}

                    # Add the bloq
                    # Because the behaviour of add varies with the number of arguments
                    # This is necessary to catch non-iterable single qubit gates
                    if n_args == 1:
                        updated_regs = (bb.add(bloq, **args),)
                    else:
                        updated_regs = bb.add(bloq, **args)

                        # Update regs
                    # It would be good to confirm how order is preserved with kwargs
                    # being unordered but regs being ordered
                    TestHelpers.consume(
                        map(
                            lambda x: regs.__setitem__(x[0], x[1]),
                            zip(args_idx, updated_regs)
                        )
                    )

                cbloq = bb.finalize(**{f'q{i}': j for i, j in enumerate(regs)})
                return soqs

        return RandomBloq(seed=seed)

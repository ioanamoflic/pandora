'''
    meta_bloq.py
    Base class for bloqs with meta compositions
'''
from typing import Dict, Iterator, Generator
from numpy.typing import NDArray

import cirq
import qualtran
from qualtran._infra.gate_with_registers import GateWithRegisters
from qualtran._infra.registers import Signature


class MetaBloq(GateWithRegisters):
    '''
        Meta Bloq Tag
        Abstract bloq for meta instructions
    '''
    @property
    def signature(self) -> Signature:
        '''
            Signature is instantiated after resolution
        '''

    def compose(self, *args, **kwargs) -> Generator[
            qualtran.Bloq | cirq.Gate | cirq.Circuit,
            None,
            None
            ]:
        '''
            Internal composition function for overloading by derived classes
        '''
        raise NotImplementedError("Implemented by child class")

    def __str__(self) -> Exception:
        raise NotImplementedError("Implemented by child class")

    def build_composite_bloq(
            self,
            bb: qualtran.BloqBuilder,
            **soqs: qualtran.SoquetT
            ) -> Dict[str, qualtran.SoquetT]:
        '''
            Naive composite bloq builder
        '''
        for subbloq in self.compose():
            bb.add(subbloq, **soqs)
        return soqs

    def decompose_from_registers(
        self,
        *args,
        context: cirq.DecompositionContext,
        **quregs: NDArray[cirq.Qid]
    ) -> Iterator[cirq.OP_TREE]:
        '''
            Call decompose from the composition object
        '''
        for op in self.compose():
            ops = op.decompose_from_registers(*args, context, quregs)
            yield from ops

    #pylint: disable=arguments-differ, unused-argument
    def _decompose_with_context_(self, *, context=None, **kwargs) -> Generator[
            qualtran.Bloq | cirq.Gate | cirq.Circuit,
            None,
            None
            ]:
        '''
            Generic decomposition wrapper calling the internal compose
        '''
        # Actually passing this into the decomposition depends on the decomp
        if context is None:
            context = cirq.DecompositionContext(
                cirq.ops.SimpleQubitManager()
            )
        yield from self.compose()

    def _qid_shape_(self):
        '''
        Override for superclass abstract method
        '''

    def num_qubits(self):
        '''
        Instantiates against an abstract method
        These qubit counts only account for non-ancillae qubits
        '''

    def __iter__(self) -> Generator[
            qualtran.Bloq | cirq.Gate | cirq.Circuit,
            None,
            None
            ]:
        return self.compose()

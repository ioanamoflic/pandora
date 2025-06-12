'''
    repeat.py
    Contains the Repeat meta-bloq
    Also contains a helper function circuit_to_quregs
'''
from typing import Dict, Iterator, Generator
from types import FunctionType
from numpy.typing import NDArray

import cirq
import qualtran
from qualtran._infra.gate_with_registers import GateWithRegisters
from qualtran._infra.registers import Signature

from pyLIQTR.utils.meta import MetaBloq


def circuit_to_quregs(circuit: cirq.Circuit) -> dict:
    '''
        Extracts quregs from a circuit
        Uses the same ordering as the
         CompositeBloq methods, allowing for
        preservation of argument order
        :: circuit : cirq.Circuit :: Circuit
    '''
    all_qubits = sorted(circuit.all_qubits())
    return {'qubits': [[i] for i in all_qubits]}


class Repeat(MetaBloq):
    '''
        Composite bloq with options for how to handle generators
        May cache and re-emit, or may continuously instantiate and generate
    '''

    # pylint: disable=too-many-instance-attributes
    def __init__(
            self,
            subbloq: qualtran.Bloq | cirq.Gate | cirq.Circuit,
            *args,
            n_repetitions: int = 1,
            caching: bool = False,
            **kwargs
    ):
        '''
            Constructor for the repeat bloq
            :: subbloq : GateWithRegisters | cirq.Gate :: Object to repeat
            :: *args :: Positional arguments
            :: n_repetitions : int :: Number of times to repeat the object
            :: caching : bool :: Whether the repeated object should be cached
            :: quregs : dict :: Map back to cirq qubit labels for qualtran bloq
        '''

        self.subbloq = subbloq
        self.args = args
        self.kwargs = kwargs
        self.n_repetitions = n_repetitions

        # Caches the circuit between iterations
        # Should only be used if the repeated object is small or constant
        self.caching = caching
        self._cached = None

        # Dynamic dispatch
        # Sets different decomposers depending on the input
        self._decompose = None

        if issubclass(type(subbloq), qualtran.Bloq):
            self._decompose = self._qualtran_bloq_decomp

        elif issubclass(type(subbloq), cirq.Gate):
            self._decompose = self._cirq_gate_decomp

        elif issubclass(type(subbloq), cirq.Circuit):
            self._decompose = self._cirq_circuit_decomp

        else:
            raise TypeError(
                f"{subbloq} is not a qualtran.Bloq, cirq.Gate or cirq.Circuit"
            )

    @property
    def signature(self) -> Signature:
        '''
            Signature is directly inherited from the subbloq
            May throw errors if the subbloq lacks a signature
        '''
        return self.subbloq.signature

    def __str__(self) -> str:
        '''
            Due to strcmp operations elsewhere in pyLIQTR this may cause issues
        '''
        return f'REPEAT({str(self.subbloq)}, {self.n_repetitions})'

    def _cirq_gate_decomp(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        '''
            _cirq_decomp
            Cirq gate decomposer
            Expected input is a single cirq gate object
        '''
        yield self.subbloq(*self.args, **self.kwargs)

    def _cirq_circuit_decomp(self) -> Generator[
        cirq.Circuit,
        None,
        None
    ]:
        '''
            _cirq_gate_decomp
            Cirq circuit decomposer
        '''
        for moment in self.subbloq:
            yield from moment

    def _qualtran_bloq_decomp(self) -> Generator[
        qualtran.Bloq,
        None,
        None
    ]:
        '''
            _qualtran_decomp
            Qualtran decomposer
        '''
        yield self.subbloq.to_cirq_circuit(
            *self.args,
            **self.kwargs
        )

    def build_composite_bloq(
            self,
            bb: qualtran.BloqBuilder,
            **soqs: qualtran.SoquetT
    ) -> Dict[str, qualtran.SoquetT]:
        '''
            Naive composite bloq builder
        '''
        for _ in range(self.n_repetitions):
            bb.add(self.subbloq, **soqs)
        return soqs

    def decompose_from_registers(
            self,
            *args,
            context: cirq.DecompositionContext,
            **quregs: NDArray[cirq.Qid]
    ) -> Iterator[cirq.OP_TREE]:
        '''
            decompose_from_registers
            Uses the subbloq's decomposition function and repeats the output
        '''
        if self.caching:
            cached_obj = list(
                self.subbloq.decompose_from_registers(
                    *args,
                    context,
                    quregs
                )
            )
            ops = iter(cached_obj)
        else:
            ops = self.subbloq.decompose_from_registers(*args, context, quregs)

        for _ in range(self.n_repetitions):
            yield from ops

    # pylint: disable=arguments-differ, unused-argument
    def _decompose_with_context_(self, *, context=None, **kwargs) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        # Actually passing this into the decomposition depends on the decomp
        if context is None:
            context = cirq.DecompositionContext(
                cirq.ops.SimpleQubitManager()
            )
        yield from self.decompose()

    def decompose(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        '''
        Dispatch method for decomposer
        Dynamic dispatch is set in the constructor
        '''
        for _ in range(self.n_repetitions):
            yield from self.decompose_once()

    def __iter__(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        return self.decompose()

    def decompose_once(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        '''
            Returns a single decomposition
        '''
        if self.caching:
            if self._cached is None:
                self._cached = tuple(self._decompose())
            decomp = self._cached
        else:
            decomp = self._decompose()

        yield from decomp

    def get_n_repetitions(self):
        '''
           Getter method
        '''
        return self.n_repetitions

    def _qid_shape_(self):
        '''
        Override for superclass abstract method
        '''

    def num_qubits(self):
        '''
        Instantiates against an abstract method
        These qubit counts only account for non-ancillae qubits
        '''
        return self.signature.n_qubits()


class Parameterised(MetaBloq):
    '''
        Parameterised Tagging Bloq
        Transparent Bloq wrapper that indicates to a `Map' bloq that this gate consumes arguments
        This Bloq should not be used outside of wrapper bloqs that handle the instantiation of
        parameters
    '''

    def __init__(
            self,
            subbloq_gen: FunctionType,
            *args,
            caching: bool = False,
            **kwargs
    ):
        '''
            Constructor for the Parameterised tagged Bloq
            :: subbloq_gen : FunctionType :: Constructor for the gate
            :: caching : bool :: Whether the repeated object should be cached
            :: quregs : dict :: Map back to cirq qubit labels for qualtran bloq
        '''
        self.subbloq_gen = subbloq_gen

        self.bound_args = args
        self.bound_kwargs = kwargs

        self.args = None
        self.kwargs = None

    @property
    def signature(self) -> Signature:
        '''
            Signature is instantiated after resolution
        '''
        pass

    def __str__(self) -> str:
        '''
            Due to strcmp operations elsewhere in pyLIQTR this may cause issues
        '''
        return f'PARAM({str(self.subbloq)})'

    def bind_params(self, *args, **kwargs):
        '''
            Setter method for binding args and kwargs
        '''
        self.args = args
        self.kwargs = kwargs

    def compose(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        '''
        Dispatch method for decomposer
        Dynamic dispatch is set in the constructor
        '''
        bloq = self.subbloq_gen(
            *self.bound_args, *self.args,
            **self.bound_kwargs, **self.kwargs
        )
        yield bloq


class ParamMap(MetaBloq):
    '''
        Parameterised Mapping Gate
        Bloq that takes a series of parameters and a sequence of gates / bloq objects
        When decomposed the parameters are consumed and the gate sequence is emitted
        Parameters are consumed by Parameterised Bloqs
    '''

    def __init__(
            self,
            parameters,
            *gate_sequence,
            caching: bool = False,
            **kwargs
    ):
        '''
            Constructor for the Parameterised tagged Bloq
            :: subbloq_gen : FunctionType :: Constructor for the gate
            :: caching : bool :: Whether the repeated object should be cached
            :: quregs : dict :: Map back to cirq qubit labels for qualtran bloq
        '''
        self.sequence = gate_sequence
        self.parameters = parameters

        self.kwargs = kwargs
        self.caching = caching
        self.cache = []
        self.cache_state = []

    @property
    def signature(self) -> Signature:
        '''
            Signature is instantiated after resolution
        '''
        pass

    def __str__(self) -> str:
        '''
            Due to strcmp operations elsewhere in pyLIQTR this may cause issues
        '''
        return f'MAP'

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

    @staticmethod
    def infer_params(*params):
        args = []
        kwargs = {}

        for param in params:
            if isinstance(param, dict):
                kwargs |= param
            elif isinstance(param, list):
                args += param
            else:
                args.append(param)
        return args, kwargs

    def compose(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        '''
        Dispatch method for decomposer
        Dynamic dispatch is set in the constructor
        '''
        cache_idx = 0
        params = iter(self.parameters)
        for bloq in self.sequence:

            # Special handling for flattening generators
            if isinstance(bloq, Generator):
                for subbloq in bloq:
                    yield self.resolve_params(subbloq, params, cache_idx)
                    cache_idx += 1

            else:  # Non-generator
                yield self.resolve_params(bloq, params, cache_idx)
                cache_idx += 1

    def resolve_params(self, bloq, params, cache_idx) -> qualtran.Bloq | cirq.Gate | cirq.Circuit:
        '''
            Helper function for resolving params
        '''
        # Collect Parameterised Tags
        if isinstance(bloq, Parameterised):

            # Infer params
            args, kwargs = self.infer_params(next(params))

            # Bind params to bloq instance
            bloq.bind_params(*args, **kwargs)

            for seq in bloq.compose():
                return seq

            if self.caching:
                self.cache_state.append(False)
                self.cache.append(None)

        else:  # Not Parameterised
            # Cache undiscovered object
            if self.caching:

                if (cache_idx < len(self.cache_state) and self.cache_state[cache_idx] is True):
                    return self.cache[cache_idx]

                self.cache.append(bloq)
                self.cache_state.append(True)

            return bloq

    def append(self, bloq: qualtran.Bloq | cirq.Gate | cirq.Circuit):
        '''
            Adds another gate to the sequence
        '''
        self.sequence.append(bloq)

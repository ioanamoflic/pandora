"""
    deferred.py
    Bloqs that defer instantiation
"""
from typing import Dict, Iterator, Generator
from types import FunctionType
from numpy.typing import NDArray

import cirq
import qualtran
from qualtran._infra.gate_with_registers import GateWithRegisters
from qualtran._infra.registers import Signature

from pyLIQTR.utils.meta import MetaBloq


class Deferred(MetaBloq):
    """
        This Bloq exists to defer instantiation
        The constructor for the deferred bloq is only instantiated during decomposition
        This allows for the seperation of decompose_multi and generator_decompose
        Where decompose_multi can instantiate a layer without the cost of all constructors
        in that layer
    """

    def __init__(
            self,
            subbloq_gen: FunctionType,
            *args,
            **kwargs
    ):
        """
            Constructor for the Deferred bloq
            :: subbloq_gen : FunctionType :: Constructor for the gate
            :: *args :: Args to the deferred bloq
            :: quregs : dict :: Map back to cirq qubit labels for qualtran bloq
            :: **kwargs :: Kwargs to the deferred bloq
        """
        self.subbloq_gen = subbloq_gen

        self.args = args
        self.kwargs = kwargs

    @property
    def signature(self) -> Signature:
        """
            Signature is instantiated after resolution
        """
        pass

    def __str__(self) -> str:
        """
            Due to strcmp operations elsewhere in pyLIQTR this may cause issues
        """
        return f'DEFER'

    def compose(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        """
        Dispatch method for decomposer
        Dynamic dispatch is set in the constructor
        """
        bloq = self.subbloq_gen(
            *self.args,
            **self.kwargs
        )
        yield bloq


class Cached(MetaBloq):
    """
        This Bloq exists to cache sub-bloqs
        Defers instantiation
        Generates singleton instances of sub-bloqs

        Cached elements may be dynamically altered without reconstructing
        the global object by re-writing the entry in the SINGLETON_CACHE

        Overwriting the cache variable itself will unbind the new instance
        at the object level

        Behaviour of overwriting the entire cache at the class level will
        depend on whether it is instantiated as a slot with double indirection
        or as a per-instance reference in each vtable
    """

    SINGLETON_CACHE = {}

    def __init__(
            self,
            tag,
            subbloq_gen: FunctionType,
            *args,
            **kwargs
    ):
        """
            Constructor for the Parameterised tagged Bloq
            :: tag : Hashable ::
            :: subbloq_gen : FunctionType :: Constructor for the gate
            :: quregs : dict :: Map back to cirq qubit labels for qualtran bloq
        """
        self.tag = tag
        self.subbloq_gen = subbloq_gen

        self.args = args
        self.kwargs = kwargs

    @property
    def signature(self) -> Signature:
        """
            Signature is instantiated after resolution
        """
        pass

    def __str__(self) -> str:
        """
            Due to strcmp operations elsewhere in pyLIQTR this may cause issues
        """
        return f'CACHE'

    def compose(self) -> Generator[
        qualtran.Bloq | cirq.Gate | cirq.Circuit,
        None,
        None
    ]:
        """
        Dispatch method for decomposer
        """
        cache_entry = Cached.SINGLETON_CACHE.get(self.tag, None)

        if cache_entry is None:
            bloq = self.subbloq_gen(
                *self.args,
                **self.kwargs
            )
            Cached.SINGLETON_CACHE[self.tag] = bloq
            yield bloq
        else:
            yield cache_entry

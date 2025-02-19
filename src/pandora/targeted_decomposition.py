'''
    Functions for extracting gates from pyliqtr decompositions
'''

from typing import Iterable, Callable

from cirq import Circuit
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
from pandora.pandora import Pandora


class GateNotFound(Exception):
    '''
        Exception used when a targeted gate is not found
         at that decomposition level
    '''
    def __str__(self):
        return '''Gate not found at this decomposition level'''

    def __repr__(self):
        return self.__str__()


def chain_decompose_multi(
        circuit: Circuit,
        maximum_decomp: int,
        minimum_decomp: int = 1):
    '''
        Generator function that chains multiple layers of decompositions
         together
        :: circuit : Circuit :: Circuit object
        :: maximum_decomp : int :: Maximum decomposition level
    '''
    for decomp_level in range(minimum_decomp, maximum_decomp):
        yield from circuit_decompose_multi(circuit, decomp_level)


def find_target_gate(
        decomposition: Circuit,
        target: type):
    '''
        Naive search for a target gate by class over a decomposition.
    :: decomposition : Circuit :: Circuit object
    :: target : type :: Gate type to target
    Bails on finding the first instance
    '''
    for moment in iter(decomposition):
        for operation in iter(moment):
            if isinstance(operation.gate, target):
                return operation
    print("Failed to find target")
    raise GateNotFound


def collect_gates(
        circuit: Circuit,
        gates: Iterable[type],
        maximum_decomp: int,
        minimum_decomp: int = 1,
        hash_fn: Callable = lambda x: x.__hash__()):
    '''
        collect_gates
        Takes a collection of gate types and returns a dictionary of types
         mapped to hashes of gates
        :: circuit : Circuit :: Circuit to decompose
        :: gates : Iterable[type] :: Types to track
        :: maximum_decomp : int :: Decomp levels
        :: minimum_decomp : int :: Starting decomp level
        :: hash_fh : Callable :: Hashing function

        It is suggested to patch the target gate objects with hash
         functions that parameterise the inputs of the target gates
    '''

    collected_gates = {gate: dict() for gate in gates}

    for moment in chain_decompose_multi(
            circuit,
            maximum_decomp=maximum_decomp,
            minimum_decomp=minimum_decomp):

        for operation in moment:

            tracked_op = collected_gates.get(operation.gate.__class__, None)
            if tracked_op is not None:
                tracked_op[hash_fn(operation)] = operation

    return collected_gates


def add_cache_db(pandora: Pandora, gate, db_name: str):
    '''
        Adds a decomposed gate to a new Pandora database
        :: gate : Operation :: pyliqtr operation
        :: db_name : str :: Name of database
    '''
    decomp_circuit = Circuit()
    decomp_circuit.append(gate)

    conn = pandora.spawn(db_name)
    conn.build_pyliqtr_circuit(pyliqtr_circuit=decomp_circuit)
    return conn

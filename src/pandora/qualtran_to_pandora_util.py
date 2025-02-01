import time
from typing import Iterator, Tuple, List

import cirq
import sys
import numpy as np

from qualtran import Bloq, QUInt
from qualtran.bloqs.chemistry.hubbard_model.qubitization import PrepareHubbard
from qualtran.bloqs.mod_arithmetic import ModAddK
from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM
from qualtran.bloqs.basic_gates import CNOT, TwoBitCSwap, XGate
from qualtran.cirq_interop import BloqAsCirqGate
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.qubitization import QubitizationWalkOperator
from qualtran.bloqs.qubitization.qubitization_walk_operator_test import get_walk_operator_for_1d_ising_model

from pyLIQTR.circuits.operators.AddMod import AddMod as pyLAM
from pyLIQTR.circuits.operators.AddMod import Add

from pyLIQTR.gate_decomp.cirq_transforms import _perop_clifford_plus_t_direct_transform
from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pandora.cirq_to_pandora_util import windowed_cirq_to_pandora_from_op_list
from pandora.exceptions import WindowSizeError
from pandora.gate_translator import In, Out, SINGLE_QUBIT_GATES, TWO_QUBIT_GATES
from pandora.gates import PandoraGate
from pandora.utils import printred

sys.setrecursionlimit(10000000)
# Increase recursion limit from default since adder bloq has a recursive implementation.

cirq_and_bloq_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    cirq.X, cirq.Y, cirq.Z,
    ModAddK,
    BloqAsCirqGate
)

pandora_ingestible_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    cirq.X, cirq.Y, cirq.Z,
)


def flatten(nested: list):
    for i in nested:
        if isinstance(i, list):
            for j in flatten(i):
                yield j
        else:
            yield i


def keep(op: cirq.Operation):
    gate = op.without_classical_controls().gate
    ret = gate in cirq_and_bloq_gate_set
    if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
        ret |= op.gate._original in cirq_and_bloq_gate_set
    return ret


def get_cirq_circuit_for_bloq(bloq: Bloq):
    # Get a cirq circuit containing only this operation.
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts()))
    # Decompose the operation until all gates are in the target gate set.
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    return cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))


def assert_circuit_is_decomposable(circuit: cirq.Circuit):
    # Assert that all operations in the decomposed circuit are part of the target gate set.
    assert all(op.without_classical_controls() in cirq_and_bloq_gate_set for op in circuit.all_operations())


def assert_circuit_is_pandora_ingestible(circuit: cirq.Circuit):
    # Assert that all operations in the decomposed circuit are part of the target gate set.
    for op in circuit.all_operations():
        if op.without_classical_controls() not in pandora_ingestible_gate_set:
            print(op.without_classical_controls().gate)
    assert all(op.without_classical_controls() in pandora_ingestible_gate_set for op in circuit.all_operations())


def assert_op_list_is_pandora_ingestible(op_list: list):
    # Assert that all operations are part of the target gate set.
    for op in op_list:
        if isinstance(op, list):
            op = op[0]
        if op.without_classical_controls() not in pandora_ingestible_gate_set:
            print(op.without_classical_controls().gate)
    assert all(op.without_classical_controls() in pandora_ingestible_gate_set for op in op_list)


def decompose_fredkin(op: cirq.Operation):
    ops = []
    ctrl, x, y = op.qubits
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.CNOT(ctrl, x), cirq.H(y)]
    ops += [cirq.T(ctrl), cirq.T(x) ** -1, cirq.T(y)]
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.CNOT(ctrl, y), cirq.T(x)]
    ops += [cirq.CNOT(ctrl, x), cirq.T(y) ** -1]
    ops += [cirq.T(x) ** -1, cirq.CNOT(ctrl, y)]
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.T(x), cirq.H(y)]
    ops += [cirq.CNOT(y, x)]
    return ops


def decompose_qualtran_bloq_gate(bloq: Bloq):
    cirq_quregs = get_named_qubits(bloq.signature.lefts())
    circuit = bloq.as_composite_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs)
    decomp_circuit = cirq.Circuit(cirq.decompose(next(circuit.all_operations())))

    fully_decomposed_ops = []
    for op in decomp_circuit.all_operations():
        if isinstance(op.gate, BloqAsCirqGate):
            if isinstance(op.gate.bloq, CNOT):
                ctrl, tgt = op.qubits
                fully_decomposed_ops.append(cirq.CX.on(ctrl, tgt))
            elif isinstance(op.gate.bloq, XGate):
                fully_decomposed_ops.append(cirq.X.on(op.qubits[0]))
            elif isinstance(op.gate.bloq, TwoBitCSwap):
                fully_decomposed_ops = fully_decomposed_ops + decompose_fredkin(op)
        else:
            fully_decomposed_ops.append(op)
    return fully_decomposed_ops


def get_pandora_compatible_circuit(circuit: cirq.Circuit, decompose_from_high_level=True) -> cirq.Circuit:
    """
    Takes a Cirq circuit as input and outputs a logically equivalent circuit with operations acting on at most three
    qubits which can be ingested into Pandora.

    This is the SLOW method. For small circuits only.
    """
    if decompose_from_high_level:
        context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
        circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops = []
    for op in circuit.all_operations():
        # TODO: should we ignore GlobalPhaseGate?
        if isinstance(op.gate, cirq.GlobalPhaseGate):
            print(f'Encountered GlobalPhaseGate with qubits = {op.qubits}')
            continue
        if isinstance(op.gate, BloqAsCirqGate):
            atomic_ops = list(decompose_qualtran_bloq_gate(op.gate.bloq))
            final_ops = final_ops + atomic_ops
        else:
            final_ops.append(op)

    decomposed_circuit = cirq.Circuit(final_ops)
    return decomposed_circuit


def generator_get_pandora_compatible_batch_via_pyliqtr(circuit: cirq.Circuit,
                                                       window_size: int) -> Iterator[list[cirq.Operation]]:
    """
    This is a generator-based (windowed) decomposition into Clifford+T build on top of pyLIQTR's generator
    decomposition method. The method yields a batch of window_size elements.
    Args:
        circuit: the high-level cirq circuit
        window_size: size of the window

    Returns:
        Generator over the tuples consisting of the cirq operations contained in the batch.
    """
    window_ops = []

    for dop in generator_decompose(circuit, keep=keep):
        start_dop = time.time()
        if isinstance(dop.gate, cirq.GlobalPhaseGate):
            print(f'Encountered GlobalPhaseGate with qubits = {dop.qubits}')
            pass
        elif isinstance(dop.gate, BloqAsCirqGate):
            atomic_ops = decompose_qualtran_bloq_gate(dop.gate.bloq)
            window_ops.extend(atomic_ops)
        elif isinstance(dop.gate, ModAddK):
            top = pyLAM(bitsize=dop.gate.bitsize,
                        add_val=dop.gate.add_val,
                        mod=dop.gate.mod,
                        cvs=dop.gate.cvs).on(*dop.qubits)
            for d_top in generator_decompose(top):
                atomic_ops = _perop_clifford_plus_t_direct_transform(d_top,
                                                                     use_rotation_decomp_gates=False,
                                                                     use_random_decomp=True,
                                                                     warn_if_not_decomposed=True)
                window_ops.extend(atomic_ops)
        else:
            atomic_ops = _perop_clifford_plus_t_direct_transform(dop,
                                                                 use_rotation_decomp_gates=False,
                                                                 use_random_decomp=True,
                                                                 warn_if_not_decomposed=True)
            window_ops.extend(atomic_ops)

        if len(window_ops) >= window_size:
            window_ops = list(flatten(window_ops))
            assert_op_list_is_pandora_ingestible(window_ops)
            yield window_ops, time.time() - start_dop
            window_ops = []

    start_last = time.time()
    if len(window_ops) > 0:
        window_ops = list(flatten(window_ops))
        assert_op_list_is_pandora_ingestible(window_ops)
        yield window_ops, time.time() - start_last


def windowed_cirq_to_pandora(circuit: cirq.Circuit | Bloq, window_size: int, is_test: bool = False) \
        -> Iterator[tuple[list[PandoraGate], float]]:
    """
    This method traverses a cirq circuit in windows of arbitrary size and returns the PandoraGate operations equivalent
    to the cirq operations in the window. Especially useful for very large circuits which do not fit into memory. The
    list of qubits in the resulting circuit will be a permutation fo the original one.
    Args:
        is_test: boolean which takes qubit ordering into account during testing for 1:1 reconstruction.
        circuit: the high-level cirq circuit
        window_size: the size of each decomposition window
    Returns:
        Generator over the PandoraGate objects of each batch.
    """
    if window_size <= 1:
        raise WindowSizeError

    qubit_set = set()
    pandora_dictionary = dict()
    latest_conc_on_qubit = dict()
    last_id = 0

    windows = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=circuit,
                                                                 window_size=window_size)

    for i, (current_window, cliff_decomp_time) in enumerate(windows):
        for op in current_window:
            qubit_set.update(set(list(op.qubits)))

        start_cirq_to_pandora = time.time()
        # the idea is to add anything that is not null on "next link" from the pandora gates dictionary
        pandora_dictionary, latest_conc_on_qubit, last_id = windowed_cirq_to_pandora_from_op_list(
            op_list=current_window,
            pandora_dictionary=pandora_dictionary,
            latest_conc_on_qubit=latest_conc_on_qubit,
            last_id=last_id,
            label='x',
            is_test=is_test
        )

        #TODO: Explain the code below
        dictionary_copy = pandora_dictionary.copy()
        window_elements: list[PandoraGate] = []
        for pandora_gate in dictionary_copy.values():
            if (pandora_gate.type in SINGLE_QUBIT_GATES
                and pandora_gate.next_q1 is not None) \
                    or (pandora_gate.type in TWO_QUBIT_GATES
                        and pandora_gate.next_q1 is not None
                        and pandora_gate.next_q2 is not None):
                window_elements.append(pandora_gate)
                pandora_dictionary.pop(pandora_gate.id)

        yield window_elements, time.time() - start_cirq_to_pandora + cliff_decomp_time

    # The final window consists of only output gates
    # printred("The last batch from here")
    start_final = time.time()
    final_window: list[cirq.Operation] = [Out().on(q) for q in qubit_set]
    pandora_out_gates, _, _ = windowed_cirq_to_pandora_from_op_list(
        op_list=final_window,
        pandora_dictionary=pandora_dictionary,
        latest_conc_on_qubit=latest_conc_on_qubit,
        last_id=last_id,
        label='x',
        is_test=is_test)
    yield list(pandora_out_gates.values()), time.time() - start_final


def get_resource_state(m: int):
    r"""Returns a state vector representing the resource state on m qubits from Eq.17 of Ref-1.

    Returns a numpy array of size 2^{m} representing the state vector corresponding to the state
    $$
        \sqrt{\frac{2}{2^m + 1}} \sum_{n=0}^{2^{m}-1} \sin{\frac{\pi(n + 1)}{2^{m}+1}}\ket{n}
    $$

    Args:
        m: Number of qubits to prepare the resource state on.

    Ref:
        1) [Encoding Electronic Spectra in Quantum Circuits with Linear T Complexity]
            (https://arxiv.org/abs/1805.03662)
            Eq. 17
    """
    den = 1 + 2 ** m
    norm = np.sqrt(2 / den)
    return norm * np.sin(np.pi * (1 + np.arange(2 ** m)) / den)


def phase_estimation(walk: QubitizationWalkOperator, m: int) -> cirq.OP_TREE:
    """Heisenberg limited phase estimation circuit for learning eigenphase of `walk`.

    The method yields an OPTREE to construct Heisenberg limited phase estimation circuit
    for learning eigenphases of the `walk` operator with `m` bits of accuracy. The
    circuit is implemented as given in Fig.2 of Ref-1.

    Args:
        walk: Qubitization walk operator.
        m: Number of bits of accuracy for phase estimation.

    Ref:
        1) [Encoding Electronic Spectra in Quantum Circuits with Linear T Complexity]
            (https://arxiv.org/abs/1805.03662)
            Fig. 2
    """
    reflect = walk.reflect
    walk_regs = get_named_qubits(walk.signature)
    reflect_regs = {reg.name: walk_regs[reg.name] for reg in reflect.signature}

    reflect_controlled = reflect.controlled(control_values=[0])
    walk_controlled = walk.controlled(control_values=[1])

    m_qubits = [cirq.q(f'm_{i}') for i in range(m)]
    state_prep = cirq.StatePreparationChannel(get_resource_state(m), name='chi_m')

    # yield state_prep.on(*m_qubits)
    yield walk_controlled.on_registers(**walk_regs, control=m_qubits[0])
    for i in range(1, m):
        yield reflect_controlled.on_registers(control=m_qubits[i], **reflect_regs)
        walk = walk ** 2
        yield walk.on_registers(**walk_regs)
        yield reflect_controlled.on_registers(control=m_qubits[i], **reflect_regs)

    yield cirq.qft(*m_qubits, inverse=True)


def get_adder(n_bits, window_size=100, is_test=False) -> Iterator[tuple[list[PandoraGate], float]]:
    """
    Returns a decomposed Qualtran Adder into a Pandora compatible gate format.
    """
    bloq = Add(QUInt(n_bits))
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts())).unfreeze()
    return windowed_cirq_to_pandora(circuit=circuit, window_size=window_size, is_test=is_test)


def get_qrom(data, window_size=100, is_test=False) -> Iterator[tuple[list[PandoraGate], float]]:
    """
    Returns a decomposed Qualtran QROM into a Pandora compatible gate format.
    """
    bloq = QROM.build_from_data(data)
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts())).unfreeze()
    return windowed_cirq_to_pandora(circuit=circuit, window_size=window_size, is_test=is_test)


def get_qpe_of_1d_ising_model(num_sites=1, eps=1e-5, m_bits=1) -> Iterator[tuple[list[PandoraGate], float]]:
    """
    Returns a decomposed Qualtran QPE of a 1d ising model into a Pandora compatible gate format.

    Implementation from https://github.com/quantumlib/Qualtran/blob/main/qualtran/bloqs/phase_estimation/phase_estimation_of_quantum_walk.ipynb
    """
    walk_op = get_walk_operator_for_1d_ising_model(num_sites, eps)
    circuit = cirq.Circuit(phase_estimation(walk_op, m=m_bits))
    return windowed_cirq_to_pandora(circuit=circuit, window_size=1000000)


def get_2d_hubbard_model(dim: tuple[int, int] = (2, 2), t=1.0, u=4) -> Iterator[tuple[list[PandoraGate], float]]:
    """
    PREPARE bloq taken from https://github.com/quantumlib/Qualtran/blob/main/qualtran/bloqs/chemistry/hubbard_model/qubitization/hubbard_model.ipynb
    Args:
        dim: the number of sites along the x/y-axis.
        t: coefficient for hopping terms in the Hubbard model hamiltonian.
        u: coefficient for single body Z term and two-body ZZ terms in the Hubbard model hamiltonian.

    Returns:
        A decomposed PREPARE operation optimized for the 2D Hubbard model into a Pandora compatible gate format.

    """
    x_dim, y_dim = dim
    bloq = PrepareHubbard(x_dim, y_dim, t=t, u=u)
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts())).unfreeze()
    return windowed_cirq_to_pandora(circuit=circuit, window_size=1000000)


def get_adder_as_cirq_circuit(n_bits) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = Add(QUInt(n_bits))
    clifford_t_circuit = get_cirq_circuit_for_bloq(bloq)
    assert_circuit_is_pandora_ingestible(clifford_t_circuit)
    return clifford_t_circuit


def get_qrom_as_cirq_circuit(data) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = QROM.build_from_data(data)
    qrom_circuit = get_cirq_circuit_for_bloq(bloq)
    return qrom_circuit

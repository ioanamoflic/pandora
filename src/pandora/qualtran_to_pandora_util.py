import cirq
import sys
import numpy as np
from qualtran import Bloq, QUInt
from qualtran.bloqs.arithmetic import Add
from qualtran.bloqs.mod_arithmetic import ModAddK
from qualtran._infra.adjoint import Adjoint
from qualtran.bloqs.data_loading import QROM
from qualtran.bloqs.basic_gates import CNOT, TwoBitCSwap, XGate
from qualtran.cirq_interop import BloqAsCirqGate
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.qubitization import QubitizationWalkOperator
from qualtran.bloqs.qubitization.qubitization_walk_operator_test import get_walk_operator_for_1d_ising_model

sys.setrecursionlimit(10000)  # Increase recursion limit from default since adder bloq has a recursive implementation.

cirq_and_bloq_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    cirq.X, cirq.Y, cirq.Z,
    # ModAddK,
    # Adjoint,
    BloqAsCirqGate,
)

pandora_ingestible_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    cirq.X, cirq.Y, cirq.Z,
)


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
    assert all(op.without_classical_controls() in pandora_ingestible_gate_set for op in circuit.all_operations())


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


def get_adder(n_bits) -> cirq.Circuit:
    """
    Returns a decomposed Qualtran Adder into a Pandora compatible gate format.
    """
    bloq = Add(QUInt(n_bits))
    clifford_t_circuit = get_cirq_circuit_for_bloq(bloq)
    assert_circuit_is_pandora_ingestible(clifford_t_circuit)
    return clifford_t_circuit


def get_qrom(data) -> cirq.Circuit:
    """
    Returns a decomposed Qualtran QROM into a Pandora compatible gate format.
    """
    bloq = QROM.build_from_data(data)
    qrom_circuit = get_cirq_circuit_for_bloq(bloq)
    return get_pandora_compatible_circuit(circuit=qrom_circuit, decompose_from_high_level=False)


def get_qpe_of_1d_ising_model(num_sites=1, eps=1e-5, m_bits=1) -> cirq.Circuit:
    """
    Returns a decomposed Qualtran QPE of a 1d ising model into a Pandora compatible gate format.

    Implementation from https://github.com/quantumlib/Qualtran/blob/main/qualtran/bloqs/phase_estimation/phase_estimation_of_quantum_walk.ipynb
    """
    walk_op = get_walk_operator_for_1d_ising_model(num_sites, eps)
    circuit = cirq.Circuit(phase_estimation(walk_op, m=m_bits))
    return get_pandora_compatible_circuit(circuit=circuit, decompose_from_high_level=True)


def get_qpe_of_2d_hubbard_model() -> cirq.Circuit:
    # TODO figure out a way to decompose ModAddK
    raise NotImplementedError

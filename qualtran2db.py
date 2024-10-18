import qualtran
from qualtran.bloqs.arithmetic import Add
from _connection import *
import sys
import numpy as np
from qualtran import Bloq, QUInt
from qualtran.bloqs.arithmetic import Add
from qualtran.bloqs.data_loading import QROM
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.qubitization import QubitizationWalkOperator
from qualtran.bloqs.qubitization.qubitization_walk_operator_test import get_walk_operator_for_1d_ising_model
from qualtran.cirq_interop import cirq_optree_to_cbloq
from qualtran.bloqs.chemistry.hubbard_model.qubitization import get_walk_operator_for_hubbard_model

sys.setrecursionlimit(10000)  # Increase recursion limit from default since adder bloq has a recursive implementation.

more_general_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel, qualtran.cirq_interop.BloqAsCirqGate,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.CZPowGate, cirq.CXPowGate,
    cirq.X, cirq.Y, cirq.Z, qualtran.bloqs.mod_arithmetic.ModAddK
)


def keep(op: cirq.Operation):
    gate = op.without_classical_controls().gate
    ret = gate in more_general_gate_set
    if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
        ret |= op.gate._original in more_general_gate_set
    return ret


def get_clifford_plus_t_cirq_circuit_for_bloq(bloq: Bloq):
    # Get a cirq circuit containing only this operation.
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts()))
    # Decompose the operation until all gates are in the target gate set.
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    return cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))


def assert_circuit_in_clifford_plus_t(circuit: cirq.Circuit):
    # Assert that all operations in the decomposed circuit are part of the target gate set.
    assert all(op.without_classical_controls() in more_general_gate_set for op in circuit.all_operations())


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
    # state_prep = cirq.StatePreparationChannel(get_resource_state(m), name='chi_m')

    # yield state_prep.on(*m_qubits)
    yield walk_controlled.on_registers(**walk_regs, control=m_qubits[0])
    for i in range(1, m):
        yield reflect_controlled.on_registers(control=m_qubits[i], **reflect_regs)
        walk = walk ** 2
        yield walk.on_registers(**walk_regs)
        yield reflect_controlled.on_registers(control=m_qubits[i], **reflect_regs)

    yield cirq.qft(*m_qubits, inverse=True)


def adder_decomposed():
    # adder example
    bloq = Add(QUInt(2))
    circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
    assert_circuit_in_clifford_plus_t(circuit)
    print(circuit)


def qrom_decomposed():
    # QROM example
    data1 = np.arange(9).reshape((3, 3))
    data2 = (np.arange(9) + 1).reshape((3, 3))
    qrom_multi_dim = QROM([data1, data2], selection_bitsizes=(2, 2), target_bitsizes=(8, 8))
    circuit = get_clifford_plus_t_cirq_circuit_for_bloq(qrom_multi_dim)
    assert_circuit_in_clifford_plus_t(circuit)
    print(circuit)


def qpe_decomposed():
    # phase estimation example
    num_sites: int = 2
    eps: float = 1e-2
    m_bits: int = 4

    circuit = cirq.Circuit(phase_estimation(get_walk_operator_for_1d_ising_model(num_sites, eps), m=m_bits))
    print(circuit)
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops = []
    for op in circuit.all_operations():
        op = op.without_classical_controls()
        if isinstance(op.gate, cirq.GlobalPhaseGate):
            continue
        if isinstance(op.gate, qualtran.cirq_interop.BloqAsCirqGate):
            if isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.swap.TwoBitCSwap):
                ctrl, x, y = op.qubits
                context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
                ops = op.gate.bloq.decompose_from_registers(ctrl=[ctrl], x=[x], y=[y], context=context)
                for o in ops:
                    for x in o:
                        final_ops.append(x)
            elif isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.cnot.CNOT):
                ctrl, tgt = op.qubits
                cx = op.gate.bloq.as_cirq_op(qubit_manager=cirq.SimpleQubitManager(),
                                             ctrl=[ctrl],
                                             target=[tgt]
                                             )
                final_ops.append(cx[0])
        else:
            final_ops.append(op)

    decomposed_circuit = cirq.Circuit(final_ops)
    op_set = set()
    for op in decomposed_circuit.all_operations():
        if op.gate.__class__.__name__ == 'NoneType':
            print(op)
            print(op.gate)
        op_set.add(op.gate.__class__.__name__)

    print(op_set)
    return decomposed_circuit


def hubbard_2D_decomposed():
    x_dim, y_dim = 2, 2
    t = 2
    mu = 4 * t
    N = x_dim * y_dim * 2
    qlambda = 2 * N * t + (N * mu) // 2
    delta_E = t / 100
    m_bits = int(np.ceil(np.log2(qlambda * np.pi * np.sqrt(2) / delta_E)))
    walk = get_walk_operator_for_hubbard_model(x_dim, y_dim, t, mu)
    circuit = cirq.Circuit(phase_estimation(walk, m=m_bits))
    print(circuit)
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    print('Starting to decompose in cirq...')
    circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    print('Starting to decompose manually...')
    final_ops = []
    for op in circuit.all_operations():
        op = op.without_classical_controls()
        if isinstance(op.gate, cirq.GlobalPhaseGate):
            continue
        # for now, ignore ModAddK, this might add optimisation logical problems
        if isinstance(op.gate, qualtran.bloqs.mod_arithmetic.ModAddK):
            continue
        if isinstance(op.gate, qualtran.cirq_interop.BloqAsCirqGate):
            if isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.swap.TwoBitCSwap):
                ctrl, x, y = op.qubits
                context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
                ops = op.gate.bloq.decompose_from_registers(ctrl=[ctrl], x=[x], y=[y], context=context)
                for o in ops:
                    for x in o:
                        final_ops.append(x)
            elif isinstance(op.gate.bloq, qualtran.bloqs.basic_gates.cnot.CNOT):
                ctrl, tgt = op.qubits
                cx = op.gate.bloq.as_cirq_op(qubit_manager=cirq.SimpleQubitManager(),
                                             ctrl=[ctrl],
                                             target=[tgt]
                                             )
                final_ops.append(cx[0])
        else:
            final_ops.append(op)

    print(f'Number of operations in the circuit: {len(final_ops)}')
    decomposed_circuit = cirq.Circuit(final_ops)
    op_set = set()
    for op in decomposed_circuit.all_operations():
        op_set.add(op.gate.__class__.__name__)
    print(op_set)
    return decomposed_circuit


if __name__ == "__main__":
    # adder_decomposed()
    # qrom_decomposed()
    # qpe_decomposed()
    hubbard_2D_decomposed()

import cirq
from collections import defaultdict

from qiskit import QuantumCircuit
from qiskit.circuit import Operation

from pandora.translation.translator import (
    PANDORA_TO_CIRQ,
    PANDORA_TO_QISKIT
)


def gate_qubits(g):
    if g.control_q is not None and g.target_q is not None:
        return [g.control_q, g.target_q]

    if g.control_q is not None and g.target_q is None:
        return [g.control_q]

    if g.control_q is None and g.target_q is None:
        return []

    raise ValueError(
        f"Invalid gate {g.id}: target_q is set but control_q is None"
    )


def pandora_gate_layers_to_cirq(gate_layers):
    if not gate_layers:
        return cirq.Circuit()

    max_q = max(
        q
        for g in gate_layers
        for q in (g.control_q, g.target_q)
        if q is not None
    )

    qubits = [cirq.LineQubit(i) for i in range(max_q + 1)]
    ops_by_layer = defaultdict(list)

    for g in gate_layers:
        gate = PANDORA_TO_CIRQ[g.type]

        if isinstance(gate, type):
            gate = gate(exponent=g.param) if g.param is not None else gate()

        elif callable(gate) and not isinstance(gate, cirq.Gate):
            gate = gate(rads=g.param) if g.param is not None else gate()

        qids = gate_qubits(g)

        if len(qids) == 0:
            continue
        else:
            op = gate.on(*(qubits[q] for q in qids))

        ops_by_layer[g.layer].append(op)

    return cirq.Circuit(
        cirq.Moment(ops_by_layer[layer])
        for layer in sorted(ops_by_layer)
    )


def make_qiskit_instruction(gate_like, param):
    if isinstance(gate_like, type):
        if param is not None:
            try:
                return gate_like(param)
            except TypeError:
                return gate_like()
        return gate_like()

    if isinstance(gate_like, Operation):
        return gate_like

    if hasattr(gate_like, "num_qubits") and hasattr(gate_like, "params"):
        return gate_like

    raise TypeError(f"Unsupported Qiskit gate mapping: {gate_like!r}")


def pandora_gate_layers_to_qiskit(gate_layers):
    if not gate_layers:
        return QuantumCircuit(0)

    max_q = max(
        q
        for g in gate_layers
        for q in (g.control_q, g.target_q)
        if q is not None
    )

    qc = QuantumCircuit(max_q + 1)

    for g in sorted(gate_layers, key=lambda x: (x.layer, x.id)):
        qargs = gate_qubits(g)

        if not qargs:
            continue

        gate_like = PANDORA_TO_QISKIT[g.type]

        instruction = make_qiskit_instruction(gate_like, g.param)

        qc.append(instruction, qargs)

    return qc

import cirq
import qiskit
from qiskit import QuantumCircuit

from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM
from qualtran import QUInt

from pandora.util.qualtran_util import (
    assert_circuit_is_pandora_ingestible
)
from pandora.translation.translator import In, Out
from pandora.util.test_util import test_get_cirq_circuit_for_bloq


def get_adder_as_cirq_circuit(n_bits) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = Add(QUInt(n_bits))
    clifford_t_circuit = test_get_cirq_circuit_for_bloq(bloq)
    assert_circuit_is_pandora_ingestible(clifford_t_circuit)
    return clifford_t_circuit


def get_qrom_as_cirq_circuit(data) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = QROM.build_from_data(data)
    qrom_circuit = test_get_cirq_circuit_for_bloq(bloq)
    return qrom_circuit


def remove_io_gates(circuit: cirq.Circuit | qiskit.QuantumCircuit,
                    type='cirq'):
    if type == 'cirq':
        return cirq.Circuit(
            op
            for op in circuit.all_operations()
            if not isinstance(op.gate, (In, Out))
        )

    if type == 'qiskit':
        new_circuit = QuantumCircuit(
            circuit.num_qubits,
            circuit.num_clbits
        )
        for inst in circuit.data:
            if inst.operation.name not in ("In", "Out"):
                new_circuit.append(
                    inst.operation,
                    inst.qubits,
                    inst.clbits
                )

        return new_circuit

    return None


def remove_classically_controlled_ops(circuit: cirq.Circuit) -> cirq.Circuit:
    return cirq.Circuit(
        op.without_classical_controls()
        for op in circuit.all_operations()
    )


def remove_measurements(circuit: cirq.Circuit) -> cirq.Circuit:
    return cirq.Circuit(
        op
        for op in circuit.all_operations()
        if not isinstance(op.gate, (cirq.MeasurementGate, cirq.ResetChannel))
    )

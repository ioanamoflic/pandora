import math
from qiskit import QuantumCircuit

from pandora.translation.gates import PandoraGate, PandoraGateWrapper
from pandora.translation.qiskit_translator import QiskitToPandoraTranslator
from pandora.translation.translator import PandoraGateTranslator

def test_qiskit_rotation_gates_keep_their_axis():
    circuit = QuantumCircuit(1)
    circuit.rx(0.1, 0)
    circuit.ry(0.2, 0)
    circuit.rz(0.3, 0)

    translator = QiskitToPandoraTranslator()
    translated = [translator.translate(instruction) for instruction in circuit.data]

    assert [gate.type for gate in translated] == [
        PandoraGateTranslator.Rx.value,
        PandoraGateTranslator.Ry.value,
        PandoraGateTranslator.Rz.value,
    ]

def test_qiskit_rotation_gates_keep_their_value():
    circuit = QuantumCircuit(1)
    circuit.rx(math.pi, 0)
    circuit.ry(math.pi, 0)
    circuit.rz(math.pi, 0)

    translator = QiskitToPandoraTranslator()
    translated = [translator.translate(instruction) for instruction in circuit.data]

    for gate in translated:
        wrapper = PandoraGateWrapper(gate)
        qgate = wrapper.to_qiskit_gate()
        assert qgate.params[0] == math.pi

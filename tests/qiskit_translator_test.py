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


def test_qiskit_exponent_gates_work():
    circuit = QuantumCircuit(4)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cz(1, 2)
    circuit.ccx(0, 1, 2)

    translator = QiskitToPandoraTranslator()
    translated = [translator.translate(instruction) for instruction in circuit.data]

    back_to_qiskit = [PandoraGateWrapper(gate).to_qiskit_gate() for gate in translated]

    assert [gate.name for gate in back_to_qiskit] == [
        "h",
        "cx",
        "cz",
        "ccx",
    ]

def test_qiskit_exponent_gates_have_param():
    circuit = QuantumCircuit(4)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cz(1, 2)
    circuit.ccx(0, 1, 2)

    translator = QiskitToPandoraTranslator()
    translated = [translator.translate(instruction) for instruction in circuit.data]

    assert [(gate.type, gate.param) for gate in translated] == [
        (PandoraGateTranslator.HPowGate.value, 1.0),
        (PandoraGateTranslator.CXPowGate.value, 1.0),
        (PandoraGateTranslator.CZPowGate.value, 1.0),
        (PandoraGateTranslator.CCXPowGate.value, 1.0),
    ]
    
def test_pandora_to_qiskit_extra_gates():
    gates = [
        PandoraGate(gate_code=PandoraGateTranslator.Swap.value),
        PandoraGate(gate_code=PandoraGateTranslator.CNOT.value),
    ]

    qiskit_gates = [PandoraGateWrapper(gate).to_qiskit_gate() for gate in gates]

    assert [gate.name for gate in qiskit_gates] == [
        "swap",
        "cx",
    ]
from abc import ABC
from enum import Enum
import cirq
import numpy as np
import qiskit
from qiskit import QuantumCircuit
from qualtran.bloqs.arithmetic.addition import And


class In(cirq.Gate, ABC):
    def __init__(self, is_classic=False, key=None):
        super(In, self)
        if key is None:
            self.gate = 'In'
        else:
            self.gate = key
        self.is_classic = is_classic

    def _num_qubits_(self):
        return 1

    def _unitary_(self):
        return np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ])

    def _circuit_diagram_info_(self, args):
        return self.gate

    def __str__(self):
        return self.gate


class Out(cirq.Gate, ABC):
    def __init__(self, is_classic=False, key=None):
        super(Out, self)
        self.is_classic = is_classic
        if key is None:
            self.gate = 'Out'
        else:
            self.gate = key

    def _num_qubits_(self):
        return 1

    def _unitary_(self):
        return np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ])

    def _circuit_diagram_info_(self, args):
        return self.gate

    def __str__(self):
        return self.gate


# each gate will have a different code used as a fast(er) comparison key in the database
class PandoraGateTranslator(Enum):
    In = 0
    Out = 1
    Rx = 2
    Ry = 3
    Rz = 4
    XPowGate = 5
    YPowGate = 6
    ZPowGate = 7
    HPowGate = 8
    _PauliX = 9
    _PauliZ = 10
    _PauliY = 11
    GlobalPhaseGate = 12
    ResetChannel = 13
    M = 14
    CNOT = 15
    CZ = 16
    CZPowGate = 17
    CXPowGate = 18
    XXPowGate = 19
    ZZPowGate = 20
    Toffoli = 21
    And = 22
    CCXPowGate = 23
    CSwapGate = 24
    GlobalIn = 25
    GlobalOut = 26
    S = 27
    S_dag = 28
    T = 29
    T_dag = 30
    Swap = 31


MAX_QUBITS_PER_GATE = 3
GLOBAL_IN_ID = -1
GLOBAL_OUT_ID = -2

KEEP_RZ = False

# accepted gates for now
QISKIT_TO_PANDORA = {
    "rx": PandoraGateTranslator.Rx.value,
    "ry": PandoraGateTranslator.Rx.value,
    "rz": PandoraGateTranslator.Rx.value,
    "h": PandoraGateTranslator.HPowGate.value,
    "x": PandoraGateTranslator._PauliX.value,
    "y": PandoraGateTranslator._PauliY.value,
    "z": PandoraGateTranslator._PauliZ.value,
    "s": PandoraGateTranslator.S.value,
    "sdg": PandoraGateTranslator.S_dag.value,
    "t": PandoraGateTranslator.T.value,
    "tdg": PandoraGateTranslator.T_dag.value,
    "cx": PandoraGateTranslator.CXPowGate.value,
    "cz": PandoraGateTranslator.CZPowGate.value,
    "ccx": PandoraGateTranslator.CCXPowGate.value,
    "swap": PandoraGateTranslator.Swap.value,
    "measure": PandoraGateTranslator.M.value,
    "In": PandoraGateTranslator.In.value,
    "Out": PandoraGateTranslator.Out.value,
}

PANDORA_TO_QISKIT = {
    PandoraGateTranslator.In.value: QuantumCircuit(1, name="In").to_gate(label="In"),
    PandoraGateTranslator.Out.value: QuantumCircuit(1, name="Out").to_gate(label="Out"),
    PandoraGateTranslator.Rx.value: qiskit.circuit.library.RXGate,
    PandoraGateTranslator.Ry.value: qiskit.circuit.library.RYGate,
    PandoraGateTranslator.Rz.value: qiskit.circuit.library.RZGate,
    PandoraGateTranslator.HPowGate.value: qiskit.circuit.library.HGate,
    PandoraGateTranslator.S.value: qiskit.circuit.library.SGate,
    PandoraGateTranslator.S_dag.value: qiskit.circuit.library.SdgGate,
    PandoraGateTranslator.T.value: qiskit.circuit.library.TGate,
    PandoraGateTranslator.T_dag.value: qiskit.circuit.library.TdgGate,
    PandoraGateTranslator._PauliX.value: qiskit.circuit.library.XGate,
    PandoraGateTranslator._PauliZ.value: qiskit.circuit.library.ZGate,
    PandoraGateTranslator._PauliY.value: qiskit.circuit.library.YGate,
    PandoraGateTranslator.CXPowGate.value: qiskit.circuit.library.CXGate,
    PandoraGateTranslator.CZPowGate.value: qiskit.circuit.library.CZGate,
    PandoraGateTranslator.CCXPowGate.value: qiskit.circuit.library.CCXGate,
    PandoraGateTranslator.Swap.value: qiskit.circuit.library.SwapGate
}

IS_IO = [PandoraGateTranslator.In.value, PandoraGateTranslator.Out.value]

PANDORA_TO_CIRQ = {
    PandoraGateTranslator.Rx.value: cirq.ops.common_gates.Rx,
    PandoraGateTranslator.Ry.value: cirq.ops.common_gates.Ry,
    PandoraGateTranslator.Rz.value: cirq.ops.common_gates.Rz,
    PandoraGateTranslator.XPowGate.value: cirq.XPowGate,
    PandoraGateTranslator.ZPowGate.value: cirq.ZPowGate,
    PandoraGateTranslator.YPowGate.value: cirq.YPowGate,
    PandoraGateTranslator.HPowGate.value: cirq.HPowGate,
    PandoraGateTranslator._PauliX.value: cirq.X,
    PandoraGateTranslator._PauliY.value: cirq.Z,
    PandoraGateTranslator._PauliZ.value: cirq.Y,
    PandoraGateTranslator.GlobalPhaseGate.value: cirq.GlobalPhaseGate,
    PandoraGateTranslator.ResetChannel.value: cirq.ResetChannel(),
    PandoraGateTranslator.In.value: In(),
    PandoraGateTranslator.Out.value: Out(),
    # only single qubit measurements supported for now
    PandoraGateTranslator.M.value: cirq.MeasurementGate(num_qubits=1),
    PandoraGateTranslator.CNOT.value: cirq.CX,
    PandoraGateTranslator.CZ.value: cirq.CZ,
    PandoraGateTranslator.CZPowGate.value: cirq.CZPowGate,
    PandoraGateTranslator.CXPowGate.value: cirq.CXPowGate,
    PandoraGateTranslator.XXPowGate.value: cirq.XXPowGate,
    PandoraGateTranslator.ZZPowGate.value: cirq.ZZPowGate,
    PandoraGateTranslator.Toffoli.value: cirq.CCX,
    PandoraGateTranslator.CCXPowGate.value: cirq.CCXPowGate,
    PandoraGateTranslator.And.value: And,
    PandoraGateTranslator.CSwapGate: cirq.CSwapGate
}

PANDORA_TO_READABLE = {
    PandoraGateTranslator.Rx.value: "Rx",
    PandoraGateTranslator.Ry.value: "Ry",
    PandoraGateTranslator.Rz.value: "Rz",
    PandoraGateTranslator.XPowGate.value: "X",
    PandoraGateTranslator.ZPowGate.value: "Z",
    PandoraGateTranslator.YPowGate.value: "Y",
    PandoraGateTranslator.HPowGate.value: "H",
    PandoraGateTranslator._PauliX.value: "X",
    PandoraGateTranslator._PauliY.value: "Y",
    PandoraGateTranslator._PauliZ.value: "Z",
    PandoraGateTranslator.GlobalPhaseGate.value: "global phase",
    PandoraGateTranslator.ResetChannel.value: "R",
    PandoraGateTranslator.In.value: "In",
    PandoraGateTranslator.Out.value: "Out",
    PandoraGateTranslator.M.value: "M",
    PandoraGateTranslator.CNOT.value: "CX",
    PandoraGateTranslator.CZ.value: "CZ",
    PandoraGateTranslator.CZPowGate.value: "CZ",
    PandoraGateTranslator.CXPowGate.value: "CX",
    PandoraGateTranslator.XXPowGate.value: "XX",
    PandoraGateTranslator.ZZPowGate.value: "ZZ",
    PandoraGateTranslator.Toffoli.value: "CCX",
    PandoraGateTranslator.And.value: "And",
    PandoraGateTranslator.CSwapGate.value: "CSwap",
    PandoraGateTranslator.CCXPowGate.value: "CCXp",
    PandoraGateTranslator.GlobalIn.value: "G_In",
    PandoraGateTranslator.GlobalOut.value: "G_Out",
}

SINGLE_QUBIT_GATES = [PandoraGateTranslator.Rx.value,
                      PandoraGateTranslator.Ry.value,
                      PandoraGateTranslator.Rz.value,
                      PandoraGateTranslator.XPowGate.value,
                      PandoraGateTranslator.ZPowGate.value,
                      PandoraGateTranslator.YPowGate.value,
                      PandoraGateTranslator.HPowGate.value,
                      PandoraGateTranslator._PauliX.value,
                      PandoraGateTranslator._PauliY.value,
                      PandoraGateTranslator._PauliZ.value,
                      PandoraGateTranslator.GlobalPhaseGate.value,
                      PandoraGateTranslator.ResetChannel.value,
                      PandoraGateTranslator.In.value,
                      PandoraGateTranslator.Out.value,
                      PandoraGateTranslator.M.value,
                      PandoraGateTranslator.S.value,
                      PandoraGateTranslator.S_dag.value,
                      PandoraGateTranslator.T.value,
                      PandoraGateTranslator.T_dag.value
                      ]

TWO_QUBIT_GATES = [PandoraGateTranslator.CNOT.value,
                   PandoraGateTranslator.CZ.value,
                   PandoraGateTranslator.Swap.value,
                   PandoraGateTranslator.CZPowGate.value,
                   PandoraGateTranslator.CXPowGate.value,
                   PandoraGateTranslator.XXPowGate.value,
                   PandoraGateTranslator.ZZPowGate.value]

THREE_QUBIT_GATES = [PandoraGateTranslator.Toffoli.value,
                     PandoraGateTranslator.And.value,
                     PandoraGateTranslator.CCXPowGate.value,
                     PandoraGateTranslator.CSwapGate.value]

REQUIRES_ROTATION = [PandoraGateTranslator.Rx.value,
                     PandoraGateTranslator.Ry.value,
                     PandoraGateTranslator.Rz.value]

REQUIRES_EXPONENT = [PandoraGateTranslator.XPowGate.value,
                     PandoraGateTranslator.YPowGate.value,
                     PandoraGateTranslator.ZPowGate.value,
                     PandoraGateTranslator.HPowGate.value,
                     PandoraGateTranslator.CZPowGate.value,
                     PandoraGateTranslator.CXPowGate.value,
                     PandoraGateTranslator.XXPowGate.value,
                     PandoraGateTranslator.ZZPowGate.value,
                     PandoraGateTranslator.CCXPowGate.value]


PYLIQTR_ROTATION_TO_PANDORA = {
    'rz_decomp': 'Rz',
    'ry_decomp': 'Ry',
    'rx_decomp': 'Rx'
}

CAN_HAVE_GLOBAL_SHIFT = REQUIRES_EXPONENT

CAN_HAVE_KEY = [PandoraGateTranslator.In.value,
                PandoraGateTranslator.Out.value,
                PandoraGateTranslator.M.value]

ALL_GATES = SINGLE_QUBIT_GATES + TWO_QUBIT_GATES + THREE_QUBIT_GATES

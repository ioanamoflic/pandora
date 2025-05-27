from abc import ABC
from enum import Enum
import cirq
import numpy as np
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


MAX_QUBITS_PER_GATE = 3
GLOBAL_IN_ID = -1
GLOBAL_OUT_ID = -2

KEEP_RZ = False

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
                      ]

TWO_QUBIT_GATES = [PandoraGateTranslator.CNOT.value,
                   PandoraGateTranslator.CZ.value,
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

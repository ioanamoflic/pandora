import math
from typing import Optional

from qiskit.circuit import CircuitInstruction, Measure

from pandora.translation.gates import PandoraGate
from pandora.translation.translator import (
    PandoraGateTranslator,
    QISKIT_TO_PANDORA,
    REQUIRES_EXPONENT,
)


class QiskitToPandoraTranslator:
    """
    Translator Qiskit CircuitInstruction -> PandoraGate.
    """

    def __init__(self):
        self.meas_key_dict: dict[str, int] = {}

    def translate(
        self,
        instr: CircuitInstruction,
        label: Optional[str] = None,
    ) -> PandoraGate:
        gate_code, parameter, global_shift, measurement_key = self._resolve_gate(instr)

        return PandoraGate(
            gate_code=gate_code,
            gate_parameter=parameter,
            switch=self._is_switched(instr),
            global_shift=global_shift,
            is_classically_controlled=self._is_classically_controlled(instr),
            measurement_key=measurement_key,
            label=label,
        )

    def _resolve_gate(
        self,
        instr: CircuitInstruction,
    ) -> tuple[int, float, float, Optional[int]]:
        op = instr.operation

        if isinstance(op, Measure):
            qubit_index = instr.qubits[0]._index
            key = f"m_{qubit_index}"

            if key not in self.meas_key_dict:
                self.meas_key_dict[key] = len(self.meas_key_dict)

            return (
                PandoraGateTranslator.M.value,
                0.0,
                0.0,
                self.meas_key_dict[key],
            )

        qiskit_name = op.name
        if qiskit_name not in QISKIT_TO_PANDORA:
            raise ValueError(f"Unsupported gate: {qiskit_name}")

        gate_code = QISKIT_TO_PANDORA[qiskit_name]
        if op.params:
            # Qiskit rotation gates take angles in radians, while Pandora takes them in multiples of pi, so we convert here.
            parameter = float(op.params[0] / math.pi)
        elif gate_code in REQUIRES_EXPONENT:
            parameter = 1.0
        else:
            parameter = 0.0

        global_shift = 0.0
        measurement_key = None

        return gate_code, parameter, global_shift, measurement_key

    @staticmethod
    def _is_switched(instr: CircuitInstruction) -> bool:
        qargs = instr.qubits
        if len(qargs) != 2:
            return False
        return qargs[0]._index < qargs[1]._index

    @staticmethod
    def _is_classically_controlled(instr: CircuitInstruction) -> bool:
        op = instr.operation
        return bool(getattr(op, "condition", None))

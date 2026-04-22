import cirq

from pandora.exceptions.exceptions import CirqGateHasNoPandoraEquivalent
from pandora.translation.gates import PandoraGate
from pandora.translation.translator import (
    PandoraGateTranslator,
    PYLIQTR_ROTATION_TO_PANDORA,
    REQUIRES_ROTATION,
    REQUIRES_EXPONENT
)


class CirqToPandoraTranslator:
    """
    Translator for Cirq operations -> PandoraGate.
    """

    def __init__(self):
        self.meas_key_dict: dict[str, int] = {}

    def translate(self, op: cirq.Operation, label: str | None = None) -> PandoraGate:
        gate, code, meas_key = self._resolve_gate(op)

        return PandoraGate(
            gate_code=code,
            gate_parameter=self._get_parameter(op, code),
            switch=self._is_switched(op),
            global_shift=self._get_global_shift(op, code),
            is_classically_controlled=self._is_classically_controlled(op),
            measurement_key=meas_key,
            label=label,
        )

    def _resolve_gate(self, op):
        gate = op.without_classical_controls().gate

        if isinstance(gate, cirq.MeasurementGate):
            key = gate.key
            if key not in self.meas_key_dict:
                self.meas_key_dict[key] = len(self.meas_key_dict)

            return gate, PandoraGateTranslator.M.value, self.meas_key_dict[key]

        name = gate.__class__.__name__

        if name in {"rx_decomp", "ry_decomp", "rz_decomp"}:
            name = PYLIQTR_ROTATION_TO_PANDORA[name]

        if name not in PandoraGateTranslator.__members__:
            raise CirqGateHasNoPandoraEquivalent(f"Unsupported gate: {name}")

        enum_value = getattr(PandoraGateTranslator, name).value
        return gate, enum_value, None

    @staticmethod
    def _is_switched(op):
        return len(op.qubits) == 2 and op.qubits[0] < op.qubits[1]

    @staticmethod
    def _is_classically_controlled(op):
        return len(op.classical_controls) > 0

    @staticmethod
    def _get_parameter(op, code):
        gate = op.gate
        if code in REQUIRES_ROTATION:
            return getattr(gate, "_rads", 0)

        if code in REQUIRES_EXPONENT:
            return gate.exponent

        return 0

    @staticmethod
    def _get_global_shift(op, code):
        if code in REQUIRES_EXPONENT:
            return getattr(op.gate, "global_shift", 0)
        return 0
from dataclasses import dataclass, asdict
from typing import Optional

import cirq
import numpy as np
import qiskit

from pandora.exceptions.exceptions import PandoraGateWrappedMissingQubits
from pandora.translation.translator import (
    PANDORA_TO_CIRQ,
    REQUIRES_ROTATION,
    REQUIRES_EXPONENT,
    CAN_HAVE_KEY,
    PANDORA_TO_QISKIT,
    IS_IO,
    PandoraGateTranslator,
)
from pandora.translation.link import LinkID


@dataclass
class PandoraGate:
    id: Optional[int] = None

    prev_q1: Optional[int] = None
    prev_q2: Optional[int] = None
    prev_q3: Optional[int] = None

    type: Optional[int] = None
    param: float = 0.0
    global_shift: float = 0.0
    switch: bool = False

    next_q1: Optional[int] = None
    next_q2: Optional[int] = None
    next_q3: Optional[int] = None

    visited: int = -1
    label: Optional[str] = None
    cl_ctrl: bool = False
    meas_key: Optional[int] = None
    qubit_name: Optional[str] = None

    def __init__(
        self,
        gate_id: Optional[int] = None,
        gate_code: Optional[int] = None,
        prev_q1: Optional[int] = None,
        prev_q2: Optional[int] = None,
        prev_q3: Optional[int] = None,
        gate_parameter: float = 0.0,
        global_shift: float = 0.0,
        switch: bool = False,
        next_q1: Optional[int] = None,
        next_q2: Optional[int] = None,
        next_q3: Optional[int] = None,
        visited: int = -1,
        label: Optional[str] = None,
        is_classically_controlled: bool = False,
        measurement_key: Optional[int] = None,
        qubit_name: Optional[str] = None,
    ):
        self.id = gate_id
        self.type = gate_code

        self.prev_q1 = prev_q1
        self.prev_q2 = prev_q2
        self.prev_q3 = prev_q3

        self.param = gate_parameter
        self.global_shift = global_shift
        self.switch = switch

        self.next_q1 = next_q1
        self.next_q2 = next_q2
        self.next_q3 = next_q3

        self.visited = visited
        self.label = label
        self.cl_ctrl = is_classically_controlled
        self.meas_key = measurement_key
        self.qubit_name = qubit_name

    @classmethod
    def from_db_row(cls, row):
        return cls(
            gate_id=row[0],
            prev_q1=row[1],
            prev_q2=row[2],
            prev_q3=row[3],
            gate_code=row[4],
            gate_parameter=row[5],
            global_shift=row[6],
            switch=row[7],
            next_q1=row[8],
            next_q2=row[9],
            next_q3=row[10],
            visited=row[11],
            label=row[12],
            is_classically_controlled=row[13],
            measurement_key=row[14],
            qubit_name=row[15] if len(row) > 15 else None,
        )

    def with_stripped_links(self):
        return PandoraGate(
            gate_id=self.id,
            prev_q1=LinkID.strip_type(self.prev_q1),
            prev_q2=LinkID.strip_type(self.prev_q2),
            prev_q3=LinkID.strip_type(self.prev_q3),
            gate_code=self.type,
            gate_parameter=self.param,
            global_shift=self.global_shift,
            switch=self.switch,
            next_q1=LinkID.strip_type(self.next_q1),
            next_q2=LinkID.strip_type(self.next_q2),
            next_q3=LinkID.strip_type(self.next_q3),
            visited=self.visited,
            label=self.label,
            is_classically_controlled=self.cl_ctrl,
            measurement_key=self.meas_key,
            qubit_name=self.qubit_name,
        )

    def links_prev(self):
        return [self.prev_q1, self.prev_q2, self.prev_q3]

    def links_next(self):
        return [self.next_q1, self.next_q2, self.next_q3]

    def to_tuple(self, include_test_fields: bool = False):
        base = (
            self.id,
            self.prev_q1,
            self.prev_q2,
            self.prev_q3,
            self.type,
            self.param,
            self.global_shift,
            self.switch,
            self.next_q1,
            self.next_q2,
            self.next_q3,
            self.visited,
            self.label,
            self.cl_ctrl,
            self.meas_key,
        )

        if include_test_fields:
            return base + (self.qubit_name,)
        return base

    def __repr__(self):
        return (
            f"PandoraGate(id={self.id}, type={self.type}, "
            f"prev={self.links_prev()}, next={self.links_next()})"
        )


class PandoraGateWrapper:

    def __init__(self, gate: PandoraGate):
        self.gate = gate

        self.q1 = None
        self.q2 = None
        self.q3 = None
        self.moment = -1

    @property
    def prev_id1(self):
        return self._link_to_gate_id(self.gate.prev_q1)

    @property
    def prev_id2(self):
        return self._link_to_gate_id(self.gate.prev_q2)

    @property
    def prev_id3(self):
        return self._link_to_gate_id(self.gate.prev_q3)

    @property
    def next_id1(self):
        return self._link_to_gate_id(self.gate.next_q1)

    @property
    def next_id2(self):
        return self._link_to_gate_id(self.gate.next_q2)

    @property
    def next_id3(self):
        return self._link_to_gate_id(self.gate.next_q3)

    @staticmethod
    def _link_to_gate_id(link):
        return None if link is None else LinkID.stripped_gate_id(link)

    def qubits(self):
        return [q for q in (self.q1, self.q2, self.q3) if q is not None]

    def get_gate_qubits(self, qubit_list):
        qs = self.qubits()

        if not qs:
            raise PandoraGateWrappedMissingQubits(
                f"No qubits assigned for gate {self.gate.id}"
            )

        return [qubit_list[q] for q in qs]

    def to_cirq_operation(self):
        gate_type = self.gate.type
        base = PANDORA_TO_CIRQ[gate_type]

        if gate_type in REQUIRES_ROTATION:
            op = base(rads=self.gate.param * np.pi)

        elif gate_type in REQUIRES_EXPONENT:
            op = base(
                exponent=self.gate.param,
                global_shift=self.gate.global_shift,
            )

        else:
            op = base

        if gate_type == PandoraGateTranslator.M.value:
            return cirq.MeasurementGate(
                num_qubits=1,
                key=str(self.gate.meas_key),
            )

        if gate_type in CAN_HAVE_KEY and self.gate.meas_key is not None:
            op = op.with_key(str(self.gate.meas_key))

        return op

    def to_cirq_op(self, qubit_list) -> cirq.Operation:
        return self.to_cirq_operation().on(*self.get_gate_qubits(qubit_list))

    def to_qiskit_gate(self):
        gate_type = self.gate.type
        cls = PANDORA_TO_QISKIT[gate_type]

        if gate_type in REQUIRES_ROTATION:
            # Pandora params are multiples of pi, but Qiskit uses radians
            return cls(self.gate.param * np.pi)

        # The pow and rotation gates are equal up to a global phase
        elif gate_type in REQUIRES_EXPONENT and self.gate.param == 1:
            return cls()
        elif gate_type == PandoraGateTranslator.XPowGate.value:
            return qiskit.circuit.library.RXGate(self.gate.param * np.pi)
        elif gate_type == PandoraGateTranslator.YPowGate.value:
            return qiskit.circuit.library.RYGate(self.gate.param * np.pi)
        elif gate_type == PandoraGateTranslator.ZPowGate.value:
            return qiskit.circuit.library.RZGate(self.gate.param * np.pi)

        elif gate_type in REQUIRES_EXPONENT:
            raise NotImplementedError(
                f"Qiskit gate {cls} with exponent {self.gate.param} not implemented"
            )

        if gate_type in IS_IO:
            return cls

        return cls()

    def __repr__(self):
        return f"Wrapper(type={self.gate.type}, q={self.qubits()}, moment={self.moment})"

    def __str__(self):
        return f"{self.gate.type}({self.q1}, {self.q2}, {self.q3})"


@dataclass
class PandoraGateLayer:

    def __init__(
            self,
            id: int = None,
            control_q: int = None,
            target_q: int = None,
            type: int = None,
            param: float = None,
            layer: int = None, ):
        self.id = id
        self.control_q = control_q
        self.target_q = target_q
        self.type = type
        self.param = param
        self.layer = layer

    @classmethod
    def from_pandora_wrapped(cls, pandora_wrapped: PandoraGateWrapper):
        assert isinstance(pandora_wrapped, PandoraGateWrapper)

        if pandora_wrapped.q3 is not None:
            raise "LSCOM only supports < 3 qubit-gates!"

        return cls(
            id=pandora_wrapped.gate.id,
            control_q=pandora_wrapped.q1,
            target_q=pandora_wrapped.q2,
            type=pandora_wrapped.gate.type,
            param=pandora_wrapped.gate.param,
            layer=pandora_wrapped.moment)

    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row[0],
            control_q=row[1],
            target_q=row[2],
            type=row[3],
            param=row[4],
            layer=row[5]
        )

    def to_tuple(self):
        base = (
            self.id,
            self.control_q,
            self.target_q,
            self.type,
            self.param,
            self.layer,
        )
        return base



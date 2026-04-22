from typing import Iterator, Union, Iterable

import cirq
import qiskit

from pandora.exceptions.exceptions import (
    WindowSizeError,
    WrongPandoraBuilderInput,
)
from pandora.translation.cirq_translator import CirqToPandoraTranslator
from pandora.translation.qiskit_translator import QiskitToPandoraTranslator

from pandora.translation.translator import (
    PandoraGateTranslator,
    MAX_QUBITS_PER_GATE,
    SINGLE_QUBIT_GATES,
    TWO_QUBIT_GATES,
)

from pandora.translation.gates import PandoraGate
from pandora.translation.link import LinkID


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


class PandoraWindowedBuilder:
    """
    Single builder that supports:
        - full circuits
        - op lists
        - streaming batches

    It maintains state across calls and can emit gates in windows.
    """

    def __init__(self, label=None, window_size: int = 1000):
        if window_size <= 1:
            raise WindowSizeError

        self.label = label
        self.window_size = window_size

        self.last_id = 0
        self.gates: dict[int, PandoraGate] = {}
        self.latest = {}

        self.buffer: list[PandoraGate] = []
        self.emitted_ids: set[int] = set()

        self.meas_key_dict = {}
        self.translator = None

    def consume(
        self,
        data: Union[qiskit.QuantumCircuit, cirq.Circuit, Iterable],
    ) -> Iterator[list[PandoraGate]]:
        ops = self._normalize_input(data)

        for op in ops:
            self._process(op)

            if len(self.buffer) >= self.window_size:
                yield self._flush()

    def finalize(self) -> list[PandoraGate]:
        self._append_out_gates()
        return self._flush()

    def _normalize_input(
        self,
        data: Union[qiskit.QuantumCircuit, cirq.Circuit, Iterable],
    ) -> Iterable:
        if isinstance(data, cirq.Circuit):
            self.translator = CirqToPandoraTranslator()
            return data.all_operations()

        if isinstance(data, qiskit.QuantumCircuit):
            self.translator = QiskitToPandoraTranslator()
            return data.data

        if isinstance(data, Iterable):
            return data

        raise WrongPandoraBuilderInput

    @staticmethod
    def _get_qubits(op) -> tuple:
        return tuple(op.qubits)  # same for cirq and qiskit

    def _process(self, op) -> None:
        self._ensure_inputs(op)
        gate = self.translator.translate(op, label=self.label)

        gate_id = self._new_id()
        gate.id = gate_id

        self._set_prev(gate, op)
        completed = self._set_next(gate, op, gate_id)

        self.gates[gate_id] = gate
        self.buffer.extend(completed)

    def _ensure_inputs(self, op) -> None:
        for q in self._get_qubits(op):
            if q in self.latest:
                continue

            gid = self._new_id()
            in_type = PandoraGateTranslator.In.value

            self.gates[gid] = PandoraGate(
                gate_id=gid,
                gate_code=in_type,
                label=self.label,
            )

            self.latest[q] = LinkID.encode(gid, 0, in_type)

    @staticmethod
    def _is_complete(g: PandoraGate):
        if g.type in SINGLE_QUBIT_GATES:
            return g.next_q1 is not None

        if g.type in TWO_QUBIT_GATES:
            return g.next_q1 is not None and g.next_q2 is not None

        return True

    def _set_prev(self, gate: PandoraGate, op) -> None:
        prev = [self.latest[q] for q in self._get_qubits(op)]

        while len(prev) < MAX_QUBITS_PER_GATE:
            prev.append(None)

        gate.prev_q1, gate.prev_q2, gate.prev_q3 = prev

    def _emit_once(self, gate: PandoraGate) -> None:
        if gate.id not in self.emitted_ids:
            self.buffer.append(gate)
            self.emitted_ids.add(gate.id)

    def _set_next(self, gate: PandoraGate, op, gate_id: int):
        completed = []

        for idx, q in enumerate(self._get_qubits(op)):
            prev_link = self.latest[q]
            prev_id = LinkID.gate_id(prev_link)
            prev_port = LinkID.port(prev_link)

            prev_gate = self.gates[prev_id]

            new_link = LinkID.encode(gate_id, idx, gate.type)
            setattr(prev_gate, f"next_q{prev_port + 1}", new_link)

            if self._is_complete(prev_gate) and prev_gate.id not in self.emitted_ids:
                completed.append(prev_gate)
                self.emitted_ids.add(prev_gate.id)

            self.latest[q] = new_link

        return completed

    def _append_out_gates(self) -> None:
        for _, last_link in self.latest.items():
            gid = self._new_id()
            out_type = PandoraGateTranslator.Out.value

            out_gate = PandoraGate(
                gate_id=gid,
                gate_code=out_type,
                label=self.label,
            )

            prev_id = LinkID.gate_id(last_link)
            prev_port = LinkID.port(last_link)
            prev_gate = self.gates[prev_id]

            next_link = LinkID.encode(gid, 0, out_type)
            setattr(prev_gate, f"next_q{prev_port + 1}", next_link)

            out_gate.prev_q1 = last_link
            self.gates[gid] = out_gate

            if self._is_complete(prev_gate):
                self._emit_once(prev_gate)

            self._emit_once(out_gate)

    def _flush(self) -> list[PandoraGate]:
        out = self.buffer
        self.buffer = []
        return out

    def _new_id(self) -> int:
        gid = self.last_id
        self.last_id += 1
        return gid

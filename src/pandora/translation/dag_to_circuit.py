from typing import List

import cirq
import qiskit

from collections import defaultdict, deque

from pandora.exceptions.exceptions import (
    PandoraGateOrderingError,
    PandoraWrappedGateMissingLinks,
    PandoraGateWrappedMissingQubits,
)
from pandora.translation.translator import (
    SINGLE_QUBIT_GATES,
    TWO_QUBIT_GATES,
    PandoraGateTranslator,
)
from pandora.translation.gates import (
    PandoraGate,
    PandoraGateWrapper,
    PandoraGateLayer
)
from pandora.translation.link import LinkID


class PandoraDAG:
    def __init__(self, wrapped: dict[int, PandoraGateWrapper]):
        self.wrapped = wrapped
        self.graph = defaultdict(list)
        self.indegree = defaultdict(int)
        self._build()

    def _build(self):
        for w in self.wrapped.values():
            for prev_id in (w.prev_id1, w.prev_id2):
                if prev_id is None:
                    continue

                if prev_id not in self.wrapped:
                    raise PandoraGateOrderingError(
                        f"Missing dependency: {prev_id} for gate {w.gate.id}"
                    )

                self.graph[prev_id].append(w.gate.id)
                self.indegree[w.gate.id] += 1

            self.indegree.setdefault(w.gate.id, 0)

    def schedule(self):
        q = deque()
        moment = {gid: 0 for gid in self.wrapped}

        for gid, deg in self.indegree.items():
            if deg == 0:
                q.append(gid)

        topo = []

        while q:
            node = q.popleft()
            topo.append(node)

            for child in self.graph[node]:
                moment[child] = max(moment[child], moment[node] + 1)

                self.indegree[child] -= 1
                if self.indegree[child] == 0:
                    q.append(child)

        if len(topo) != len(self.wrapped):
            raise ValueError("Cycle detected in Pandora DAG")

        return topo, moment


class PandoraGateWrapperBuilder:
    def __init__(self, gates: list[PandoraGate]):
        self.topo: list[int] = []
        self.gates = gates
        self.wrapped = {g.id: PandoraGateWrapper(gate=g) for g in gates}
        self.dag = PandoraDAG(self.wrapped)

    def build(self) -> dict[int, PandoraGateWrapper]:
        topo, moment = self.dag.schedule()
        self.topo = topo

        for gid in topo:
            w = self.wrapped[gid]
            w.moment = moment[gid]

            if w.gate.type == PandoraGateTranslator.In.value:
                w.moment = 0

        return self.wrapped


class PandoraCircuitReconstructor:
    def __init__(self, gates: list[PandoraGate]):
        self.gates = gates
        self.wrapper_builder = PandoraGateWrapperBuilder(gates)
        self.wrapped_map = self.wrapper_builder.build()
        self.n_qubits = self._n_qubits()

    def to_cirq(self) -> cirq.Circuit:
        wrapped = self._resolve_qubits()
        return self._to_cirq(wrapped, self.n_qubits)

    def to_qiskit(self) -> qiskit.QuantumCircuit:
        wrapped = self._resolve_qubits()
        return self._to_qiskit(wrapped, self.n_qubits)

    def to_lscom(self) -> List[PandoraGateLayer]:
        wrapped = self._resolve_qubits()
        return self._to_lscom(wrapped)

    def _n_qubits(self) -> int:
        return sum(1 for g in self.gates if g.type == PandoraGateTranslator.In.value)

    def _resolve_qubits(self) -> list[PandoraGateWrapper]:
        wrapped = self.wrapped_map
        topo = self.wrapper_builder.topo

        next_qubit = 0
        for gid in topo:
            w = wrapped[gid]
            if w.gate.type == PandoraGateTranslator.In.value:
                w.q1 = next_qubit
                next_qubit += 1

        for gid in topo:
            self._assign_qubits(wrapped[gid], wrapped)

        return [wrapped[gid] for gid in topo]

    def _assign_qubits(
        self,
        w: PandoraGateWrapper,
        wrapped: dict[int, PandoraGateWrapper],
    ) -> None:
        gate_type = w.gate.type

        if gate_type == PandoraGateTranslator.In.value:
            return

        if gate_type in SINGLE_QUBIT_GATES:
            self._assign_single_qubit(w, wrapped)
            return

        if gate_type in TWO_QUBIT_GATES:
            self._assign_two_qubit(w, wrapped)
            return

        raise NotImplementedError(
            f"Reconstruction for gate type {gate_type} is not supported"
        )

    @staticmethod
    def _qubit_from_port(prev: PandoraGateWrapper, prev_link: int, gate_id: int) -> int:
        if prev_link is None:
            raise PandoraGateWrappedMissingQubits(
                f"Gate {gate_id} is missing a predecessor link"
            )

        port = LinkID.stripped_port(prev_link)

        if port == 0:
            q = prev.q1
        elif port == 1:
            q = prev.q2
        elif port == 2:
            q = prev.q3
        else:
            raise PandoraGateWrappedMissingQubits(
                f"Invalid predecessor port {port} for gate {gate_id}"
            )

        if q is None:
            raise PandoraGateWrappedMissingQubits(
                f"Predecessor qubit not assigned for gate {gate_id}"
            )

        return q

    def _assign_single_qubit(
        self,
        w: PandoraGateWrapper,
        wrapped: dict[int, PandoraGateWrapper],
    ) -> None:
        if w.prev_id1 is None:
            raise PandoraGateWrappedMissingQubits(
                f"Single-qubit gate {w.gate.id} has no predecessor"
            )

        prev = wrapped[w.prev_id1]
        w.q1 = self._qubit_from_port(prev, w.gate.prev_q1, w.gate.id)

    def _assign_two_qubit(
        self,
        w: PandoraGateWrapper,
        wrapped: dict[int, PandoraGateWrapper],
    ) -> None:
        if w.prev_id1 is None or w.prev_id2 is None:
            raise PandoraGateWrappedMissingQubits(
                f"Two-qubit gate {w.gate.id} is missing predecessors"
            )

        prev1 = wrapped[w.prev_id1]
        prev2 = wrapped[w.prev_id2]

        w.q1 = self._qubit_from_port(prev1, w.gate.prev_q1, w.gate.id)
        w.q2 = self._qubit_from_port(prev2, w.gate.prev_q2, w.gate.id)

    @staticmethod
    def _to_cirq(wrapped: list[PandoraGateWrapper], n_qubits: int) -> cirq.Circuit:
        circuit = cirq.Circuit()
        q = [cirq.NamedQubit(str(i)) for i in range(n_qubits)]

        for w in wrapped:
            if w.prev_id1 is None and w.next_id1 is None:
                raise PandoraWrappedGateMissingLinks

            op = w.to_cirq_operation()
            qubits = w.get_gate_qubits(q)
            circuit.append(op.on(*qubits))

        return circuit

    @staticmethod
    def _to_qiskit(wrapped: list[PandoraGateWrapper], n_qubits: int) -> qiskit.QuantumCircuit:
        circuit = qiskit.QuantumCircuit(n_qubits)
        q = list(range(n_qubits))

        for w in wrapped:
            if w.prev_id1 is None and w.next_id1 is None:
                raise PandoraWrappedGateMissingLinks

            gate = w.to_qiskit_gate()
            qubits = w.get_gate_qubits(q)
            circuit.append(gate, qubits)

        return circuit

    @staticmethod
    def _to_lscom(wrapped: list[PandoraGateWrapper]) -> List[PandoraGateLayer]:
        gates = []

        for w in wrapped:
            if w.prev_id1 is None and w.next_id1 is None:
                raise PandoraWrappedGateMissingLinks

            gates.append(PandoraGateLayer.from_pandora_wrapped(pandora_wrapped=w))

        return gates


def pandora_to_circuit(
    pandora_gates: list[PandoraGate],
    circuit_type: str = "cirq"
):
    normalized_gates = [g.with_stripped_links() for g in pandora_gates]
    recon = PandoraCircuitReconstructor(normalized_gates)

    if circuit_type == "cirq":
        return recon.to_cirq()

    if circuit_type == 'qiskit':
        return recon.to_qiskit()

    if circuit_type == "lscom":
        return recon.to_lscom()

    return None

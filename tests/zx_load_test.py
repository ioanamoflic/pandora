from dataclasses import dataclass
import pytest
import pytest_asyncio
import pyzx
import qiskit
import qiskit.qasm2
from qiskit import QuantumCircuit

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.translation.gates import PandoraGate
from pandora.translation.translator import PandoraGateTranslator
from pandora.translation.pyzx import read_to_pyzx_graph

config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}

def make_link(vertex_id: int, port: int = 0, link_type: int = 0) -> int:
    return vertex_id * 1000 + port * 100 + link_type

def unpack_link(link: int) -> tuple[int, int, int]:
    vertex_id = link // 1000
    remainder = link % 1000
    port = remainder // 100
    link_type = remainder % 100
    return vertex_id, port, link_type

@dataclass(frozen=True)
class GateSpec:
    gate_type: PandoraGateTranslator
    qubits: tuple[int, ...]
    param: float = 0.0

def simple_circ(num_qubits: int, specs: list[GateSpec]) -> list[PandoraGate]:
    gates: list[PandoraGate] = []
    gates_by_id: dict[int, PandoraGate] = {}
    tails: dict[int, int] = {}
    next_gate_id = 1

    def add_gate(*, gate_code: int, **kwargs) -> PandoraGate:
        nonlocal next_gate_id

        gate = PandoraGate(gate_id=next_gate_id,gate_code=gate_code,**kwargs)

        next_gate_id += 1
        gates.append(gate)
        gates_by_id[gate.id] = gate
        return gate

    def connect(prev_link: int, new_gate: PandoraGate, new_gate_qubit_index: int) -> None:
        prev_gate_id, prev_gate_qubit_index, _prev_gate_code = unpack_link(prev_link)
        prev_gate = gates_by_id[prev_gate_id]

        next_link = make_link(new_gate.id, new_gate_qubit_index, new_gate.type)

        next_field = ("next_q1", "next_q2", "next_q3")[prev_gate_qubit_index]
        setattr(prev_gate, next_field, next_link)

    def add_input(qubit: int) -> None:
        gate = add_gate(gate_code=PandoraGateTranslator.In.value)
        tails[qubit] = make_link(gate.id, 0, gate.type)

    def add_output(qubit: int) -> None:
        gate_code = PandoraGateTranslator.Out.value
        prev_q1 = tails[qubit]

        gate = add_gate(gate_code=gate_code, prev_q1=prev_q1)

        connect(prev_q1, gate, 0)
        tails[qubit] = make_link(gate.id, 0, gate_code)

    def add_spec(spec: GateSpec) -> None:
        gate_code = spec.gate_type.value

        if len(spec.qubits) == 1:
            q = spec.qubits[0]
            prev_q1 = tails[q]

            gate = add_gate(gate_code=gate_code, prev_q1=prev_q1, gate_parameter=spec.param)

            connect(prev_q1, gate, 0)
            tails[q] = make_link(gate.id, 0, gate_code)
            return

        if len(spec.qubits) == 2:
            q1, q2 = spec.qubits
            prev_q1 = tails[q1]
            prev_q2 = tails[q2]

            gate = add_gate(gate_code=gate_code, prev_q1=prev_q1, prev_q2=prev_q2, gate_parameter=spec.param)

            connect(prev_q1, gate, 0)
            connect(prev_q2, gate, 1)

            tails[q1] = make_link(gate.id, 0, gate_code)
            tails[q2] = make_link(gate.id, 1, gate_code)
            return

        raise ValueError(f"Unsupported gate arity: {spec}")

    for qubit in range(num_qubits):
        add_input(qubit)

    for spec in specs:
        add_spec(spec)

    for qubit in range(num_qubits):
        add_output(qubit)

    return gates

@pytest_asyncio.fixture
async def setup():
    db = PandoraDB(config_file)
    await db.connect()
    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)
        yield db, repo, service
    finally:
        await db.close()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "gates",
    [
        pytest.param(
            simple_circ(
                3,
                [
                    GateSpec(PandoraGateTranslator.Rx, (0,), 0.125),
                    GateSpec(PandoraGateTranslator.XPowGate, (1,), -0.75),
                    GateSpec(PandoraGateTranslator._PauliX, (2,)),
                ],
            ),
            id="x-family",
        ),
        pytest.param(
            simple_circ(
                3,
                [
                    GateSpec(PandoraGateTranslator.Ry, (0,), 0.2),
                    GateSpec(PandoraGateTranslator.YPowGate, (1,), -0.6),
                    GateSpec(PandoraGateTranslator._PauliY, (2,)),
                ],
            ),
            id="y-family",
        ),
        pytest.param(
            simple_circ(
                3,
                [
                    GateSpec(PandoraGateTranslator.Rz, (0,), 0.375),
                    GateSpec(PandoraGateTranslator.ZPowGate, (1,), -0.625),
                    GateSpec(PandoraGateTranslator._PauliZ, (2,)),
                ],
            ),
            id="z-family",
        ),
        pytest.param(
            simple_circ(
                2,
                [
                    GateSpec(PandoraGateTranslator.CNOT, (0, 1), 1.0),
                    GateSpec(PandoraGateTranslator.CZ, (0, 1), 1.0),
                    GateSpec(PandoraGateTranslator.CXPowGate, (0, 1), 1.0),
                    GateSpec(PandoraGateTranslator.CZPowGate, (0, 1), 1.0),
                    GateSpec(PandoraGateTranslator.Swap, (0, 1), 1.0),
                ],
            ),
            id="two-qubit",
        ),
    ],
)
async def test_zx_load_simple(setup, gates):
    db, repo, service = setup

    await service.build_pandora()
    await repo.insert_copy(gates)
    await service.convert_linked_circuit_to_zx()

    async with db.acquire() as conn:
        expected = await read_to_pyzx_graph(conn)

    circuit = await service.load_circuit(circuit_type="qiskit")
    pyzx_orig_circ = pyzx.Circuit.from_qasm(qiskit.qasm2.dumps(circuit))
    actual = pyzx_orig_circ.to_graph()

    assert len(list(actual.vertices())) == len(list(expected.vertices()))
    assert len(list(actual.edges())) == len(list(expected.edges()))
    assert len(list(actual.inputs())) == len(list(expected.inputs()))
    assert len(list(actual.outputs())) == len(list(expected.outputs()))

    assert pyzx.compare_tensors(actual, expected)


@pytest.mark.asyncio
async def test_zx_load_simple_qiskit(setup):
    db, repo, service = setup

    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    await service.build_circuit(circuit=circuit.copy())
    await service.convert_linked_circuit_to_zx()
    async with db.acquire() as conn:
        expected = await read_to_pyzx_graph(conn)

    circuit = await service.load_circuit(circuit_type="qiskit")
    pyzx_orig_circ = pyzx.Circuit.from_qasm(qiskit.qasm2.dumps(circuit))
    actual = pyzx_orig_circ.to_graph()

    assert len(list(actual.vertices())) == len(list(expected.vertices()))
    assert len(list(actual.edges())) == len(list(expected.edges()))
    assert len(list(actual.inputs())) == len(list(expected.inputs()))
    assert len(list(actual.outputs())) == len(list(expected.outputs()))

    assert pyzx.compare_tensors(actual, expected)


@pytest.mark.asyncio
async def test_zx_load_toffoli(setup):
    db, repo, service = setup

    circuit = QuantumCircuit(3)
    circuit.ccx(0, 1, 2)
    await service.build_circuit(circuit=circuit.copy())
    await service.convert_linked_circuit_to_zx()
    async with db.acquire() as conn:
        expected = await read_to_pyzx_graph(conn)

    pyzx_orig_circ = pyzx.Circuit.from_qasm(qiskit.qasm2.dumps(circuit))
    actual = pyzx_orig_circ.to_graph()
    
    # No vertices / edges size assertions as zx_load should decompose the toffoli
    
    assert pyzx.compare_tensors(actual, expected);

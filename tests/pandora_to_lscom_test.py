import cirq
import pytest

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository, GateLayerRepository
from pandora.db.service import PandoraService
from pandora.util.circuit_util import remove_io_gates
from pandora.util.lscom_util import pandora_gate_layers_to_cirq
from pandora.util.test_util import assert_same_up_to_qubit_permutation

WINDOW_SIZE = 2
LABEL = 0
config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}


@pytest.mark.asyncio
async def test_lscom_reconstruction():
    q = [cirq.NamedQubit('0'), cirq.NamedQubit('1')]

    dummy_state = cirq.Circuit(
        cirq.H(q[0]),
        cirq.CX(q[0], q[1]),
        cirq.CX(q[0], q[1])
    )

    db = PandoraDB(config_file)
    await db.connect()

    repo = GateRepository(db)
    repo_layer = GateLayerRepository(db)

    service = PandoraService(db=db, repo=repo, repo_layered=repo_layer)

    await service.build_circuit(
        circuit=dummy_state
    )

    await service.load_circuit_into_layered()

    extracted_layered_gates = await service.load_circuit_from_layered()

    await db.close()

    extracted_circuit = remove_io_gates(pandora_gate_layers_to_cirq(extracted_layered_gates))

    assert_same_up_to_qubit_permutation(expected=dummy_state, actual=extracted_circuit)

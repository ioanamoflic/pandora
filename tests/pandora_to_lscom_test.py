import pytest

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository, GateLayerRepository
from pandora.db.service import PandoraService
from pandora.util.circuit_util import (
    remove_io_gates,
    get_adder_as_cirq_circuit,
    remove_measurements,
    remove_classically_controlled_ops
)
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
async def test_lscom_adder_reconstruction():

    full_adder_circuit = get_adder_as_cirq_circuit(n_bits=3)

    full_adder_circuit = remove_measurements(
        remove_classically_controlled_ops(full_adder_circuit)
    )

    db = PandoraDB(config_file)
    await db.connect()

    repo = GateRepository(db)
    repo_layer = GateLayerRepository(db)

    service = PandoraService(db=db, repo=repo, repo_layered=repo_layer)

    await service.build_circuit(
        circuit=full_adder_circuit
    )

    await service.load_circuit_into_layered()

    extracted_layered_gates = await service.load_circuit_from_layered()

    await db.close()

    extracted_circuit = remove_io_gates(pandora_gate_layers_to_cirq(extracted_layered_gates))

    assert_same_up_to_qubit_permutation(expected=full_adder_circuit, actual=extracted_circuit)

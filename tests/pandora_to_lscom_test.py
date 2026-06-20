import pytest

from benchmarking.benchmark_adders import replace_all_toffolis_qiskit, get_adder
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository, GateLayerRepository
from pandora.db.service import PandoraService
from pandora.util.circuit_util import (
    remove_io_gates,
    get_adder_as_cirq_circuit,
    remove_measurements,
    remove_classically_controlled_ops
)
from pandora.util.lscom_util import (
    pandora_gate_layers_to_cirq,
    pandora_gate_layers_to_qiskit
)
from pandora.util.test_util import assert_same_up_to_qubit_permutation, assert_same_up_to_qubit_permutation_qiskit

WINDOW_SIZE = 2
LABEL = 0


@pytest.mark.asyncio
async def test_lscom_adder_reconstruction():

    full_adder_circuit = get_adder_as_cirq_circuit(n_bits=3)

    full_adder_circuit = remove_measurements(
        remove_classically_controlled_ops(full_adder_circuit)
    )

    db = PandoraDB()
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


@pytest.mark.asyncio
async def test_lscom_adder_reconstruction_v2():
    adder_circuit = replace_all_toffolis_qiskit(get_adder(n_bits=1))

    db = PandoraDB()
    await db.connect()

    repo = GateRepository(db)
    repo_layer = GateLayerRepository(db)

    service = PandoraService(db=db, repo=repo, repo_layered=repo_layer)

    await service.build_circuit(
        circuit=adder_circuit
    )

    await service.load_circuit_into_layered()

    extracted_layered_gates = await service.load_circuit_from_layered()

    await db.close()

    extracted_circuit = remove_io_gates(pandora_gate_layers_to_qiskit(extracted_layered_gates), type='qiskit')

    assert_same_up_to_qubit_permutation_qiskit(expected=adder_circuit, actual=extracted_circuit)

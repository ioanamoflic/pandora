import pytest
import cirq
import itertools

from benchmarking import cirq_util
from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

from pandora.translation.dag_to_circuit import pandora_to_circuit
from pandora.util.circuit_util import (
    get_adder_as_cirq_circuit,
    remove_io_gates,
    remove_measurements,
    remove_classically_controlled_ops
)

WINDOW_SIZE = 2  # just to be extreme :)
LABEL = 0
config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}


def assert_same_up_to_qubit_permutation(expected: cirq.Circuit, actual: cirq.Circuit):
    """
    Obviously this has horrendous time complexity.
    """
    expected_qubits = sorted(expected.all_qubits())
    actual_qubits = sorted(actual.all_qubits())

    assert len(expected_qubits) == len(actual_qubits), (
        f"Different qubit counts: {len(expected_qubits)} != {len(actual_qubits)}"
    )

    for perm in itertools.permutations(actual_qubits):
        qubit_map = dict(zip(perm, expected_qubits))
        remapped = actual.transform_qubits(qubit_map)
        try:
            cirq.testing.assert_same_circuits(expected, remapped)
            return
        except AssertionError:
            pass

    raise AssertionError("Circuits are not equal up to qubit permutation")


def test_simple_reconstruction():
    q = [cirq.NamedQubit('0'), cirq.NamedQubit('1')]

    bell_state = cirq.Circuit(
        cirq.H(q[0]),
        cirq.CX(q[0], q[1]),
        cirq.CX(q[0], q[1])
    )

    builder = PandoraWindowedBuilder(window_size=WINDOW_SIZE, label=LABEL)

    gates = []
    for batch in builder.consume(bell_state):
        gates.extend(batch)

    gates.extend(builder.finalize())

    recon = pandora_to_circuit(pandora_gates=gates)
    recon = remove_io_gates(recon)

    cirq.testing.assert_same_circuits(bell_state, recon)


def test_random_reconstruction(n_circuits=100):
    templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t']

    for i in range(n_circuits):

        print(f'Random test {i}')

        rand = cirq_util.create_random_circuit(
            n_qubits=4,
            n_templates=15,
            templates=templates
        )

        builder = PandoraWindowedBuilder(window_size=WINDOW_SIZE, label=LABEL)

        gates = []
        for batch in builder.consume(rand):
            gates.extend(batch)

        gates.extend(builder.finalize())

        recon = pandora_to_circuit(pandora_gates=gates)
        recon = remove_io_gates(recon)

        assert_same_up_to_qubit_permutation(expected=rand, actual=recon)
        print("Test passed!")


@pytest.mark.asyncio
async def test_qualtran_adder_reconstruction():
    for n_bits in range(2, 4):
        print(f'Adder test {n_bits}')

        full_adder_circuit = get_adder_as_cirq_circuit(n_bits=n_bits)

        full_adder_circuit = remove_measurements(
            remove_classically_controlled_ops(full_adder_circuit)
        )

        print(full_adder_circuit)

        db = PandoraDB(config_file)
        await db.connect()

        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=full_adder_circuit
        )

        extracted_circuit = await service.load_circuit(circuit_type='cirq')

        await db.close()

        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=full_adder_circuit, actual=extracted_circuit)
        print(f'Passed adder({n_bits})!')

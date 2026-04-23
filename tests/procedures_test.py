import random

import cirq
import pytest

from benchmarking import benchmark_cirq
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.optimisation.optimiser import PandoraOptimiser
from pandora.translation.translator import PandoraGateTranslator
from pandora.util.circuit_util import remove_io_gates
from pandora.util.test_util import assert_same_up_to_qubit_permutation, count_t_gates, \
    assert_logically_equivalent_up_to_qubit_permutation

H = PandoraGateTranslator.HPowGate
CX = PandoraGateTranslator.CXPowGate
ZPow = PandoraGateTranslator.ZPowGate
PauliX = PandoraGateTranslator._PauliX
PauliZ = PandoraGateTranslator._PauliZ


config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_cancel_single_qubit(pass_count, timeout):

    qubit = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit(
        [
            cirq.H.on(qubit),
            cirq.H.on(qubit)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )

        optimiser.cancel_single_qubit_gates(
            gate_types=(H, H),
            gate_params=(1, 1),
            dedicated_nproc=1,
        )
        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        assert len(extracted_circuit) - 2 == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_cancel_two_qubit(pass_count, timeout):

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit(
        [
            cirq.CX.on(q1, q2),
            cirq.CX.on(q1, q2)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )

        optimiser.cancel_two_qubit_gates(
            gate_types=(CX, CX),
            gate_param=1,
            dedicated_nproc=1,
        )
        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert len(extracted_circuit) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_case_1(pass_count, timeout):
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    Should reduce to empty.
    """
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit(
        [
            cirq.T.on(q1),
            cirq.CX.on(q1, q2),
            cirq.T.on(q1) ** -1,
            cirq.CX.on(q1, q2)
         ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )

        optimiser.commute_rotation_with_control_left(
            gate_type=ZPow,
            gate_param=0.25,
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(ZPow, ZPow),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_two_qubit_gates(
            gate_types=(CX, CX),
            gate_param=1,
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert len(extracted_circuit) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
@pytest.mark.parametrize("n", [10])
async def test_case_1_repeated(pass_count, timeout, n):
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    repeating n times.

    Should reduce to empty.
    """

    def template(tup):
        q1, q2 = tup
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.CX.on(q1, q2)

    qubits = [cirq.NamedQubit(f'q{i}') for i in range(10)]

    initial_circuit = cirq.Circuit(
        [
            template(random.sample(qubits, 2)) for _ in range(n)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.commute_rotation_with_control_left(
            gate_type=ZPow,
            gate_param=0.25,
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(ZPow, ZPow),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_two_qubit_gates(
            gate_types=(CX, CX),
            gate_param=1,
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert len(extracted_circuit) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_commute_single_control_left(pass_count, timeout):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')

    expected_circuit = cirq.Circuit(
        [
            cirq.CX.on(q1, q2),
            cirq.T.on(q1)
        ]
    )

    initial_circuit = cirq.Circuit(
        [
            cirq.T.on(q1),
            cirq.CX.on(q1, q2)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.commute_rotation_with_control_left(
            gate_type=ZPow,
            gate_param=0.25,
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=expected_circuit, actual=extracted_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_cx_to_hhcxhh_a(pass_count, timeout):

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit(
        [
            cirq.CX.on(q1, q2),
            cirq.CX.on(q1, q2)
        ]
    )

    expected_circuit = cirq.Circuit(
        [
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.CX.on(q2, q1),
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.CX.on(q2, q1),
            cirq.H.on(q1),
            cirq.H.on(q2)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.cx_to_hhcxhh(
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=expected_circuit, actual=extracted_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_cx_to_hhcxhh_b(pass_count, timeout):

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')

    initial_circuit = cirq.Circuit(
        [
            cirq.CX.on(q2, q1)
        ]
    )
    expected_circuit = cirq.Circuit(
        [
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.CX.on(q1, q2),
            cirq.H.on(q1),
            cirq.H.on(q2)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.cx_to_hhcxhh(
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=expected_circuit, actual=extracted_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_hhcxhh_to_cx_a(pass_count, timeout):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit(
        [
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.CX.on(q1, q2),
            cirq.H.on(q1),
            cirq.H.on(q2)
        ]
    )
    expected_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.hhcxhh_to_cx(
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=expected_circuit, actual=extracted_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_hhcxhh_to_cx_b(pass_count, timeout):

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')

    initial_circuit = cirq.Circuit(
        [
            cirq.H.on(q1),
            cirq.H.on(q2),
            cirq.CX.on(q2, q1),
            cirq.H.on(q1),
            cirq.H.on(q2)
        ]
    )
    expected_circuit = cirq.Circuit(
        [
            cirq.CX.on(q1, q2)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(
            circuit=initial_circuit
        )

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.hhcxhh_to_cx(
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type='cirq')
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(expected=expected_circuit, actual=extracted_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_replace_two_sq_with_one(pass_count, timeout):
    q = cirq.NamedQubit("q")

    initial_circuit = cirq.Circuit([
        cirq.T.on(q),
        cirq.T.on(q),
    ])
    expected_circuit = cirq.Circuit([
        cirq.S.on(q),
    ])

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(circuit=initial_circuit)

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )
        optimiser.fuse_single_qubit_gates(
            gate_types=(
                PandoraGateTranslator.ZPowGate,
                PandoraGateTranslator.ZPowGate,
                PandoraGateTranslator.ZPowGate,
            ),
            gate_params=(0.25, 0.25, 0.5),
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type="cirq")
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert_same_up_to_qubit_permutation(
            expected=expected_circuit,
            actual=extracted_circuit,
        )

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_case_2(pass_count, timeout):
    """
    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───
    Should reduce to empty.
    """
    q1, q2 = cirq.NamedQubit("q1"), cirq.NamedQubit("q2")

    initial_circuit = cirq.Circuit([
        cirq.T.on(q1),
        cirq.CX.on(q1, q2),
        cirq.T.on(q1) ** -1,
        cirq.H.on(q1),
        cirq.H.on(q2),
        cirq.CX.on(q2, q1),
        cirq.H.on(q1),
        cirq.H.on(q2),
        cirq.H.on(q1),
        cirq.H.on(q1),
    ])

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(circuit=initial_circuit)

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )

        optimiser.commute_rotation_with_control_left(
            gate_type=PandoraGateTranslator.ZPowGate,
            gate_param=0.25,
            dedicated_nproc=1,
        )

        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(
                PandoraGateTranslator.ZPowGate,
                PandoraGateTranslator.ZPowGate,
            ),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.hhcxhh_to_cx(dedicated_nproc=1)
        optimiser.cancel_two_qubit_gates(
            gate_types=(
                PandoraGateTranslator.CXPowGate,
                PandoraGateTranslator.CXPowGate,
            ),
            gate_param=1,
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(
                PandoraGateTranslator.HPowGate,
                PandoraGateTranslator.HPowGate,
            ),
            gate_params=(1, 1),
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type="cirq")
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert len(extracted_circuit) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("n", [10])
@pytest.mark.parametrize("pass_count", [1])
@pytest.mark.parametrize("timeout", [1])
async def test_case_2_repeated(n, pass_count, timeout):
    """
    Repeat:
    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───
    Should reduce to empty.
    """
    def template(pair):
        q1, q2 = pair
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)
        yield cirq.CX.on(q2, q1)
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)

    qubits = [cirq.NamedQubit(f"q{i}") for i in range(10)]
    initial_circuit = cirq.Circuit(
        [
            template(random.sample(qubits, 2)) for _ in range(n)
        ]
    )

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(circuit=initial_circuit)

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=pass_count,
            timeout=timeout,
            logger_id=1,
        )

        optimiser.hhcxhh_to_cx(dedicated_nproc=1)
        await optimiser.start()

        optimiser.commute_rotation_with_control_left(
            gate_type=PandoraGateTranslator.ZPowGate,
            gate_param=0.25,
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(
                PandoraGateTranslator.ZPowGate,
                PandoraGateTranslator.ZPowGate,
            ),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        optimiser.cancel_two_qubit_gates(
            gate_types=(
                PandoraGateTranslator.CXPowGate,
                PandoraGateTranslator.CXPowGate,
            ),
            gate_param=1,
            dedicated_nproc=1,
        )

        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type="cirq")
        extracted_circuit = remove_io_gates(extracted_circuit)

        assert len(extracted_circuit) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("pass_count", [int(1e9)])
@pytest.mark.parametrize("stop_after", [5])
async def test_logical_correctness_random(pass_count, stop_after):

    for n_qubits in range(2, 4):
        for n_templates in range(5, 30, 5):
            initial_circuit = benchmark_cirq.create_random_circuit(
                n_qubits=n_qubits,
                n_templates=n_templates,
                templates=[
                    "add_two_hadamards",
                    "add_two_cnots",
                    "add_base_change",
                    "add_t_t_dag",
                    "add_t_cx",
                    "add_cx_t",
                ],
                add_margins=False,
            )

            t_count_before = count_t_gates(initial_circuit)

            db = PandoraDB(config_file)
            await db.connect()

            try:
                repo = GateRepository(db)
                service = PandoraService(db=db, repo=repo)

                await service.build_circuit(circuit=initial_circuit)

                optimiser = PandoraOptimiser(
                    db=db,
                    pass_count=pass_count,
                    timeout=stop_after,
                    logger_id=1,
                )

                optimiser.cancel_single_qubit_gates(
                    gate_types=(PandoraGateTranslator.HPowGate, PandoraGateTranslator.HPowGate),
                    gate_params=(1, 1),
                    dedicated_nproc=2,
                )
                optimiser.cancel_single_qubit_gates(
                    gate_types=(PandoraGateTranslator._PauliZ, PandoraGateTranslator._PauliZ),
                    gate_params=(1, 1),
                    dedicated_nproc=1,
                )
                optimiser.cancel_single_qubit_gates(
                    gate_types=(PandoraGateTranslator.ZPowGate, PandoraGateTranslator.ZPowGate),
                    gate_params=(0.25, -0.25),
                    dedicated_nproc=1,
                )
                optimiser.cancel_single_qubit_gates(
                    gate_types=(PandoraGateTranslator._PauliX, PandoraGateTranslator._PauliX),
                    gate_params=(1, 1),
                    dedicated_nproc=1,
                )
                optimiser.cancel_two_qubit_gates(
                    gate_types=(PandoraGateTranslator.CXPowGate, PandoraGateTranslator.CXPowGate),
                    gate_param=1,
                    dedicated_nproc=1,
                )
                optimiser.fuse_single_qubit_gates(
                    gate_types=(
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator.ZPowGate,
                    ),
                    gate_params=(0.25, 0.25, 0.5),
                    dedicated_nproc=1,
                )
                optimiser.fuse_single_qubit_gates(
                    gate_types=(
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator._PauliZ,
                    ),
                    gate_params=(-0.5, -0.5, -1.0),
                    dedicated_nproc=1,
                )
                optimiser.fuse_single_qubit_gates(
                    gate_types=(
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator.ZPowGate,
                        PandoraGateTranslator.ZPowGate,
                    ),
                    gate_params=(-0.25, -0.25, -0.5),
                    dedicated_nproc=1,
                )
                optimiser.commute_rotation_with_control_left(
                    gate_type=PandoraGateTranslator.ZPowGate,
                    gate_param=0.25,
                    dedicated_nproc=1,
                )
                optimiser.commute_rotation_with_control_left(
                    gate_type=PandoraGateTranslator.ZPowGate,
                    gate_param=-0.25,
                    dedicated_nproc=1,
                )
                optimiser.commute_rotation_with_control_left(
                    gate_type=PandoraGateTranslator.ZPowGate,
                    gate_param=0.5,
                    dedicated_nproc=1,
                )
                optimiser.commute_rotation_with_control_left(
                    gate_type=PandoraGateTranslator.ZPowGate,
                    gate_param=-0.5,
                    dedicated_nproc=1,
                )
                optimiser.hhcxhh_to_cx(dedicated_nproc=1)

                await optimiser.start()

                extracted_circuit = await service.load_circuit(circuit_type="cirq")
                extracted_circuit = remove_io_gates(extracted_circuit)

                t_count_after = count_t_gates(extracted_circuit)
                print(f"T before {t_count_before}, T after {t_count_after}")

                if len(extracted_circuit.all_qubits()) == 0:
                    assert True

                assert_logically_equivalent_up_to_qubit_permutation(expected=extracted_circuit, actual=initial_circuit)

            finally:
                await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("n_proc", [2, 4, 8])
@pytest.mark.parametrize("stop_after", [3])
@pytest.mark.parametrize("pass_count", [int(1e9)])
async def test_commute_T_leftmost_location(n_proc, stop_after, pass_count):
    print(f"Testing leftmost T commutation template with {n_proc} processes.")

    cx_count = 20
    qubits = cirq.LineQubit.range(3)

    initial_circuit = cirq.Circuit()
    for _ in range(cx_count):
        initial_circuit.append(cirq.T(qubits[1]))
    for _ in range(0, cx_count, 2):
        initial_circuit.append(cirq.CX(qubits[1], qubits[0]))
        initial_circuit.append(cirq.CX(qubits[1], qubits[2]))
    for _ in range(cx_count):
        initial_circuit.append(cirq.T(qubits[1]) ** -1)

    db = PandoraDB(config_file)
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)

        await service.build_circuit(circuit=initial_circuit)

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=int(1e9),
            timeout=stop_after,
            logger_id=1,
        )

        optimiser.commute_rotation_with_control_left(
            gate_type=PandoraGateTranslator.ZPowGate,
            gate_param=0.25,
            dedicated_nproc=max(n_proc - 1, 1),
        )
        await optimiser.start()

        optimiser.cancel_single_qubit_gates(
            gate_types=(PandoraGateTranslator.ZPowGate, PandoraGateTranslator.ZPowGate),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type="cirq")
        print("After commute and cancel:")
        print(extracted_circuit)

        optimiser.cancel_single_qubit_gates(
            gate_types=(PandoraGateTranslator.ZPowGate, PandoraGateTranslator.ZPowGate),
            gate_params=(0.25, -0.25),
            dedicated_nproc=1,
        )
        await optimiser.start()

        extracted_circuit = await service.load_circuit(circuit_type="cirq")
        extracted_circuit = remove_io_gates(extracted_circuit)

        print("After cancel:")
        print(extracted_circuit)

        t_count = count_t_gates(extracted_circuit)

        assert t_count == 0
        assert_logically_equivalent_up_to_qubit_permutation(expected=extracted_circuit, actual=initial_circuit)

    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_after", [1])
@pytest.mark.parametrize("pass_count", [int(1e9)])
@pytest.mark.parametrize("timeout", [2])
@pytest.mark.parametrize("trials", [100])
async def test_race_condition(pass_count, timeout, stop_after, trials):
    q0, q1 = cirq.LineQubit.range(2)

    initial_circuit = cirq.Circuit()
    initial_circuit.append([
        cirq.CNOT(q0, q1),
        cirq.CNOT(q0, q1),
        cirq.T(q0),
        cirq.CNOT(q0, q1),
        cirq.CNOT(q1, q0),
        cirq.CNOT(q1, q0),
        cirq.T(q1),
        cirq.T(q1) ** -1,
        cirq.CNOT(q0, q1),
        cirq.CNOT(q0, q1),
        cirq.H(q0),
        cirq.H(q0),
        cirq.CNOT(q1, q0),
        cirq.T(q1),
        cirq.CNOT(q1, q0),
        cirq.CNOT(q1, q0),
        cirq.CNOT(q1, q0),
        cirq.T(q1),
        cirq.CNOT(q0, q1),
        cirq.T(q0),
        cirq.CNOT(q1, q0),
        cirq.H(q0),
        cirq.H(q0),
        cirq.T(q1),
        cirq.T(q1),
        cirq.T(q1) ** -1,
        cirq.T(q1),
        cirq.T(q1) ** -1,
        cirq.CNOT(q0, q1),
        cirq.CNOT(q0, q1),
        cirq.CNOT(q1, q0),
        cirq.T(q1),
        cirq.H(q1),
        cirq.H(q1),
        cirq.T(q1),
        cirq.T(q1) ** -1,
        cirq.CNOT(q0, q1),
        cirq.CNOT(q0, q1),
        cirq.H(q0),
        cirq.H(q0),
        cirq.H(q0),
        cirq.H(q1),
        cirq.H(q1),
        cirq.H(q1),
        cirq.CNOT(q0, q1),
        cirq.H(q0),
        cirq.H(q0),
        cirq.H(q0),
        cirq.H(q1),
        cirq.T(q1),
        cirq.T(q1) ** -1,
        cirq.CNOT(q1, q0),
        cirq.CNOT(q1, q0),
    ])

    for i in range(trials):

        db = PandoraDB(config_file)
        await db.connect()

        try:
            repo = GateRepository(db)
            service = PandoraService(db=db, repo=repo)

            await service.build_circuit(circuit=initial_circuit)

            optimiser = PandoraOptimiser(
                db=db,
                pass_count=pass_count,
                timeout=timeout,
                logger_id=1,
            )

            optimiser.cancel_single_qubit_gates(
                gate_types=(PandoraGateTranslator.HPowGate, PandoraGateTranslator.HPowGate),
                gate_params=(1, 1),
                dedicated_nproc=2,
            )
            optimiser.cancel_single_qubit_gates(
                gate_types=(PandoraGateTranslator._PauliZ, PandoraGateTranslator._PauliZ),
                gate_params=(1, 1),
                dedicated_nproc=1,
            )
            optimiser.cancel_single_qubit_gates(
                gate_types=(PandoraGateTranslator.ZPowGate, PandoraGateTranslator.ZPowGate),
                gate_params=(0.25, -0.25),
                dedicated_nproc=1,
            )
            optimiser.cancel_single_qubit_gates(
                gate_types=(PandoraGateTranslator.ZPowGate, PandoraGateTranslator.ZPowGate),
                gate_params=(-0.25, 0.25),
                dedicated_nproc=1,
            )
            optimiser.cancel_single_qubit_gates(
                gate_types=(PandoraGateTranslator._PauliX, PandoraGateTranslator._PauliX),
                gate_params=(1, 1),
                dedicated_nproc=1,
            )
            optimiser.cancel_two_qubit_gates(
                gate_types=(PandoraGateTranslator.CXPowGate, PandoraGateTranslator.CXPowGate),
                gate_param=1,
                dedicated_nproc=1,
            )
            optimiser.fuse_single_qubit_gates(
                gate_types=(
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator.ZPowGate,
                ),
                gate_params=(0.25, 0.25, 0.5),
                dedicated_nproc=1,
            )
            optimiser.fuse_single_qubit_gates(
                gate_types=(
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator._PauliZ,
                ),
                gate_params=(-0.5, -0.5, -1.0),
                dedicated_nproc=1,
            )
            optimiser.fuse_single_qubit_gates(
                gate_types=(
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator.ZPowGate,
                    PandoraGateTranslator.ZPowGate,
                ),
                gate_params=(-0.25, -0.25, -0.5),
                dedicated_nproc=1,
            )
            optimiser.commute_rotation_with_control_left(
                gate_type=PandoraGateTranslator.ZPowGate,
                gate_param=0.25,
                dedicated_nproc=1,
            )
            optimiser.commute_rotation_with_control_left(
                gate_type=PandoraGateTranslator.ZPowGate,
                gate_param=-0.25,
                dedicated_nproc=1,
            )
            optimiser.commute_rotation_with_control_left(
                gate_type=PandoraGateTranslator.ZPowGate,
                gate_param=0.5,
                dedicated_nproc=1,
            )
            optimiser.commute_rotation_with_control_left(
                gate_type=PandoraGateTranslator.ZPowGate,
                gate_param=-0.5,
                dedicated_nproc=1,
            )
            optimiser.hhcxhh_to_cx(dedicated_nproc=1)

            await optimiser.start()

            extracted_circuit = await service.load_circuit(circuit_type="cirq")
            extracted_circuit = remove_io_gates(extracted_circuit)

            assert_logically_equivalent_up_to_qubit_permutation(expected=extracted_circuit, actual=initial_circuit)

        finally:
            await db.close()

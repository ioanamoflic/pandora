import math
import random

import cirq
import numpy as np

from qualtran import QUInt
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.arithmetic.addition import Add

from benchmarking import benchmark_cirq

from pandora.connection_util import *

TABLE_NAME = 'linked_circuit'
LARGE_BUFFER_VALUE = 100000
CIRCUIT_LABEL = 't'

myH = PandoraGateTranslator.HPowGate.value
myCX = PandoraGateTranslator.CXPowGate.value
myZPow = PandoraGateTranslator.ZPowGate.value
myPauliX = PandoraGateTranslator._PauliX.value
myPauliZ = PandoraGateTranslator._PauliZ.value

proc_id = 0
nprocs = 1
short_timeout = 1
long_timeout = 3
pass_count = 1
larger_pass_count = 1000000000

pandora_ingestible_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    cirq.X, cirq.Y, cirq.Z,
)


def keep(op: cirq.Operation):
    gate = op.without_classical_controls().gate
    ret = gate in pandora_ingestible_gate_set
    if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
        ret |= op.gate._original in pandora_ingestible_gate_set
    return ret


def get_adder_as_cirq_circuit(n_bits) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = Add(QUInt(n_bits))

    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts()))
    # Decompose the operation until all gates are in the target gate set.
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    return cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))


def clean_pandora(connection):
    drop_and_replace_tables(connection=connection,
                            clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name=TABLE_NAME,
                      large_buffer_value=LARGE_BUFFER_VALUE)


def convert_and_insert(connection, initial_circuit: cirq.Circuit):
    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label=CIRCUIT_LABEL)
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name=TABLE_NAME)


def test_cancel_single_qubit(connection):
    qubit = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.H.on(qubit), cirq.H.on(qubit)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)

    print(extracted_circuit)
    assert len(extracted_circuit) - 2 == 0
    print('Test cancel_single_qubit passed!')


def test_cancel_two_qubit(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)

    print(extracted_circuit)
    assert len(extracted_circuit) - 2 == 0
    print('Test cancel_two_qubit passed!')


def test_case_1(connection):
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    Should reduce to empty.
    """
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1, cirq.CX.on(q1, q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    assert len(extracted_circuit) == 0
    print('Test case 1 passed!')


def test_case_1_repeated(connection, n):
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
    initial_circuit = cirq.Circuit([template(random.sample(qubits, 2)) for _ in range(n)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    print(extracted_circuit)
    assert len(extracted_circuit) == 0
    print('Test case 1 repeated passed!')


def test_commute_single_control_right(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    expected_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call commute_single_control_right({myZPow}, 0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    print(expected_circuit)
    print(extracted_circuit)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test commute_single_control_right passed!')


def test_commute_single_control_left(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    expected_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    print(expected_circuit)
    print(extracted_circuit)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test commute_single_control_left passed!')


def test_cx_to_hhcxhh_a(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q2)])
    expected_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2),
                                     cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call linked_cx_to_hhcxhh({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    print(initial_circuit)
    print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_cx_to_hhcxhh_b(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])
    expected_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call linked_cx_to_hhcxhh({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    print(initial_circuit)
    print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_hhcxhh_to_cx_a(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])
    expected_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_hhcxhh_to_cx_b(connection):
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])
    expected_circuit = cirq.Circuit([cirq.CX.on(q1, q2)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_replace_two_sq_with_one(connection):
    q = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.T.on(q), cirq.T.on(q)])
    expected_circuit = cirq.Circuit([cirq.S.on(q)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test replace_two_sq_with_one passed!')


def test_commute_cx_ctrl():
    return NotImplementedError()


def test_commute_cx_target():
    return NotImplementedError()


def test_commute_cx_ctrl_target_case_1(connection):
    q1, q2, q3 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2'), cirq.NamedQubit('q3')
    initial_circuit = cirq.Circuit([cirq.CX.on(q2, q3), cirq.CX.on(q1, q2)])
    expected_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q2, q3), cirq.CX.on(q1, q3)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call commute_cx_ctrl_target_bernoulli(10, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test commute_cx_ctrl_target_1 passed!')


def test_commute_cx_ctrl_target_case_2(connection):
    q1, q2, q3 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2'), cirq.NamedQubit('q3')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q2, q3)])
    expected_circuit = cirq.Circuit([cirq.CX.on(q2, q3), cirq.CX.on(q1, q2), cirq.CX.on(q1, q3)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call commute_cx_ctrl_target_bernoulli(10, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(expected_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    expected_circuit = expected_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(expected_circuit) == str(extracted_circuit)
    print('Test commute_cx_ctrl_target_2 passed!')


def test_case_2(connection):
    """
    Testing circuit
    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───
    Should reduce to empty.
    """
    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1,
                                    cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2),
                                    cirq.H.on(q1), cirq.H.on(q1)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)
    print(extracted_circuit)

    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1,{proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    print(extracted_circuit)
    assert len(extracted_circuit) == 0
    print('Test case 2 passed!')


def test_case_2_repeated(connection, n):
    """
    Testing circuit

    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───

    repeating n times.

    Should reduce to empty.
    """

    def template(tup):
        q1, q2 = tup
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)
        yield cirq.CX.on(q2, q1)
        yield cirq.H.on(q1)
        yield cirq.H.on(q2)

    qubits = [cirq.NamedQubit(f'q{i}') for i in range(10)]
    initial_circuit = cirq.Circuit([template(random.sample(qubits, 2)) for _ in range(n)])

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    cursor = connection.cursor()
    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    assert len(extracted_circuit) == 0
    print('Test case 2 repeated passed!')


def test_qualtran_adder_opt_reconstruction(connection, stop_after=15):
    """
    This method tries to optimize a qualtran adder for stop_after seconds and then reconstruct it.
    In case of errors, the reconstruction will most probably not work. This is used mainly for testing the correctness
    of procedures on this type of circuit.
    Args:
        stop_after: the time (in seconds) the optimizing procedures run for
    """

    for bit_size in range(2, 5):
        adder_as_cirq_circuit = get_adder_as_cirq_circuit(n_bits=bit_size)

        clean_pandora(connection=connection)
        convert_and_insert(connection=connection, initial_circuit=adder_as_cirq_circuit)

        thread_procedures = [
            (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1,
             f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1,
             f"CALL cancel_single_qubit({myPauliX}, {myPauliX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1,
             f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1,
             f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL linked_hhcxhh_to_cx({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
            (1, f"CALL linked_cx_to_hhcxhh({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        ]
        db_multi_threaded(thread_proc=thread_procedures)
        stop_all_lurking_procedures(connection)
        print('stopped')

        extracted_circuit = extract_cirq_circuit(connection=connection,
                                                 circuit_label=CIRCUIT_LABEL,
                                                 table_name=TABLE_NAME,
                                                 remove_io_gates=True,
                                                 just_count=False,
                                                 is_test=False)
        print('extracted')

        circuit = remove_measurements(remove_classically_controlled_ops(adder_as_cirq_circuit))
        extracted_circuit = remove_measurements(remove_classically_controlled_ops(extracted_circuit))

        assert np.allclose(circuit.unitary(), extracted_circuit.unitary())
        print(f'Passed adder({bit_size})!')


def count_t_gates(circuit, tol=1e-8):
    def is_t_like(op):
        # Only care about Z rotations
        if not isinstance(op.gate, cirq.ZPowGate):
            return False

        # Normalize exponent into [0, 1)
        exp = op.gate.exponent % 1

        # T = 1/4, T† = 3/4 (mod 1)
        return (
                math.isclose(exp, 0.25, abs_tol=tol) or
                math.isclose(exp, 0.75, abs_tol=tol)
        )

    return sum(
        1
        for moment in circuit
        for op in moment
        if is_t_like(op)
    )


def test_logical_correctness_random(connection, stop_after: int):
    all_thread_proc = [
        (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliZ}, {myPauliZ}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliX}, {myPauliX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myPauliZ}, -0.5, -0.5, -1.0, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL linked_hhcxhh_to_cx({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
    ]

    thread_procedures = all_thread_proc

    for n_qubits in range(2, 4):
        for n_templates in range(5, 30, 5):
            print(f'Testing for {n_qubits} qubits and {n_templates} templates.')

            initial_circuit = benchmark_cirq.create_random_circuit(n_qubits=n_qubits, n_templates=n_templates,
                                                                   templates=[
                                                                       'add_two_hadamards',
                                                                       'add_two_cnots',
                                                                       'add_base_change',
                                                                       'add_t_t_dag',
                                                                       'add_t_cx',
                                                                       'add_cx_t'
                                                                   ],
                                                                   add_margins=False)
            clean_pandora(connection=connection)
            convert_and_insert(connection=connection, initial_circuit=initial_circuit)

            print('----------------------------------------------')
            print('Initial:')
            print(initial_circuit)

            t_count_before = count_t_gates(initial_circuit)

            db_multi_threaded(thread_proc=thread_procedures)
            stop_all_lurking_procedures(connection)

            extracted_circuit = extract_cirq_circuit(connection=connection,
                                                     circuit_label=CIRCUIT_LABEL,
                                                     table_name=TABLE_NAME,
                                                     remove_io_gates=False,
                                                     just_count=False,
                                                     is_test=False)
            print('Final:')
            print(extracted_circuit)

            t_count_after = count_t_gates(extracted_circuit)

            print(f"T before {t_count_before}, T after {t_count_after}")
            assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


def test_multithreading_performance(connection,
                                    repeated_template: str,
                                    same_proc_id: bool,
                                    n_proc: int,
                                    seed: int,
                                    stop_after: int):
    print(f'Testing for {repeated_template} template with {n_proc} processes (same_proc_id={same_proc_id}).')

    initial_circuit = benchmark_cirq.create_random_circuit(n_qubits=5,
                                                           n_templates=20,
                                                           seed=seed,
                                                           templates=[repeated_template],
                                                           add_margins=False)
    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    def get_thread_proc():
        match repeated_template:
            case 'add_two_hadamards':
                if same_proc_id:
                    return [(1,
                             f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1,
                         f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case 'add_two_cnots':
                if same_proc_id:
                    return [(1,
                             f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1,
                         f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case 'add_base_change':
                if same_proc_id:
                    return [(1,
                             f"CALL linked_hhcxhh_to_cx({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1, f"CALL linked_hhcxhh_to_cx({my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case 'add_t_t_dag':
                if same_proc_id:
                    return [(1,
                             f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1,
                         f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case 'add_t_cx':
                if same_proc_id:
                    return [(1,
                             f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1,
                         f"CALL commute_single_control_left({myZPow}, 0.25, {my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case 'add_cx_t':
                if same_proc_id:
                    return [(1,
                             f"CALL commute_single_control_right({myZPow}, 0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")] * n_proc
                return [(1,
                         f"CALL commute_single_control_right({myZPow}, 0.25, {my_proc_id}, {nprocs}, {larger_pass_count}, {stop_after})")
                        for my_proc_id in range(n_proc)]
            case _:
                raise f"Template {repeated_template} does not exist"

    all_thread_proc = get_thread_proc()

    db_multi_threaded(thread_proc=all_thread_proc)
    stop_all_lurking_procedures(connection)

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)
    print(initial_circuit)
    print(extracted_circuit)

    assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


def test_commute_T_leftmost_location(connection,
                                     n_proc: int,
                                     stop_after: int):
    print(f'Testing leftmost T commutation template with {n_proc} processes.')

    cx_count = 20
    initial_circuit = cirq.Circuit()
    qubits = cirq.LineQubit.range(3)
    for i in range(cx_count):
        initial_circuit.append(cirq.T(qubits[1]))
    for _ in range(0, cx_count, 2):
        initial_circuit.append(cirq.CX(qubits[1], qubits[0]))
        initial_circuit.append(cirq.CX(qubits[1], qubits[2]))
    for i in range(cx_count):
        initial_circuit.append(cirq.T(qubits[1])**-1)

    clean_pandora(connection=connection)
    convert_and_insert(connection=connection, initial_circuit=initial_circuit)

    def get_thread_proc():
        return_list = []
        for proc_id in range(n_proc - 1):
            return_list.append((1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {n_proc}, {larger_pass_count}, {stop_after})"))
        return_list.append((1, f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {n_proc-1}, {n_proc}, {larger_pass_count}, {stop_after})"))

        return return_list

    all_thread_proc = get_thread_proc()

    db_multi_threaded(thread_proc=all_thread_proc)
    stop_all_lurking_procedures(connection)

    print("Before:")
    print(initial_circuit)

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    print("After commute and cancel:")
    print(extracted_circuit)

    cursor = connection.cursor()
    cursor.execute(f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, 1, 1)")

    print("After cancel:")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label=CIRCUIT_LABEL,
                                             table_name=TABLE_NAME,
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)
    print(extracted_circuit)
    assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


def test_race_condition(connection, stop_after: int):
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
        cirq.CNOT(q1, q0)
    ])

    print(initial_circuit)

    local_nprocs = 1

    all_thread_proc = [
        (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliZ}, {myPauliZ}, 1, 1, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myZPow}, {myZPow}, -0.25, 0.25, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliX}, {myPauliX}, 1, 1, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myPauliZ}, -0.5, -0.5, -1.0, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, -0.25, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, 0.5, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL commute_single_control_left({myZPow}, -0.5, {proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL linked_hhcxhh_to_cx({proc_id}, {local_nprocs}, {larger_pass_count}, {stop_after})"),
    ]

    thread_procedures = all_thread_proc

    passed_count = 0
    test_count = 100
    for i in range(test_count):
        print(f'Test nr {i}.')

        clean_pandora(connection=connection)
        convert_and_insert(connection=connection, initial_circuit=initial_circuit)
        db_multi_threaded(thread_proc=thread_procedures)
        stop_all_lurking_procedures(connection)

        extracted_circuit = extract_cirq_circuit(connection=connection,
                                                 circuit_label=CIRCUIT_LABEL,
                                                 table_name=TABLE_NAME,
                                                 remove_io_gates=False,
                                                 just_count=False,
                                                 is_test=False)

        print(extracted_circuit)

        passed = np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())
        if passed:
            passed_count += 1

        assert passed is True

    print(f'Passed {passed_count}/{test_count} tests.')


if __name__ == "__main__":
    conn = get_connection()

    # test_cancel_single_qubit(conn)
    # test_cancel_two_qubit(conn)
    # test_commute_single_control_right(conn)
    # test_commute_single_control_left(conn)
    # test_cx_to_hhcxhh_a(conn)
    # test_cx_to_hhcxhh_b(conn)
    # test_hhcxhh_to_cx_a(conn)
    # test_hhcxhh_to_cx_b(conn)
    # test_replace_two_sq_with_one(conn)
    # test_case_1(conn)
    # test_case_2(conn)
    # test_case_1_repeated(conn, n=10)
    # test_case_2_repeated(conn, n=10)
    # test_qualtran_adder_opt_reconstruction(conn, stop_after=5)
    # test_logical_correctness_random(conn, stop_after=5)
    #
    # for n_procs in [1, 2, 4, 8]:
    #     test_commute_T_leftmost_location(connection=conn, n_proc=n_procs, stop_after=10)
    #
    # experiment_seed = random.randint(1, 100)
    # print(f"Running experiment with seed {experiment_seed} ")
    # for repeated_template in ['add_two_hadamards',
    #                           'add_two_cnots',
    #                           # 'add_base_change',
    #                           'add_t_t_dag',
    #                           # 'add_t_cx',
    #                           # 'add_cx_t' # this one is buggy
    #                           ]:
    #     for same_proc_id in [True, False]:
    #         for n_procs in [1, 2, 4, 8]:
    #             test_multithreading_performance(conn,
    #                                             repeated_template=repeated_template,
    #                                             same_proc_id=same_proc_id,
    #                                             n_proc=n_procs,
    #                                             seed=experiment_seed,
    #                                             stop_after=3)

    test_race_condition(conn, stop_after=3)

    conn.close()

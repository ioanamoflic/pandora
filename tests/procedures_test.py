import random
import numpy as np

from qualtran import QUInt
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.arithmetic.addition import Add
from qualtran.bloqs.data_loading import QROM

from benchmarking import benchmark_cirq

from pandora.connection_util import *
from pandora.qualtran_to_pandora_util import get_cirq_circuit_for_bloq, assert_circuit_is_pandora_ingestible

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
larger_pass_count = 10

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


def get_qrom_as_cirq_circuit(data) -> cirq.Circuit:
    """
    Used of testing.
    """
    bloq = QROM.build_from_data(data)
    qrom_circuit = get_cirq_circuit_for_bloq(bloq)
    return qrom_circuit


def test_cancel_single_qubit(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    qubit = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.H.on(qubit), cirq.H.on(qubit)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)

    print(extracted_circuit)
    assert len(extracted_circuit) - 2 == 0
    print('Test cancel_single_qubit passed!')


def test_cancel_two_qubit(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)

    print(extracted_circuit)
    assert len(extracted_circuit) - 2 == 0
    print('Test cancel_two_qubit passed!')


def test_commute_single_control_right(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    final_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(
        f"call commute_single_control_right({myZPow}, 0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    print(final_circuit)
    print(extracted_circuit)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_single_control_right passed!')


def test_commute_single_control_left(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    final_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.T.on(q1)])
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(
        f"call commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    print(final_circuit)
    print(extracted_circuit)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_single_control_right passed!')


def test_cx_to_hhcxhh_a(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=6)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q1, q2)])
    final_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2),
                                  cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call linked_cx_to_hhcxhh({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)
    print(initial_circuit)
    print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    # assert str(final_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_cx_to_hhcxhh_b(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])
    final_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call linked_cx_to_hhcxhh({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=False,
                                             just_count=False,
                                             is_test=False)
    # print(initial_circuit)
    # print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    # assert str(final_circuit) == str(extracted_circuit)
    print('Test cx_to_hhcxhh passed!')


def test_hhcxhh_to_cx_a(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    # initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q1, q2), cirq.H.on(q1), cirq.H.on(q2)])
    initial_circuit = benchmark_cirq.create_random_circuit(n_qubits=3, n_templates=3,
                                                           templates=['add_base_change'],
                                                           add_margins=False)
    print(initial_circuit)

    final_circuit = cirq.Circuit([cirq.CX.on(q2, q1)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)


    print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    # assert str(final_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_hhcxhh_to_cx_b(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2)])
    final_circuit = cirq.Circuit([cirq.CX.on(q1, q2)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    print(initial_circuit)
    print(extracted_circuit)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test hhcxhh_to_cx passed!')


def test_replace_two_sq_with_one(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q = cirq.NamedQubit('q')
    initial_circuit = cirq.Circuit([cirq.T.on(q), cirq.T.on(q)])
    final_circuit = cirq.Circuit([cirq.S.on(q)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(
        f"call fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {pass_count}, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             just_count=False,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test replace_two_sq_with_one passed!')


def test_commute_cx_ctrl():
    return NotImplementedError()


def test_commute_cx_target():
    return NotImplementedError()


def test_commute_cx_ctrl_target_case_1(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2, q3 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2'), cirq.NamedQubit('q3')
    initial_circuit = cirq.Circuit([cirq.CX.on(q2, q3), cirq.CX.on(q1, q2)])
    final_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q2, q3), cirq.CX.on(q1, q3)])

    print(initial_circuit)
    print(final_circuit)

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call commute_cx_ctrl_target_bernoulli(10, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_cx_ctrl_target_1 passed!')


def test_commute_cx_ctrl_target_case_2(connection):
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2, q3 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2'), cirq.NamedQubit('q3')
    initial_circuit = cirq.Circuit([cirq.CX.on(q1, q2), cirq.CX.on(q2, q3)])
    final_circuit = cirq.Circuit([cirq.CX.on(q2, q3), cirq.CX.on(q1, q2), cirq.CX.on(q1, q3)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0, add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    cursor.execute(f"call commute_cx_ctrl_target_bernoulli(10, 1)")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             table_name='linked_circuit',
                                             remove_io_gates=True,
                                             is_test=False)

    qubit_map = dict(
        zip(
            sorted(final_circuit.all_qubits()),
            sorted(extracted_circuit.all_qubits())
        )
    )
    final_circuit = final_circuit.transform_qubits(qubit_map=qubit_map)

    assert str(final_circuit) == str(extracted_circuit)
    print('Test commute_cx_ctrl_target_2 passed!')


def test_case_1(connection):
    """
    Testing circuit

    q1: ───T───@───T^-1───@───
               │          │
    q2: ───────X──────────X───

    Should reduce to empty.
    """
    cursor = connection.cursor()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1, cirq.CX.on(q1, q2)])
    print(initial_circuit)
    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
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
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    cursor = connection.cursor()
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    def template(tup):
        q1, q2 = tup
        yield cirq.T.on(q1)
        yield cirq.CX.on(q1, q2)
        yield cirq.T.on(q1) ** -1
        yield cirq.CX.on(q1, q2)

    qubits = [cirq.NamedQubit(f'q{i}') for i in range(10)]
    initial_circuit = cirq.Circuit([template(random.sample(qubits, 2)) for _ in range(n)])

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')

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
                                             is_test=False
                                             )
    print(extracted_circuit)
    assert len(extracted_circuit) == 0
    print('Test case 1 repeated passed!')


def test_case_2(connection):
    """
    Testing circuit
    q1: ───T───@───T^-1───H───X───H───
               │              │
    q2: ───────X───H──────────@───H───
    Should reduce to empty.
    """
    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

    q1, q2 = cirq.NamedQubit('q1'), cirq.NamedQubit('q2')
    initial_circuit = cirq.Circuit([cirq.T.on(q1), cirq.CX.on(q1, q2), cirq.T.on(q1) ** -1,
                                    cirq.H.on(q1), cirq.H.on(q2), cirq.CX.on(q2, q1), cirq.H.on(q1), cirq.H.on(q2),
                                    cirq.H.on(q1), cirq.H.on(q1)])
    print(initial_circuit)
    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=False,
                                             table_name='linked_circuit',
                                             is_test=False
                                             )
    print(extracted_circuit)

    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=False,
                                             table_name='linked_circuit',
                                             just_count=False,
                                             is_test=False
                                             )
    print(extracted_circuit)

    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1,{proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=True,
                                             table_name='linked_circuit',
                                             just_count=False,
                                             is_test=False
                                             )
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
    cursor = connection.cursor()

    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

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

    pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                       last_id=0,
                                       add_margins=True,
                                       label='t')
    insert_in_batches(pandora_gates=pandora_gates,
                      connection=connection,
                      table_name='linked_circuit')

    cursor.execute(f"call linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call commute_single_control_right({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(
        f"call cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")
    cursor.execute(f"call cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {short_timeout})")

    extracted_circuit = extract_cirq_circuit(connection=connection,
                                             circuit_label='t',
                                             remove_io_gates=True,
                                             table_name='linked_circuit',
                                             just_count=False,
                                             is_test=False
                                             )
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
        drop_and_replace_tables(connection=connection, clean=True)
        refresh_all_stored_procedures(connection=connection)
        reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

        adder_as_cirq_circuit = get_adder_as_cirq_circuit(n_bits=bit_size)

        pandora_gates, _ = cirq_to_pandora(cirq_circuit=adder_as_cirq_circuit,
                                           last_id=0,
                                           label='t',
                                           add_margins=True)
        insert_in_batches(pandora_gates=pandora_gates,
                          connection=connection,
                          table_name='linked_circuit')

        thread_procedures = [
            (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1,
             f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1,
             f"CALL cancel_single_qubit({myPauliX}, {myPauliX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1,
             f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1,
             f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, -0.25, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, 0.5, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL commute_single_control_left({myZPow}, -0.5, {proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL linked_hhcxhh_to_cx({proc_id}, {nprocs}, {pass_count}, {stop_after})"),
            (1, f"CALL linked_cx_to_hhcxhh({proc_id}, {nprocs}, {pass_count}, {stop_after})"),
        ]
        db_multi_threaded(thread_proc=thread_procedures)
        stop_all_lurking_procedures(connection)
        print('stopped')

        extracted_circuit: cirq.Circuit = extract_cirq_circuit(connection=connection,
                                                               circuit_label='t',
                                                               remove_io_gates=True,
                                                               table_name='linked_circuit',
                                                               just_count=False,
                                                               is_test=False)
        print('extracted')

        circuit = remove_measurements(remove_classically_controlled_ops(adder_as_cirq_circuit))
        extracted_circuit = remove_measurements(remove_classically_controlled_ops(extracted_circuit))

        assert np.allclose(circuit.unitary(), extracted_circuit.unitary())
        print(f'Passed adder({bit_size})!')


def check_logical_correctness_random(connection, stop_after: int):
    all_thread_proc = [
        (1, f"CALL cancel_single_qubit({myH}, {myH}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliZ}, {myPauliZ}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myZPow}, {myZPow}, 0.25, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_single_qubit({myPauliX}, {myPauliX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL cancel_two_qubit({myCX}, {myCX}, 1, 1, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, 0.25, 0.25, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (
        #     1,
            # f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myPauliZ}, -0.5, -0.5, -1.0, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (
        #     1,
            # f"CALL fuse_single_qubit({myZPow}, {myZPow}, {myZPow}, -0.25, -0.25, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL commute_single_control_left({myZPow}, 0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL commute_single_control_left({myZPow}, -0.25, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL commute_single_control_left({myZPow}, 0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL commute_single_control_left({myZPow}, -0.5, {proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        (1, f"CALL linked_hhcxhh_to_cx({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
        # (1, f"CALL linked_cx_to_hhcxhh({proc_id}, {nprocs}, {larger_pass_count}, {stop_after})"),
    ]

    thread_procedures = all_thread_proc

    for n_qubits in range(2, 4):
        for n_templates in range(5, 30, 5):
            print(f'Testing for {n_qubits} qubits and {n_templates} templates.')

            drop_and_replace_tables(connection=connection, clean=True)
            refresh_all_stored_procedures(connection=connection)
            reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

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
            print('----------------------------------------------')
            print('Initial:')
            print(initial_circuit)

            pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                               last_id=0,
                                               label='t',
                                               add_margins=True)
            insert_in_batches(pandora_gates=pandora_gates,
                              connection=connection,
                              table_name='linked_circuit')

            db_multi_threaded(thread_proc=thread_procedures)
            stop_all_lurking_procedures(connection)
            extracted_circuit = extract_cirq_circuit(connection=connection,
                                                     circuit_label='t',
                                                     remove_io_gates=False,
                                                     table_name='linked_circuit',
                                                     is_test=False,
                                                     just_count=False
                                                     )
            print('Final:')
            print(extracted_circuit)
            assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())


def test_BVZ_optimization(connection, stop_after):
    for n_bits in range(2, 5):
        for secret in range(2 ** n_bits):
            secret_bin = '{0:b}'.format(secret)
            drop_and_replace_tables(connection=connection, clean=True)
            refresh_all_stored_procedures(connection=connection)
            reset_database_id(conn, table_name='linked_circuit', large_buffer_value=100000)

            initial_circuit = benchmark_cirq.bernstein_vazirani(nr_bits=n_bits, secret=secret_bin)
            pandora_gates, _ = cirq_to_pandora(cirq_circuit=initial_circuit,
                                               last_id=0,
                                               label='t',
                                               add_margins=True)
            insert_in_batches(pandora_gates=pandora_gates,
                              connection=connection,
                              table_name='linked_circuit')

            thread_procedures = [
                (3, f"CALL cancel_single_qubit_bernoulli({myH}, {myH}, 1, 1, 10, 10000000)"),
                (1, f"CALL linked_hhcxhh_to_cx_bernoulli(10, 10000000)"),
                (1, f"CALL linked_cx_to_hhcxhh_bernoulli(10, 10000000)"),
                (1, f"CALL stopper({stop_after})")
            ]

            db_multi_threaded(thread_proc=thread_procedures)
            stop_all_lurking_procedures(connection)
            extracted_circuit = extract_cirq_circuit(connection=connection,
                                                     circuit_label='t',
                                                     remove_io_gates=False,
                                                     table_name='linked_circuit',
                                                     is_test=False
                                                     )
            assert np.allclose(initial_circuit.unitary(), extracted_circuit.unitary())
            print(f'Passed bvz({n_bits}, secret={secret})')


if __name__ == "__main__":
    conn = get_connection()

    # test_commute_cx_ctrl_target_case_1(conn)
    # test_commute_cx_ctrl_target_case_2(conn)

    # test_cancel_single_qubit(conn)
    # test_cancel_two_qubit(conn)
    # test_commute_single_control_right(conn)
    # test_commute_single_control_left(conn)
    # test_cx_to_hhcxhh_a(conn)
    # test_cx_to_hhcxhh_b(conn)
    test_hhcxhh_to_cx_a(conn)
    # test_hhcxhh_to_cx_b(conn)
    # test_replace_two_sq_with_one(conn)
    # test_case_1(conn)
    # test_case_2(conn)
    # test_case_1_repeated(conn, n=10)
    # test_case_2_repeated(conn, n=10)
    # test_qualtran_adder_opt_reconstruction(conn, stop_after=5)
    # check_logical_correctness_random(conn, stop_after=5)
    # test_BVZ_optimization(conn, stop_after=3)
    conn.close()
    # extracted_circuit = extract_cirq_circuit(connection=conn,
    #                                          circuit_label='t',
    #                                          remove_io_gates=False,
    #                                          table_name='linked_circuit',
    #                                          is_test=False,
    #                                          just_count=False
    #                                          )
    # print('Final:')
    # print(extracted_circuit)

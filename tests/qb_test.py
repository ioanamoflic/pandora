from pandora.connection_util import *
from pandora.pyliqtr_to_pandora_util import make_fh_circuit, make_mg_coating_walk_op, make_cyclic_o3_circuit, \
    make_hc_circuit, make_transverse_ising_circuit
from pandora.qualtran_to_pandora_util import get_pandora_compatible_circuit


def test_fh_circuit(N=10, p_algo=0.9999999904, times=0.01):
    print("Making fh circuit...")
    fh_circuit = make_fh_circuit(N=2, p_algo=0.9999999904, times=0.01)
    print(type(fh_circuit))

    decomposed_circuit = get_pandora_compatible_circuit(circuit=fh_circuit, decompose_from_high_level=True)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='f', add_margins=True)

    connection = get_connection()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      batch_size=1000000,
                      table_name='linked_circuit')

    print('Done fh_circuit!')


def test_mg_coating_walk_op():
    print("Making mg circuit...")
    mg_circuit = make_mg_coating_walk_op(EC=13)
    print(type(mg_circuit))

    decomposed_circuit = get_pandora_compatible_circuit(circuit=mg_circuit, decompose_from_high_level=True)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='m', add_margins=True)

    connection = get_connection()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      batch_size=1000000,
                      table_name='linked_circuit')
    print('Done mg_circuit!')
    return decomposed_circuit


def test_cyclic_o3():
    print("Making o3 circuit...")
    o3_circuit = make_cyclic_o3_circuit()
    print(type(o3_circuit))

    decomposed_circuit = get_pandora_compatible_circuit(circuit=o3_circuit, decompose_from_high_level=True)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='o', add_margins=True)

    connection = get_connection()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      batch_size=1000000,
                      table_name='linked_circuit')

    print('Done o3_circuit!')
    return decomposed_circuit


def test_hc_circuit():
    print("Making hc circuit...")
    hc_circuit = make_hc_circuit()
    print(type(hc_circuit))

    decomposed_circuit = get_pandora_compatible_circuit(circuit=hc_circuit, decompose_from_high_level=True)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='h', add_margins=True)

    connection = get_connection()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      batch_size=1000000,
                      table_name='linked_circuit')

    print('Done hc_circuit!')
    return decomposed_circuit


def test_traverse_ising():
    print("Making ti circuit...")
    ti_circuit = make_transverse_ising_circuit(N=3)
    print(type(ti_circuit))

    decomposed_circuit = get_pandora_compatible_circuit(circuit=ti_circuit, decompose_from_high_level=True)
    db_tuples, _ = cirq_to_pandora(cirq_circuit=decomposed_circuit, last_id=0, label='i', add_margins=True)

    connection = get_connection()
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit', large_buffer_value=1000)
    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      batch_size=1000000,
                      table_name='linked_circuit')
    print('Done ti_circuit!')
    return decomposed_circuit


if __name__ == "__main__":
    test_fh_circuit()
    # test_mg_coating_walk_op()
    # test_cyclic_o3()
    # test_hc_circuit()
    # test_traverse_ising()

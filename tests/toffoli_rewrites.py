import cirq

from pandora.connection_util import *


def test_toffoli_rewrite(connection):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)
    reset_database_id(connection, table_name='linked_circuit_test', large_buffer_value=100000)

    circuit = cirq.Circuit()
    q = [cirq.LineQubit(i) for i in range(3)]
    circuit.append(cirq.TOFFOLI.on(q[0], q[1], q[2]))
    circuit.append(cirq.CNOT.on(q[2], q[1]))
    print(circuit)

    storage = cirq_to_pandora(circuit, last_id=0, add_margins=True)

    insert_single_batch(connection, storage[0])


if __name__ == "__main__":

    """
        python3.12 tests/toffoli_rewrites.py ../default_config.json
    """

    import sys
    conn = get_connection(config_file_path=sys.argv[1])
    test_toffoli_rewrite(conn)

    conn.close()

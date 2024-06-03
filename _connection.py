import cirq
import cirq2db


def refresh_all_stored_procedures(conn):
    procedures = [
        'generic_procedures/cancel_single_qubit.sql',
        'generic_procedures/cancel_two_qubit.sql',
        'generic_procedures/commute_single_control_left.sql',
        'generic_procedures/commute_single_control_right.sql',
        'generic_procedures/insert_two_qubit.sql',
        'generic_procedures/replace_two_sq_with_one.sql',
        'generic_procedures/toffoli_decomposition.sql',
        'generic_procedures/cx_to_hhcxhh.sql',
        'generic_procedures/hhcxhh_to_cx.sql',
        'generic_procedures/stopper.sql',
        'generic_procedures/for_loop.sql'
    ]
    cursor = conn.cursor()
    for sp in procedures:
        with open(sp, "r") as spfile:
            print(f"...uploading {sp}")
            sql_statement = spfile.read()
            cursor.execute(sql_statement)
            conn.commit()


def create_linked_table(conn, clean=False):
    cursor = conn.cursor()
    if clean:
        print(f"...dropping linked_circuit")
        sql_statement = "drop table if exists linked_circuit cascade"
        # print(sql_statement)
        cursor.execute(sql_statement)
        conn.commit()

    with open("sql_generate_table.sql", "r") as create_f:
        print(f"...creating linked_circuit")
        sql_statement = create_f.read()
        # print(sql_statement)
        cursor.execute(sql_statement)
        conn.commit()


def create_batches(db_tuples, batch_size):
    """
    Create batches of lists
    :param batch_size:
    :param db_tuples:
    :return:
    """
    for i in range(0, len(db_tuples), batch_size):
        yield db_tuples[i:i + batch_size]


def insert_in_batches(db_tuples, conn, batch_size=1000):
    assert type(db_tuples) is list

    batches = create_batches(db_tuples, batch_size=int(batch_size))
    cursor = conn.cursor()
    for i, batch in enumerate(batches):
        args = ','.join(
            cursor.mogrify("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", tup).decode('utf-8') for tup in
            batch)
        sql_statement = \
            ("INSERT INTO linked_circuit(id, prev_q1, prev_q2, prev_q3, type, param, switch, next_q1, next_q2, "
             "next_q3, visited, label, cl_ctrl, meas_key) VALUES" + args)

        # execute the sql statement
        cursor.execute(sql_statement)
        conn.commit()


def extract_cirq_circuit(conn, circuit_label=None, remove_io_gates=False, with_tags=False):
    args = None
    if circuit_label is not None:
        args = (circuit_label,)
        sql = f"select * from linked_circuit where label=%s;"
    else:
        sql = f"select * from linked_circuit;"

    cursor = conn.cursor()
    cursor.execute(sql, args)
    tuples = cursor.fetchall()
    final_circ = cirq2db.db_to_cirq(tuples, with_tags=with_tags)

    if remove_io_gates:
        io_free_reconstructed = cirq.Circuit()
        for op in final_circ.all_operations():
            if not isinstance(op.gate, cirq2db.In) and not isinstance(op.gate, cirq2db.Out):
                io_free_reconstructed.append(op)
        return io_free_reconstructed

    return final_circ


def get_circuit_stats(conn):
    cur = conn.cursor()
    postgres_select_tot = \
        """select count(*) from linked_circuit;"""
    postgres_select_t = \
        """select count(*) from linked_circuit where type='T' or type='T**-1';"""
    postgres_select_s = \
        """select count(*) from linked_circuit where type='S' or type='S**-1';"""
    postgres_select_cx = \
        """select count(*) from linked_circuit where type='CNOT';"""
    postgres_select_h = \
        """select count(*) from linked_circuit where type='H';"""
    postgres_select_x = \
        """select count(*) from linked_circuit where type='X';"""

    cur.execute(postgres_select_tot)
    conn.commit()
    tot_count = cur.fetchone()[0]

    cur.execute(postgres_select_t)
    conn.commit()
    t_count = cur.fetchone()[0]

    cur.execute(postgres_select_cx)
    conn.commit()
    cx_count = cur.fetchone()[0]

    cur.execute(postgres_select_h)
    conn.commit()
    h_count = cur.fetchone()[0]

    cur.execute(postgres_select_x)
    conn.commit()
    x_count = cur.fetchone()[0]

    cur.execute(postgres_select_s)
    conn.commit()
    s_count = cur.fetchone()[0]

    return tot_count, t_count, s_count, cx_count, h_count, x_count

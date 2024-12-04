import os
import sys
import typing
from itertools import cycle
from multiprocessing import Process

import cirq
import psycopg2
import cirq2db
import db_config


def get_connection():
    connection = psycopg2.connect(
        database=db_config.database,
        user=db_config.user,
        host=db_config.host,
        port=db_config.port,
        password=db_config.password)

    connection.set_session(autocommit=True)

    if connection:
        print("Connection to the PostgreSQL established successfully.")
    else:
        print("Connection to the PostgreSQL encountered and error.")

    return connection


def refresh_all_stored_procedures(connection):
    procedures = [
        # bernoulli sample version
        'generic_procedures/cancel_single_qubit_bernoulli.sql',
        'generic_procedures/cancel_two_qubit_bernoulli.sql',
        'generic_procedures/commute_single_control_left_bernoulli.sql',
        'generic_procedures/commute_single_control_right_bernoulli.sql',
        'generic_procedures/replace_two_sq_with_one_bernoulli.sql',
        'generic_procedures/insert_two_qubit_bernoulli.sql',
        'generic_procedures/cx_to_hhcxhh_bernoulli.sql',
        'generic_procedures/hhcxhh_to_cx_bernoulli.sql',
        'generic_procedures/generate_edge_list.sql',
        # 'generic_procedures/commute_cx_ctrl_target_bernoulli.sql',

        # system sample version
        'generic_procedures/cancel_single_qubit.sql',
        'generic_procedures/cancel_two_qubit.sql',
        'generic_procedures/commute_single_control_left.sql',
        'generic_procedures/commute_single_control_right.sql',
        'generic_procedures/insert_two_qubit.sql',
        'generic_procedures/replace_two_sq_with_one.sql',
        'generic_procedures/toffoli_decomposition.sql',
        'generic_procedures/cx_to_hhcxhh.sql',
        'generic_procedures/hhcxhh_to_cx.sql',

        # worker procedures
        'generic_procedures/stopper.sql',
        'generic_procedures/for_loop.sql',

        # benchmarking only procedures
        'generic_procedures/cx_to_hhcxhh_visit.sql',

        # ls style procedures
        'ls_style_procedures/simplify_two_parity_check.sql',
        'ls_style_procedures/simplify_erasure_error.sql',
        'ls_style_procedures/cnotify_XX.sql',
        'ls_style_procedures/cnotify_ZZ.sql'
    ]
    cursor = connection.cursor()
    for sp in procedures:
        with open(sp, "r") as spfile:
            print(f"...uploading {sp}")
            sql_statement = spfile.read()
            cursor.execute(sql_statement)
            connection.commit()


def create_linked_table(connection, clean=False):
    cursor = connection.cursor()
    if clean:
        print(f"...dropping linked_circuit")
        sql_statement = "drop table if exists linked_circuit cascade"
        cursor.execute(sql_statement)
        connection.commit()

        print(f"...dropping stop_condition")
        sql_statement = "drop table if exists stop_condition cascade"
        cursor.execute(sql_statement)
        connection.commit()

        print(f"...dropping edge_list")
        sql_statement = "drop table if exists edge_list cascade"
        cursor.execute(sql_statement)
        connection.commit()

    with open("generic_procedures/_sql_generate_table.sql", "r") as create_f:
        print(f"...creating linked_circuit")
        sql_statement = create_f.read()
        cursor.execute(sql_statement)
        connection.commit()


def create_batches(db_tuples, batch_size):
    """
    Create batches of lists
    :param batch_size:
    :param db_tuples:
    :return:
    """
    for i in range(0, len(db_tuples), batch_size):
        yield db_tuples[i:i + batch_size]


def insert_in_batches(db_tuples, connection, batch_size=1000, reset_id=False):
    assert type(db_tuples) is list

    batches = create_batches(db_tuples, batch_size=int(batch_size))
    cursor = connection.cursor()
    for i, batch in enumerate(batches):
        args = ','.join(
            cursor.mogrify("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", tup).decode('utf-8') for tup in
            batch)
        sql_statement = \
            ("INSERT INTO linked_circuit(id, prev_q1, prev_q2, prev_q3, type, param, switch, next_q1, next_q2, "
             "next_q3, visited, label, cl_ctrl, meas_key) VALUES" + args)

        # execute the sql statement
        cursor.execute(sql_statement)
        connection.commit()

    if reset_id is True:
        query_max = "select * from linked_circuit order by id desc limit 1"
        cursor.execute(query_max, None)
        max_id = cursor.fetchall()[0][0]
        print(max_id)
        if reset_id is not None:
            cursor.execute(f"ALTER SEQUENCE linked_circuit_id_seq RESTART WITH {max_id + 1}")


def extract_cirq_circuit(connection, circuit_label=None, remove_io_gates=False, with_tags=False):
    args = None
    if circuit_label is not None:
        args = (circuit_label,)
        sql = "select * from linked_circuit where label=%s;"
    else:
        sql = "select * from linked_circuit;"

    cursor = connection.cursor()
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


def get_edge_list(connection):
    sql = "select * from edge_list;"

    cursor = connection.cursor()
    cursor.execute(sql, None)
    tuples = cursor.fetchall()

    return tuples


def get_gate_types(connection, num_elem):
    TRANSLATE = {
        'Rx': "Rx",
        'Ry': "Ry",
        'Rz': "Rz",
        'XPowGate': "X",
        'ZPowGate': "Z",
        'YPowGate': "Y",
        'HPowGate': "H",
        '_PauliX': "X",
        '_PauliZ': "Z",
        '_PauliY': "Y",
        'GlobalPhaseGate': "Phase",
        'ResetChannel': "R",
        'In': 'In',
        'Out': 'Out',
        'Inc': 'In',
        'Outc': 'Out',
        'M': "M",
        'CNOT': "CX",
        'CZ': "CZ",
        'CZPowGate': "CZ",
        'CXPowGate': "CX",
        'XXPowGate': "XX",
        'ZZPowGate': "ZZ"
    }
    EXTENDED = TRANSLATE.copy()
    for gate in EXTENDED.keys():
        for param in [0.25, -0.25, 0.5, -0.5, -1.0]:
            TRANSLATE[f'{gate}**{param}'] = f'{EXTENDED[gate]}**{param}'

    gate_ids = list(range(num_elem))
    types = []
    for gate_id in gate_ids:
        args = (gate_id,)
        sql = "select * from linked_circuit where id=%s;"
        cursor = connection.cursor()
        cursor.execute(sql, args)
        gate = cursor.fetchone()
        if gate is None:
            if gate_id == num_elem - 1:
                types.append("GLOBAL OUT")
            if gate_id == num_elem - 2:
                types.append("GLOBAL IN")
            if gate_id != num_elem - 1 and gate_id != num_elem - 2:
                print(f'Gate id {gate_id} not found!')
        else:
            types.append(TRANSLATE[gate[4]])
    return types


def map_hack(aff, proc_call, verbose=False):
    if sys.platform == "linux":
        my_pid = os.getppid()
        old_aff = os.sched_getaffinity(0)
        x = (my_pid, old_aff, os.sched_getaffinity(0))
        print("My pid is {} and my old affinity was {}, my new affinity is {}".format(*x))

    connection = get_connection()
    cursor = connection.cursor()
    connection.set_session(autocommit=True)
    if verbose:
        print('Calling procedure...')
    cursor.execute(proc_call)


def db_multi_threaded(thread_proc: typing.List[tuple]):
    n_threads = sum([n for (n, _) in thread_proc])
    if sys.platform == "linux":
        my_cpus = cycle(os.sched_getaffinity(0))
        cpus = [[next(my_cpus) * 2] for _ in range(n_threads)]

    process_list = []
    for (n, proc) in thread_proc:
        for _ in range(n):
            if sys.platform == "linux":
                p = Process(target=map_hack, args=(cpus.pop(), proc))
            else:
                p = Process(target=map_hack, args=(None, proc))
            process_list.append(p)

    for i in range(n_threads):
        process_list[i].start()
    for i in range(n_threads):
        process_list[i].join()

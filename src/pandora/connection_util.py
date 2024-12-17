import inspect
import os
import sys
from itertools import cycle
from multiprocessing import Process
import psycopg2

from pandora.cirq_to_pandora_util import *
from pandora.db_config import *
import cirq

from pandora.gate_translator import PANDORA_TO_READABLE


def get_connection():
    """
    Creates and returns a database connection object.
    """
    connection = psycopg2.connect(
        database=database,
        user=user,
        host=host,
        port=port,
        password=password)

    connection.set_session(autocommit=True)

    if connection:
        print("Connection to the PostgreSQL established successfully.")
    else:
        print("Connection to the PostgreSQL encountered and error.")

    return connection


def stop_all_lurking_procedures(connection) -> None:
    """
    Make sure there are no procedures running in a loop in Pandora.
    This can happen and is expected to happen if a procedure is supposed to find a template which does
    not exist in the database.
    """
    cursor = connection.cursor()
    cursor.execute("update stop_condition set stop=False")


def refresh_all_stored_procedures(connection, verbose=False) -> None:
    """
    Updates all stored procedures in the database.
    Params:
            connection: the Postgres connection object
    Returns:
            None.
    """
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
        'generic_procedures/commute_cx_ctrl_target_bernoulli.sql',

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
        'lattice_surgery_procedures/simplify_two_parity_check.sql',
        'lattice_surgery_procedures/simplify_erasure_error.sql',
        'lattice_surgery_procedures/cnotify_XX.sql',
        'lattice_surgery_procedures/cnotify_ZZ.sql'
    ]
    cursor = connection.cursor()

    directory, file = os.path.split(inspect.getfile(drop_and_replace_tables))
    for sp in procedures:
        with open(f"{directory}/{sp}", "r") as sp_file:
            if verbose:
                print(f"Uploading {sp}")
            sql_statement = sp_file.read()
            cursor.execute(sql_statement)
            connection.commit()


def drop_and_replace_tables(connection,
                            clean: bool = False,
                            tables: tuple[str] = ('linked_circuit', 'stop_condition', 'edge_list'),
                            verbose=False) -> None:
    """
    This method drops all tables of Pandora and rebuilds them according to the configuration in
    generic_procedures/_sql_generate_table.sql.
    Params:
            connection: the Postgres connection object
            clean: if True, drop previously existing tables with same names
            tables: tuple containing the names of tables which need to be dropped and rebuilt from scratch.
    Returns:
            None.

    """
    tables = list(tables)
    cursor = connection.cursor()

    if clean:
        for table in tables:
            if verbose:
                print(f"Dropping {table}")
            sql_statement = f"drop table if exists {table} cascade"
            cursor.execute(sql_statement)
            connection.commit()

    directory, file = os.path.split(inspect.getfile(drop_and_replace_tables))
    with open(f"{directory}/generic_procedures/_sql_generate_table.sql", "r") as create_f:
        if verbose:
            print(f"Building all tables from _sql_generate_table.sql")
        sql_statement = create_f.read()
        cursor.execute(sql_statement)
        connection.commit()


def create_batches(pandora_gates: list[PandoraGate],
                   batch_size: int) -> list:
    """
    Create batches of lists. One batch will be inserted into the database at a time.
    """
    for i in range(0, len(pandora_gates), batch_size):
        yield pandora_gates[i:i + batch_size]


def reset_database_id(connection,
                      table_name: str,
                      large_buffer_value: int = None) -> None:
    """
    If there are no elements in table table_name, the starting index is set to 0.
    If large_buffer_value is non-null, reset the id to this value.

    TODO: explain why we need this
    """
    cursor = connection.cursor()

    if large_buffer_value is not None:
        cursor.execute(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH {large_buffer_value}")
        return

    cursor.execute(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 0")


def insert_in_batches(pandora_gates: list[PandoraGate],
                      connection,
                      table_name: str,
                      batch_size: int = 1000,
                      reset_id: bool = False) -> None:
    """
    This method is used for inserting a list of PanoraGate objects into the database in batches.
    The batched version of the insertion is faster than inserting gates one by one. The idea is to create
    a huge string of insert statements which is processed as a single one.

    Note that the fields in the PandoraGate object should match the physical table column names. Since psycopg2
    does not support ORM, and this is a way of faking it.

     Params:
            pandora_gates: list of PandoraGate objects
            connection: the Postgres connection object
            table_name: name of the table in which the gates should be inserted
            batch_size: size of PandoraGate objects which should be inserted at once.
            reset_id: boolean value based on which we reset the starting id to 0 or not.
    Returns:
            None.
    """
    pandora_gates = list(pandora_gates)
    batches = create_batches(pandora_gates, batch_size=int(batch_size))
    cursor = connection.cursor()

    mogrify_arg, insert_query = pandora_gates[0].get_insert_query(table_name=table_name)
    for i, batch in enumerate(batches):
        # TODO fix this to avid hard coding
        #     args = ','.join(cursor.mogrify(mogrify_arg, pandora_gate.to_tuple()).decode('utf-8')
        #                     for pandora_gate in batch)
        #     print(args)
        #     sql_statement = (insert_query + args)
        #     print('SQL statement:')
        #     print(sql_statement)
        #     cursor.execute(sql_statement)
        #     connection.commit()
        args = ','.join(
            cursor.mogrify("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", tup.to_tuple()).decode('utf-8')
            for tup
            in
            batch)
        sql_statement = \
            ("INSERT INTO linked_circuit(id, prev_q1, prev_q2, prev_q3, type, param, global_shift, switch, next_q1, "
             "next_q2, next_q3, visited, label, cl_ctrl, meas_key) VALUES" + args)

        # execute the sql statement
        cursor.execute(sql_statement)
        connection.commit()

    if reset_id is True:
        reset_database_id(cursor, table_name=table_name)


def remove_io_gates_from_circuit(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Constructs and returns a copy of circuit without In/Out gates.
    """
    io_free_reconstructed = cirq.Circuit()
    for op in circuit.all_operations():
        if not isinstance(op.gate, In) and not isinstance(op.gate, Out):
            io_free_reconstructed.append(op)
    return io_free_reconstructed


def extract_cirq_circuit(connection,
                         circuit_label: str = None,
                         table_name: str = None,
                         remove_io_gates: bool = False) -> cirq.Circuit:
    """
    Extracts a circuit with a given label from the database and returns the corresponding cirq circuit.
    Params:
            connection: the Postgres connection object
            table_name: name of the table from which the circuit is read out
            circuit_label: label used to store the circuit in the database.
            remove_io_gates: boolean value based on which In/Out gates are removed or not.
    Returns:
            The cirq circuit.

    """
    args = tuple()
    if circuit_label is not None:
        args = (circuit_label,)
        sql = f"select * from {table_name} where label=%s"
    else:
        sql = f"select * from {table_name}"

    cursor = connection.cursor()
    cursor.execute(sql, args)
    tuples: list[tuple] = cursor.fetchall()

    pandora_gates: list[PandoraGate] = [PandoraGate(*tup) for tup in tuples]
    final_circ: cirq.Circuit = pandora_to_cirq(pandora_gates=pandora_gates)

    if remove_io_gates:
        return remove_io_gates_from_circuit(final_circ)
    return final_circ


def get_edge_list(connection) -> list[tuple[int, int]]:
    """
    Returns the contents from edge_list table.
    """
    sql = "select * from edge_list;"

    cursor = connection.cursor()
    cursor.execute(sql, None)
    tuples = cursor.fetchall()

    return tuples


def get_gate_types(connection,
                   gate_ids: list[int]) -> list[tuple[id, str]]:
    """
    Receives a list of gate ids and returns a list of tuples containing each id and its 
    corresponding human-readable gate name.
     Params:
            connection: the Postgres connection object
            gate_ids: list of gate ids

    Returns:
            The list of tuples.

    """
    types = []
    for gate_id in gate_ids:
        args = (gate_id,)
        sql = "select * from linked_circuit where id=%s;"
        cursor = connection.cursor()
        cursor.execute(sql, args)
        gate_tuple = cursor.fetchone()

        if gate_tuple is None:
            raise TupleNotFound

        pandora_gate = PandoraGate(*gate_tuple)
        types.append((pandora_gate.id, PANDORA_TO_READABLE[pandora_gate.type]))

    return types


def map_hack(aff,
             proc_call: str,
             verbose: bool = False) -> None:
    """
    Calls an individual stored procedure in the autocommit mode (asynchronous call) from process with rank = my_pid.
    Additionally, binds each process to a specific core by setting the affinity if the platform is linux.
    This should improve cache locality and reduce context switching.

    Params:
            proc_call: stored procedure call
            verbose: to print or not to print additional info
    Returns:
            None.
    """
    if sys.platform == "linux":
        my_pid = os.getppid()
        old_aff = os.sched_getaffinity(0)
        x = (my_pid, old_aff, os.sched_getaffinity(0))
        if verbose:
            print("My pid is {} and my old affinity was {}, my new affinity is {}".format(*x))

    connection = get_connection()
    cursor = connection.cursor()
    connection.set_session(autocommit=True)
    if verbose:
        print('Calling procedure...')
    cursor.execute(proc_call)


def db_multi_threaded(thread_proc: list[tuple[int, str]]) -> None:
    """
    Spawns n processes and maps each process to a database procedure call.
    For linux platforms, the affinity of the process is also set.
    Params:
            thread_proc: a list of tuples (n_repeat, proc) in which the first element is the number of times
            a procedure proc has to be called in parallel.
    Returns:
            None.
    """
    n_threads: int = sum([n for (n, _) in thread_proc])
    cpus = list()
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

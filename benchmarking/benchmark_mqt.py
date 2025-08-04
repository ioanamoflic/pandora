from multiprocessing import Pool

import qiskit.qasm3
from mqt.qcec import verify

from qiskit import QuantumCircuit

from pandora.connection_pool_util import init_worker, map_procedure_call
from pandora.connection_util import *

import random

from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora


def reset_pandora(connection, quantum_circuit):
    drop_and_replace_tables(connection=connection, clean=True)
    refresh_all_stored_procedures(connection=connection)

    db_tuples, _ = convert_qiskit_to_pandora(qiskit_circuit=quantum_circuit,
                                             add_margins=True,
                                             label='q')

    insert_in_batches(pandora_gates=db_tuples,
                      connection=connection,
                      table_name='linked_circuit',
                      reset_id=False)

    reset_database_id(connection=connection,
                      table_name='linked_circuit',
                      large_buffer_value=10000000)


def generate_random_cnot_circuit(num_qubits=2, num_gates=8):
    if num_qubits < 2:
        print("Warning: num_qubits must be at least 2 for a CNOT gate. Setting to 2.")
        num_qubits = 2

    qc = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(num_gates):
        control_qubit = random.randint(0, num_qubits - 1)
        target_qubit = control_qubit
        while target_qubit == control_qubit:
            target_qubit = random.randint(0, num_qubits - 1)

        qc.cx(control_qubit, target_qubit)

    return qc


def remove_random_gate(circuit: QuantumCircuit) -> QuantumCircuit:
    if not circuit.data:
        print("Circuit has no gates to remove.")
        return circuit

    gate_index_to_remove = random.randint(0, len(circuit.data) - 1)
    new_qc = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

    for i, instruction in enumerate(circuit.data):
        if i != gate_index_to_remove:
            new_qc.append(instruction.operation, instruction.qubits, instruction.clbits)

    return new_qc


def pandora_verify(connection,
                   process_pool,
                   nprocs,
                   circ1: QuantumCircuit,
                   circ2: QuantumCircuit,
                   timeout_sec):
    concatenated = circ1.compose(circ2.inverse())
    nr_cnots = concatenated.count_ops()['cx'] // 2
    print(nr_cnots)

    reset_pandora(connection=conn, quantum_circuit=concatenated)

    CX = PandoraGateTranslator.CXPowGate.value

    proc_calls = []
    for proc_id in range(nprocs):
        proc_calls.append(
            f"call cancel_two_qubit_equiv({CX}, {CX}, {proc_id}, {nprocs}, {concatenated.num_qubits}, {timeout_sec})")

    process_pool.map(map_procedure_call, proc_calls)

    # for now ignore this! have to deal with the links separately
    gate_count = extract_cirq_circuit(connection=connection,
                                      table_name='linked_circuit',
                                      circuit_label=None,
                                      is_test=False,
                                      remove_io_gates=True,
                                      just_count=True)
    is_equivalent = False
    if gate_count == 2 * concatenated.num_qubits:
        is_equivalent = True

    return is_equivalent


def create_pool(n_workers, config_file_path):
    return Pool(processes=n_workers, initializer=init_worker, initargs=(config_file_path,))


def close_pool(proc_pool):
    proc_pool.close()
    proc_pool.join()


if __name__ == "__main__":
    # watch "psql -p 5432 postgres -c \"select count(*) from linked_circuit;\""

    # set timeout for MQT
    timeout = 100
    NPROCS = 24
    FILENAME = None
    EQUIV = 0
    BENCH = None
    conn = None
    pool = None

    if len(sys.argv) != 4:
        sys.exit(0)
    elif len(sys.argv) == 4:
        FILENAME = sys.argv[1]
        EQUIV = int(sys.argv[2])
        BENCH = sys.argv[3]

    if BENCH == 'pandora':
        conn = get_connection(config_file_path=FILENAME)
        print(f"Running config file {FILENAME}")

    times = []

    if BENCH == 'pandora':
        pool = create_pool(n_workers=NPROCS, config_file_path=FILENAME)
        # Warmup
        pool.map(print, ".")

    for q in range(20, 21, 2):
        total = 0
        nr_runs = 10

        for i in range(nr_runs):
            if EQUIV == 0:
                print(q, i, "correct")
            else:
                print(q, i, "incorrect")

            mqt_check_time = 0

            if BENCH == 'pandora':
                circ1 = qiskit.qasm3.load(f"circ1_{q}_{i}_{EQUIV}.qasm")
                if EQUIV == 0:
                    circ2 = circ1.copy()
                else:
                    circ2 = qiskit.qasm3.load(f"circ2_{q}_{i}_{EQUIV}.qasm")

                start_time_pandora = time.time()
                equiv = pandora_verify(connection=conn,
                                       circ1=circ1,
                                       circ2=circ2,
                                       process_pool=pool,
                                       nprocs=NPROCS,
                                       timeout_sec=timeout)
                check_time = time.time() - start_time_pandora
                print('Pandora time: ', check_time)
                print('Equiv: ', equiv)

            else:
                circ1 = generate_random_cnot_circuit(q, q ** 3)
                with open(f"circ1_{q}_{i}_{EQUIV}.qasm", "w") as f:
                    qiskit.qasm3.dump(circ1, f)

                if EQUIV == 0:
                    circ2 = circ1.copy()
                else:
                    circ2 = remove_random_gate(circ1)
                    with open(f"circ2_{q}_{i}_{EQUIV}.qasm", "w") as f:
                        qiskit.qasm3.dump(circ2, f)

                st_time_mqt = time.time()
                result = verify(circ1, circ2,
                                timeout=timeout,
                                run_simulation_checker=False,
                                run_zx_checker=False)
                check_time = time.time() - st_time_mqt
                mqt_check_time = result.check_time
                equiv = result.equivalence
                print('MQT time: ', check_time)
                print(result.equivalence)

            total = total + check_time
            times.append((q, i, equiv, check_time, mqt_check_time, BENCH))

        print("----- ", total / nr_runs)

    with open(f'{BENCH}_{EQUIV}_verification.csv', 'a') as f:
        writer = csv.writer(f)
        for row in times:
            writer.writerow(row)

    if BENCH == 'pandora':
        close_pool(pool)
        conn.close()

import sys

import cirq
import re

from benchmarking.benchmark_pandora import reset_pandora
from pandora import PandoraOptimizer
from pandora.gate_translator import PandoraGateTranslator
from pandora.connection_util import *
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora, remove_io_gates

import re
from qiskit import QuantumCircuit

from benchmarking.benchmark_adders import get_adder, decompose_toffoli_qiskit


def decompose_toffoli_qiskit_reverse(qc, c0, c1, t):
    qc.h(t)

    qc.t(t)
    qc.t(c1)
    qc.t(c0)

    qc.cx(c0, c1)
    qc.tdg(c1)

    qc.cx(c0, c1)
    qc.cx(c0, t)

    qc.tdg(t)
    qc.cx(c1, t)

    qc.t(t)
    qc.cx(c0, t)

    qc.tdg(t)
    qc.cx(c1, t)

    qc.h(t)


def decompose_toffoli_qiskit_reverse_dagger(qc, c0, c1, t):
    qc.h(t)

    qc.tdg(t)
    qc.tdg(c1)
    qc.tdg(c0)

    qc.cx(c0, c1)
    qc.t(c1)

    qc.cx(c0, c1)
    qc.cx(c0, t)

    qc.t(t)
    qc.cx(c1, t)

    qc.tdg(t)
    qc.cx(c0, t)

    qc.t(t)
    qc.cx(c1, t)

    qc.h(t)


def replace_all_toffolis_qiskit(qc, case: int):
    new_qc = QuantumCircuit(qc.num_qubits)

    qubit_map = {qb: i for i, qb in enumerate(qc.qubits)}

    for i, inst in enumerate(qc.data):
        op = inst.operation
        qargs = inst.qubits
        cargs = inst.clbits

        if op.name == "ccx":
            c0 = qubit_map[qargs[0]]
            c1 = qubit_map[qargs[1]]
            t = qubit_map[qargs[2]]

            if i % 2 == 0:
                decompose_toffoli_qiskit(new_qc, c0, c1, t)
            else:
                if case == 0:
                    decompose_toffoli_qiskit_reverse(new_qc, c0, c1, t)
                elif case == 1:
                    decompose_toffoli_qiskit_reverse_dagger(new_qc, c0, c1, t)
        else:
            new_qc.append(op, qargs, cargs)

    return new_qc


def run_optimiser(FILEPATH):
    pandora_optimizer = PandoraOptimizer(pass_count=int(2e9),
                                         timeout=2,
                                         logger_id=1,
                                         proc_count=18)

    conn = get_connection(config_file_path=FILEPATH)
    reset_pandora(connection=conn, quantum_circuit=adder_circuit)

    """
        Single-qubit gate cancellations
    """

    H = PandoraGateTranslator.HPowGate.value
    Z = PandoraGateTranslator._PauliZ.value
    X = PandoraGateTranslator._PauliX.value
    CX = PandoraGateTranslator.CXPowGate.value
    T = PandoraGateTranslator.T.value
    T_dag = PandoraGateTranslator.T_dag.value
    S = PandoraGateTranslator.S.value
    S_dag = PandoraGateTranslator.S_dag.value
    Z_rot = PandoraGateTranslator.ZPowGate.value

    # cancelling Hadamards
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(H, H), gate_params=(0, 0), dedicated_nproc=1)

    # cancelling Z gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(Z, Z), gate_params=(0, 0), dedicated_nproc=1)

    # cancelling T+T† gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(T, T_dag), gate_params=(0, 0),
                                                dedicated_nproc=1)
    # cancelling T†+T gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(T_dag, T), gate_params=(0, 0),
                                                dedicated_nproc=1)

    # cancelling S+S† gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(S, S_dag), gate_params=(0, 0),
                                                dedicated_nproc=1)
    # cancelling S†+S gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(S_dag, S), gate_params=(0, 0),
                                                dedicated_nproc=1)

    # cancelling X gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(X, X), gate_params=(0, 0), dedicated_nproc=1)

    """
        Two-qubit gate cancellations
    """

    # cancelling CX gates
    pandora_optimizer.cancel_two_qubit_gates(gate_types=(CX, CX), gate_param=0, dedicated_nproc=1)

    """
        Fusing gates
    """

    # TT = S
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(T, T, S), gate_params=(0, 0, 0),
                                              dedicated_nproc=1)
    # T†T† = S†
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(T_dag, T_dag, S_dag), gate_params=(0, 0, 0),
                                              dedicated_nproc=1)
    # SS = Z
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(S, S, Z), gate_params=(0, 0, 0),
                                              dedicated_nproc=1)
    # S†S† = Z
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(S_dag, S_dag, Z), gate_params=(0, 0, 0),
                                              dedicated_nproc=1)
    """
        Commuting Z-rotations to the left
    """

    # commute Z to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z, gate_param=0, dedicated_nproc=1)

    # commute S to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=S, gate_param=0, dedicated_nproc=1)

    # # commute S† to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=S_dag, gate_param=0, dedicated_nproc=1)

    # commute T to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=T, gate_param=0, dedicated_nproc=1)

    # # commute T† to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=T_dag, gate_param=0, dedicated_nproc=1)

    """
        Reversing CNOTs
    """
    pandora_optimizer.hhcxhh_to_cx(dedicated_nproc=1)

    """
        Start
    """
    pandora_optimizer.start(config_file_path=FILEPATH)



def extract():
    connection = get_connection()

    sql = f"select * from linked_circuit where label='q'"

    cursor = connection.cursor()
    cursor.execute(sql, )
    tuples: list[tuple] = cursor.fetchall()
    pandora_gates: list[PandoraGate] = [PandoraGate(*tup) for tup in tuples]

    extracted_circuit = pandora_to_circuit(pandora_gates=pandora_gates,
                                           circuit_type='qiskit')
    extracted_circuit = remove_io_gates(extracted_circuit)
    print("After: ")
    print(extracted_circuit)
    


if __name__ == "__main__":
    FILEPATH = sys.argv[1]

    ## CASE 0
    adder_circuit = get_adder(n_bits=1)
    adder_circuit = replace_all_toffolis_qiskit(adder_circuit, case=0)
    print('Before:')
    print(adder_circuit)
    run_optimiser(FILEPATH)
    extract()
    
    ## CASE 1    
    adder_circuit = get_adder(n_bits=1)
    adder_circuit = replace_all_toffolis_qiskit(adder_circuit, case=1)    
    print('Before:')
    print(adder_circuit)
    run_optimiser(FILEPATH)
    extract()
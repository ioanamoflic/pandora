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


def parse_controls(ctr_str):
    """
        Parse control qubits list.
        + = filled control
        - = hollow control
    """
    if not ctr_str:
        return []
    ctr = []
    for match in re.finditer(r'([+-])(\d+)', ctr_str):
        polarity, idx = match.groups()
        ctr.append((int(idx), polarity == '+'))
    return ctr


def apply_not_with_controls(qc, target, controls):
    """
        Apply the controlled-NOT gate to the circuit.
        Adds additional X gates for hollow Toffoli controls.
    """
    if not controls:
        qc.x(target)
    elif len(controls) == 1:
        control, polarity = controls[0]
        if polarity:
            qc.cx(control, target)
        else:
            qc.x(control)
            qc.cx(control, target)
            qc.x(control)
    elif len(controls) == 2:
        for c, p in controls:
            if not p:
                qc.x(c)
        control_ids = [cp[0] for cp in controls]
        qc.ccx(*control_ids, target_qubit=target)
        for c, p in controls:
            if not p:
                qc.x(c)
    else:
        raise "Issue occurred, too many controls."


def get_adder(n_bits: int):
    n_qubits = 3 * n_bits
    qc = QuantumCircuit(n_qubits)

    # Adders from https://github.com/njross/optimizer/tree/master/QFT_and_Adders
    with open(f"benchmarking/adders/Adder{n_bits}.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("QGate[\"not\"]"):
                target = int(re.search(r'\((\d+)\)', line).group(1))
                control_match = re.search(r'controls=\[([^\]]*)\]', line)
                control_str = control_match.group(1) if control_match else ''
                controls = parse_controls(control_str)
                apply_not_with_controls(qc, target, controls)
    return qc


def decompose_toffoli_qiskit(qc, c0, c1, t):
    qc.h(t)

    qc.cx(c1, t)
    qc.tdg(t)

    qc.cx(c0, t)
    qc.t(t)

    qc.cx(c1, t)
    qc.tdg(t)

    qc.cx(c0, t)
    qc.cx(c0, c1)

    qc.tdg(c1)
    qc.cx(c0, c1)

    qc.t(c0)
    qc.t(c1)
    qc.t(t)

    qc.h(t)


def replace_all_toffolis_qiskit(qc):
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

            decompose_toffoli_qiskit(new_qc, c0, c1, t)

        else:
            new_qc.append(op, qargs, cargs)

    return new_qc


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Exiting...")
        sys.exit(0)
    else:
        FILEPATH = sys.argv[1]        
    
    for N_BITS in [8, 16, 32, 64, 128, 512, 1024, 2048]:
        adder_circuit = get_adder(n_bits=N_BITS)
        adder_circuit = replace_all_toffolis_qiskit(adder_circuit)

        pandora_optimizer = PandoraOptimizer(pass_count=int(2e9),
                                            timeout=600,
                                            logger_id=N_BITS,
                                            proc_count=20)

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

        pandora_optimizer.cx_to_hhcxhh(dedicated_nproc=1)
        pandora_optimizer.hhcxhh_to_cx(dedicated_nproc=1)

        """
            Log
        """

        pandora_optimizer.log()

        """
            Start
        """
        pandora_optimizer.start(config_file_path=FILEPATH)

        """
            For plotting
        """
        pandora_optimizer.generate_csv(logger_id=N_BITS)
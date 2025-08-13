import sys

import cirq
import re

from pandora import PandoraOptimizer
from pandora.gate_translator import PandoraGateTranslator


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


def apply_not_with_controls(circuit, target_idx, controls, qubits):
    """
        Apply the controlled-NOT gate to the circuit.
        Adds additional X gates for hollow Toffoli controls.
    """
    target = qubits[target_idx]
    if not controls:
        circuit.append(cirq.X(target))
    elif len(controls) == 1:
        idx, polarity = controls[0]
        control = qubits[idx]
        if polarity:
            circuit.append(cirq.X(target).controlled_by(control))
        else:
            circuit.append(cirq.X(control))
            circuit.append(cirq.X(target).controlled_by(control))
            circuit.append(cirq.X(control))
    else:
        control_qubits = [qubits[i] for i, _ in controls]
        for ctrl_id, p in controls:
            if not p:
                circuit.append(cirq.X(qubits[ctrl_id]))
        circuit.append(cirq.X(target).controlled_by(*control_qubits))
        for ctrl_id, p in controls:
            if not p:
                circuit.append(cirq.X(qubits[ctrl_id]))


def get_adder(n_bits: int):
    cirq_circuit = cirq.Circuit()
    qubits = [cirq.NamedQubit(f'q{i}') for i in range(3 * n_bits)]

    # Adders from https://github.com/njross/optimizer/tree/master/QFT_and_Adders
    with open(f"benchmarking/adders/Adder{n_bits}.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("QGate[\"not\"]"):
                target_id = int(re.search(r'\((\d+)\)', line).group(1))
                control_match = re.search(r'controls=\[([^\]]*)\]', line)
                control_str = control_match.group(1) if control_match else ''
                control_list = parse_controls(control_str)
                apply_not_with_controls(cirq_circuit, target_id, control_list, qubits)

    return cirq_circuit


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Exiting...")
        sys.exit(0)
    else:
        N_BITS = int(sys.argv[1])

    adder_circuit = get_adder(n_bits=N_BITS)

    NPROCS = 1
    FILENAME = sys.argv[1]
    from benchmark_mqt import create_pool, close_pool, reset_pandora, get_connection, map_procedure_call
    conn = get_connection(config_file_path=FILENAME)
    pool = create_pool(n_workers=NPROCS, config_file_path=FILENAME)
    # Warmup
    pool.map(print, ".")
    reset_pandora(connection=conn, quantum_circuit=adder_circuit)

    CX = PandoraGateTranslator.CXPowGate.value
    myH = PandoraGateTranslator.HPowGate.value
    myCX = PandoraGateTranslator.CXPowGate.value
    myZPow = PandoraGateTranslator.ZPowGate.value
    myPauliX = PandoraGateTranslator._PauliX.value
    myPauliZ = PandoraGateTranslator._PauliZ.value

    nprocs = NPROCS
    larger_pass_count = 1000
    stop_after = 5
    proc_calls = [
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

    pool.map(map_procedure_call, proc_calls)

    pool.close()
    pool.join()
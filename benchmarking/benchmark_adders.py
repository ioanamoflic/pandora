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
    with open(f"adders/Adder{n_bits}.txt", "r") as f:
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
    adder_circuit = get_adder(n_bits=8)

    pandora_optimizer = PandoraOptimizer(utilize_bernoulli=True,
                                         bernoulli_percentage=5,
                                         timeout=500,
                                         logger_id=8,
                                         nproc=4)
    pandora_optimizer.build_circuit(circuit=adder_circuit)

    # decompose Toffoli gates in Pandora
    pandora_optimizer.decompose_toffolis()

    """
        Single-qubit gate cancellations
    """

    H = PandoraGateTranslator.HPowGate.value
    Z = PandoraGateTranslator._PauliZ.value
    X = PandoraGateTranslator._PauliX.value
    Z_rot = PandoraGateTranslator.ZPowGate.value
    CX = PandoraGateTranslator.CXPowGate.value

    # cancelling Hadamards
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(H, H), gate_params=(1, 1), dedicated_nproc=1)
    # cancelling Z gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(Z, Z), gate_params=(1, 1), dedicated_nproc=1)
    # cancelling T+T† gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(Z_rot, Z_rot), gate_params=(0.25, -0.25), dedicated_nproc=1)
    # cancelling S+S† gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(Z_rot, Z_rot), gate_params=(0.5, -0.5), dedicated_nproc=1)
    # cancelling X gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(X, X), gate_params=(1, 1), dedicated_nproc=1)

    """
        Two-qubit gate cancellations
    """

    # cancelling CX gates
    pandora_optimizer.cancel_single_qubit_gates(gate_types=(CX, CX), gate_params=(1, 1), dedicated_nproc=1)
    """
        Fusing gates
    """

    # TT = S
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(Z_rot, Z_rot, Z_rot), gate_params=(0.25, 0.25, 0.5),
                                              dedicated_nproc=1)
    # T†T† = S†
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(Z_rot, Z_rot, Z_rot), gate_params=(-0.25, -0.25, -0.5),
                                              dedicated_nproc=1)
    # SS = Z
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(Z_rot, Z_rot, Z_rot), gate_params=(0.5, 0.5, 1.0),
                                              dedicated_nproc=1)
    # S†S† = Z
    pandora_optimizer.fuse_single_qubit_gates(gate_types=(Z_rot, Z_rot, Z), gate_params=(-0.5, -0.5, 1.0),
                                              dedicated_nproc=1)
    """
        Commuting Z-rotations to the left
    """

    # commute Z to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z, gate_param=1, dedicated_nproc=1)
    # commute S to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z_rot, gate_param=0.5, dedicated_nproc=1)
    # commute S† to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z_rot, gate_param=-0.5, dedicated_nproc=1)
    # commute T to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z_rot, gate_param=0.25, dedicated_nproc=1)
    # commute T† to the left
    pandora_optimizer.commute_rotation_with_control_left(gate_type=Z_rot, gate_param=-0.25, dedicated_nproc=1)

    """
        Reversing CNOTs
    """

    pandora_optimizer.hhcxhh_to_cx(dedicated_nproc=1)
    pandora_optimizer.cx_to_hhcxhh(dedicated_nproc=1)

    """
        Log
    """

    pandora_optimizer.log()

    """
        Start
    """
    pandora_optimizer.start()

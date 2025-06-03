import cirq
import re

from pandora import Pandora


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

    pandora = Pandora()
    pandora.build_circuit(circuit=adder_circuit)
    pandora.decompose_toffolis()








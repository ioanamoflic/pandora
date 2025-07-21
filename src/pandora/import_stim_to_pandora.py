import sys
import stim
import cirq
from pandora.cirq_to_pandora_util import cirq_to_pandora
from pandora.connection_util import get_connection, insert_in_batches

def parse_stim_clifford_gates(stim_circuit):
    """
    Convert a stim.Circuit to a list of Cirq operations, keeping only Clifford gates and measurement.
    """
    ops = []
    qubit_map = {}
    # Define Clifford gate arity
    single_qubit_gates = {'H', 'X', 'Y', 'Z', 'S', 'S_DAG'}
    two_qubit_gates = {'CX', 'CNOT', 'CZ'}
    measure_gates = {'M'}
    allowed_gates = single_qubit_gates | two_qubit_gates | measure_gates
    for name, targets, arg in stim_circuit.flattened_operations():
        if name not in allowed_gates:
            continue
        # Map stim qubit indices to Cirq qubits
        cirq_targets = []
        for t in targets:
            if isinstance(t, int):
                if t not in qubit_map:
                    qubit_map[t] = cirq.LineQubit(t)
                cirq_targets.append(qubit_map[t])
            elif isinstance(t, tuple) and t[0] == 'inv':
                # Measurement with inversion: treat as normal measurement for now
                if t[1] not in qubit_map:
                    qubit_map[t[1]] = cirq.LineQubit(t[1])
                cirq_targets.append(qubit_map[t[1]])
        # Apply gates
        if name in single_qubit_gates:
            for q in cirq_targets:
                if name == 'H':
                    ops.append(cirq.H.on(q))
                elif name == 'X':
                    ops.append(cirq.X.on(q))
                elif name == 'Y':
                    ops.append(cirq.Y.on(q))
                elif name == 'Z':
                    ops.append(cirq.Z.on(q))
                elif name == 'S':
                    ops.append(cirq.S.on(q))
                elif name == 'S_DAG':
                    ops.append(cirq.S.on(q)**-1)
        elif name in two_qubit_gates:
            # Group targets in pairs
            if len(cirq_targets) % 2 != 0:
                print(f"[WARN] Odd number of targets for {name}: {cirq_targets}")
            for i in range(0, len(cirq_targets)-1, 2):
                q1, q2 = cirq_targets[i], cirq_targets[i+1]
                if name in {'CX', 'CNOT'}:
                    ops.append(cirq.CNOT.on(q1, q2))
                elif name == 'CZ':
                    ops.append(cirq.CZ.on(q1, q2))
        elif name in measure_gates:
            for q in cirq_targets:
                ops.append(cirq.measure(q))
    return ops

def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <stim_file>")
        sys.exit(1)
    stim_file = sys.argv[1]
    with open(stim_file, 'r') as f:
        stim_text = f.read()
    
    stim_circuit = stim.Circuit(stim_text)
    ops = parse_stim_clifford_gates(stim_circuit)
    print(f"Imported {len(ops)} Clifford gate/measurement operations from {stim_file}")
    
    cirq_circuit = cirq.Circuit(ops)
    
    pandora_gates, _ = cirq_to_pandora(cirq_circuit, last_id=0, label="stim_import", add_margins=True)
    connection = get_connection()
    
    insert_in_batches(pandora_gates = list(pandora_gates), connection= connection, table_name= 'linked_circuit')

    print(f"Converted to {len(list(pandora_gates))} PandoraGate objects.")

if __name__ == "__main__":
    main()
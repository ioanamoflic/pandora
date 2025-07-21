import sys
import stim
import cirq
from pandora.connection_util import extract_cirq_circuit

def pandora_to_stim():
    """
    Convert a Cirq circuit to a stim.Circuit, keeping only Clifford gates and measurement.
    """
    if len(sys.argv) < 2:
        print("Usage: python export_stim_form_pandora.py <input_circuit>")
        sys.exit(1)

    input_circuit = sys.argv[1]
    cirq_circuit = extract_cirq_circuit(input_circuit)
    
    stim_circuit = stim.Circuit()
    
    for op in cirq_circuit.all_operations():
        if isinstance(op.gate, cirq.CliffordGate):
            targets = [t.x for t in op.qubits]
            if isinstance(op.gate, cirq.HPowGate):
                stim_circuit.append_operation('H', targets)
            elif isinstance(op.gate, cirq.XPowGate):
                stim_circuit.append_operation('X', targets)
            elif isinstance(op.gate, cirq.YPowGate):
                stim_circuit.append_operation('Y', targets)
            elif isinstance(op.gate, cirq.ZPowGate):
                stim_circuit.append_operation('Z', targets)
            elif isinstance(op.gate, cirq.SPowGate):
                stim_circuit.append_operation('S', targets)
            elif isinstance(op.gate, cirq.SwapPowGate):
                if len(targets) == 2:
                    stim_circuit.append_operation('CX', targets)
            elif isinstance(op.gate, cirq.MeasurementGate):
                stim_circuit.append_operation('M', targets)

    print(stim_circuit)
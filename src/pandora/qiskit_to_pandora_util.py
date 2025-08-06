from qiskit.converters import circuit_to_dag, dag_to_circuit

from pandora.gate_translator import MAX_QUBITS_PER_GATE, QISKIT_TO_PANDORA, PandoraGateTranslator
from pandora.gates import PandoraGate

from qiskit import QuantumCircuit
from qiskit.circuit import Measure, CircuitInstruction

from typing import Dict

from pandora.pandora_util import get_link_id, get_gate_id, get_gate_port


def remove_io_gates(circuit):
    dag = circuit_to_dag(circuit)

    for node in list(dag.op_nodes()):
        if node.op.label in ["In", "Out"]:
            dag.remove_op_node(node)

    return dag_to_circuit(dag)


def qiskit_operation_to_pandora_gate(instr: CircuitInstruction,
                                     meas_key_dict: Dict[str, int]) -> PandoraGate:
    """
     This method will partially convert a qiskit.CircuitInstruction object to a Pandora gate by populating the
        * gate_code
        * gate_parameter
        * switch
        * is_classically_controlled
        * measurement_key
        fields.
    """
    op = instr.operation

    # get operation name
    qiskit_class_name = op.name
    num_qubits = op.num_qubits

    switch = False
    if num_qubits == 2 and hasattr(op, "qargs"):
        q0, q1 = op.qargs
        switch = q0.index < q1.index

    is_classically_controlled = False

    if isinstance(op, Measure):
        qubit_index = instr.qubits[0]._index

        key = f"m_{qubit_index}"
        if key not in meas_key_dict:
            meas_key_dict[key] = len(meas_key_dict)

        pandora_gate_code = PandoraGateTranslator.M.value
        measurement_key = meas_key_dict[key]
        parameter = 0
        global_shift = 0

    else:
        if qiskit_class_name not in QISKIT_TO_PANDORA.keys():
            raise Exception(f"Unsupported gate: {qiskit_class_name}")

        pandora_gate_code = QISKIT_TO_PANDORA[qiskit_class_name]

        measurement_key = None
        global_shift = 0

        parameter = float(op.params[0]) if op.params else 0

    return PandoraGate(
        gate_code=pandora_gate_code,
        gate_parameter=parameter,
        switch=switch,
        global_shift=global_shift,
        is_classically_controlled=is_classically_controlled,
        measurement_key=measurement_key
    )


def convert_qiskit_to_pandora(qiskit_circuit: QuantumCircuit,
                              label="",
                              add_margins=True):
    """
        Fast method which converts a qiskit circuit into a list of tuples which can be used as database entries.

        Args:

            qiskit_circuit: the circuit that is inserted into the database
            label: a string which describes the circuit and can be later used for retrieving the circuit from the
                database
            add_margins

        Returns:
            A list of tuples where each tuple describes a circuit operation.
    """
    pandora_gates = {}
    latest_link_id_on_qubit = {}
    last_gate_id = 0

    # Add In/Out margin gates
    if add_margins:
        circuit_in = QuantumCircuit(qiskit_circuit.num_qubits)
        circuit_out = QuantumCircuit(qiskit_circuit.num_qubits)

        in_gate_instr = QuantumCircuit(1, name="In").to_instruction(label="In")
        out_gate_instr = QuantumCircuit(1, name="Out").to_instruction(label="Out")

        for i in range(qiskit_circuit.num_qubits):
            circuit_in.append(in_gate_instr, [i])
            circuit_out.append(out_gate_instr, [i])

        qiskit_circuit = circuit_in.compose(qiskit_circuit)
        qiskit_circuit = qiskit_circuit.compose(circuit_out)

    for circuit_instruction in qiskit_circuit.data:
        instr, qargs, cargs = circuit_instruction

        if instr.label == "In":
            # store link_id
            # latest_link_id_on_qubit[qargs[0]] = last_gate_id * 10
            latest_link_id_on_qubit[qargs[0]] = get_link_id(last_gate_id, 0, PandoraGateTranslator.In.value)

            # gate_code in PandoraGate is gate_type in LinkID
            pandora_gates[last_gate_id] = PandoraGate(
                gate_id=last_gate_id,
                gate_code=PandoraGateTranslator.In.value,
                label=label
            )
            last_gate_id += 1
            continue

        # ignore barriers
        if instr.name == 'barrier':
            continue

        current_gate: PandoraGate = qiskit_operation_to_pandora_gate(circuit_instruction, meas_key_dict={})
        current_gate.id = last_gate_id
        current_gate.label = label

        """
            Build the previous links
        """
        prev_link_ids = [latest_link_id_on_qubit[q] for q in qargs]
        # Padding to the maximum number of ports per gate supported in Pandora.
        # For example, a CNOT might have only two ports, but Pandora needs three
        while len(prev_link_ids) < MAX_QUBITS_PER_GATE:
            prev_link_ids.append(None)
        current_gate.prev_q1, current_gate.prev_q2, current_gate.prev_q3 = prev_link_ids[:3]

        """
            Build the next links and store the current link_ids
        """
        for q_idx, q in enumerate(qargs):
            # compute previous gate_id and previous port_number
            # previous_gate_id, previous_port_number = divmod(latest_link_id_on_qubit[q], 10)
            previous_gate_id = get_gate_id(latest_link_id_on_qubit[q])
            previous_port_number = get_gate_port(latest_link_id_on_qubit[q])

            # compute new link_id
            # n_link_id = last_gate_id * 10 + q_idx
            n_link_id = get_link_id(last_gate_id, q_idx, current_gate.type)

            # store link_id
            latest_link_id_on_qubit[q] = n_link_id

            # make connection to next
            setattr(pandora_gates[previous_gate_id], f'next_q{previous_port_number + 1}', n_link_id)

        pandora_gates[last_gate_id] = current_gate
        last_gate_id += 1

    return pandora_gates.values(), last_gate_id

from typing import Optional
import cirq

from pandora.exceptions import *
from pandora.gate_translator import In, Out, PandoraGateTranslator, \
    TWO_QUBIT_GATES, SINGLE_QUBIT_GATES, MAX_QUBITS_PER_GATE, \
    REQUIRES_ROTATION, REQUIRES_EXPONENT

from pandora.gates import PandoraGate, PandoraGateWrapper


def remove_classically_controlled_ops(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Removes classically controlled operations from a cirq circuit.
    """
    new_circuit = cirq.Circuit()
    for op in circuit.all_operations():
        new_circuit.append(op.without_classical_controls())
    return new_circuit


def remove_measurements(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Removes cirq.MeasurementGate and cirq.ResetChannel from a cirq circuit.
    """
    new_circuit = cirq.Circuit()
    for op in circuit.all_operations():
        gate = op.without_classical_controls().gate
        if not isinstance(gate, cirq.MeasurementGate) and not isinstance(gate, cirq.ResetChannel):
            new_circuit.append(op)
    return new_circuit


def cirq_operation_to_pandora_gate(operation: cirq.Operation) -> PandoraGate:
    """
    This method will partially convert a cirq.Operation object to a Pandora gate by populating the
    * gate_code
    * gate_parameter
    * switch
    * is_classically_controlled
    * measurement_key
    fields. the rest of the fields in the PandoraGate object will be populated in cirq_to_db.
    """
    # boolean value which tells whether the operation is classically controlled or not
    is_classically_controlled = len(operation.classical_controls) > 0
    # gate object in cirq
    cirq_gate = operation.without_classical_controls().gate

    # CNOT direction (control up or down)
    switch = False
    if len(operation.qubits) == 2:
        switch = operation.qubits[0] < operation.qubits[1]

    # cirq gate class name will be used by the pandora gate translator
    if isinstance(cirq_gate, cirq.MeasurementGate):
        pandora_gate_code, measurement_key = PandoraGateTranslator.M.value, cirq_gate.key
    else:
        """
            Translation between Cirq and Pandora:
            * get the class name from cirq
            * get a list of all the members of the translator
            * check that the cirq class name is supported by the translator
            * by convention the translated name uses the cirq class name. e.g. cirq._PauliX -> translator._PauliX
        """
        cirq_class_name = cirq_gate.__class__.__name__
        if cirq_class_name not in list(PandoraGateTranslator.__members__):
            print(cirq_class_name)
            print(cirq_gate.bloq)
            raise CirqGateHasNoPandoraEquivalent

        # Build the translation starting from the cirq class name
        enum_value = eval(f'PandoraGateTranslator.{cirq_class_name}.value')
        pandora_gate_code, measurement_key = enum_value, None

    parameter = 0
    global_shift = 0

    if pandora_gate_code in REQUIRES_ROTATION:
        parameter = cirq_gate._rads
    if pandora_gate_code in REQUIRES_EXPONENT:
        parameter = cirq_gate.exponent
        global_shift = cirq_gate.global_shift

    return PandoraGate(gate_code=pandora_gate_code,
                       gate_parameter=parameter,
                       switch=switch,
                       global_shift=global_shift,
                       is_classically_controlled=is_classically_controlled,
                       measurement_key=measurement_key)


def wrap_pandora_gates(pandora_gates: list[PandoraGate]) -> dict[int, PandoraGateWrapper]:
    """
    Maps each raw Pandora gate in the input list to its wrapped version.
    Returns a dictionary where each key is a gate id and the value is the corresponding PandoraGate object
    """
    pandora_gate_id_map = {}
    for gate in pandora_gates:
        wrapped = PandoraGateWrapper(pandora_gate=gate)
        if gate.type == PandoraGateTranslator.In.value:
            wrapped.moment = 0
        pandora_gate_id_map[gate.id] = wrapped
    return pandora_gate_id_map


def sort_pandora_wrapped_by_moment(pandora_gate_id_map: dict[int, PandoraGateWrapper]):
    """
    This method receives a dictionary of (id, PandoraGateWrapped) and returns a list of PandoraGateWrapped objects
    sorted by the moment each pandora gate would appear in the reconstructed cirq Circuit.

    Note that this only works for gates acting on at most two qubits.
    """
    default_moment = -1
    all_are_marked = False

    while all_are_marked is False:
        all_are_marked = True
        for current_wrapped_gate in pandora_gate_id_map.values():
            # gate already has an assigned moment
            if current_wrapped_gate.moment != default_moment:
                continue

            current_gate_code = current_wrapped_gate.pandora_gate.type

            # single qubit case
            if current_gate_code in SINGLE_QUBIT_GATES:
                if current_wrapped_gate.prev_id1 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError
                prev_wrapped_gate = pandora_gate_id_map[current_wrapped_gate.prev_id1]
                if prev_wrapped_gate.moment != default_moment:
                    current_wrapped_gate.moment = prev_wrapped_gate.moment + 1
                else:
                    all_are_marked = False

            # two qubit case
            if current_gate_code in TWO_QUBIT_GATES:
                # two qubit gate following two qubit gate
                if current_wrapped_gate.prev_id1 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError

                if current_wrapped_gate.prev_id2 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError

                prev_wrapped_gate_q1 = pandora_gate_id_map[current_wrapped_gate.prev_id1]
                prev_wrapped_gate_q2 = pandora_gate_id_map[current_wrapped_gate.prev_id2]
                prev_q1_id = prev_wrapped_gate_q1.pandora_gate.id
                prev_q2_id = prev_wrapped_gate_q2.pandora_gate.id

                if prev_q1_id == prev_q2_id:
                    if prev_wrapped_gate_q1.moment != default_moment:
                        current_wrapped_gate.moment = prev_wrapped_gate_q1.moment + 1
                    else:
                        all_are_marked = False

                # two qubit gate following some other gates
                if prev_q1_id != prev_q2_id:
                    if default_moment not in [prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment]:
                        current_wrapped_gate.moment = max(prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment) + 1
                    else:
                        all_are_marked = False

    assert all([wrapped.moment != default_moment for wrapped in pandora_gate_id_map.values()])
    return sorted(pandora_gate_id_map.values(), key=lambda wrapped: (wrapped.moment,
                                                                     wrapped.pandora_gate.id))


def pandora_to_cirq(pandora_gates: list[PandoraGate]) -> cirq.Circuit:
    """
    Takes a list of Pandora gates (unwrapped) and returns the corresponding cirq Circuit.
    """
    pandora_gate_id_map = wrap_pandora_gates(pandora_gates=pandora_gates)
    sorted_gates = sort_pandora_wrapped_by_moment(pandora_gate_id_map)
    sorted_ids = [wrapped.pandora_gate.id for wrapped in sorted_gates]

    rh = dict(zip(sorted_ids, sorted_gates))

    n_qubits = 0
    for wrapped in rh.values():
        if wrapped.pandora_gate.type == PandoraGateTranslator.In.value:
            wrapped.q1 = n_qubits
            n_qubits += 1

    for wrapped in rh.values():
        wrapped_id = wrapped.pandora_gate.id

        # find q1 for single qubit gate
        if wrapped.pandora_gate.type in SINGLE_QUBIT_GATES:
            if wrapped.pandora_gate.type != PandoraGateTranslator.In.value:
                prev_wrapped_gate = rh[wrapped.prev_id1]
                if prev_wrapped_gate.next_id1 == wrapped_id:
                    wrapped.q1 = prev_wrapped_gate.q1
                elif prev_wrapped_gate.next_id2 == wrapped_id:
                    wrapped.q1 = prev_wrapped_gate.q2

        # find q1, q2 for two qubit gate
        if wrapped.pandora_gate.type in TWO_QUBIT_GATES:
            # previous gate is two qubit gate on same q1 q2
            if wrapped.prev_id1 == wrapped.prev_id2:
                previous_wrapped_gate = rh[wrapped.prev_id1]
                if previous_wrapped_gate.pandora_gate.switch == wrapped.pandora_gate.switch:
                    wrapped.q1, wrapped.q2 = previous_wrapped_gate.q1, previous_wrapped_gate.q2
                else:
                    wrapped.q1, wrapped.q2 = previous_wrapped_gate.q2, previous_wrapped_gate.q1
            else:
                # previous gates are different for q1 q2
                previous_wrapped_q1 = rh[wrapped.prev_id1]
                previous_wrapped_q2 = rh[wrapped.prev_id2]

                if previous_wrapped_q1.next_id1 == wrapped_id:
                    wrapped.q1 = previous_wrapped_q1.q1
                elif previous_wrapped_q1.next_id2 == wrapped_id:
                    wrapped.q1 = previous_wrapped_q1.q2

                if previous_wrapped_q2.next_id1 == wrapped_id:
                    wrapped.q2 = previous_wrapped_q2.q1
                elif previous_wrapped_q2.next_id2 == wrapped_id:
                    wrapped.q2 = previous_wrapped_q2.q2

    wrapped_gates: list = rh.values()
    circuit = pandora_wrapped_to_circuit(wrapped_gates=wrapped_gates, n_qubits=n_qubits)
    return circuit


def pandora_wrapped_to_circuit(wrapped_gates: list[PandoraGateWrapper],
                               n_qubits: int) -> cirq.Circuit:
    """
    Take a list of PandoraGateWrapper objects and return the corresponding cirq Circuit.
    """
    circuit = cirq.Circuit()
    q = [cirq.NamedQubit(str(j)) for j in range(n_qubits)]

    for wrapped in wrapped_gates:
        if wrapped.prev_id1 is None and wrapped.next_id1 is None:
            raise PandoraWrappedGateMissingLinks
        cirq_op = wrapped.to_cirq_operation()
        cirq_qubits = wrapped.get_gate_qubits_from_list(q)
        circuit.append(cirq_op.on(*cirq_qubits))

    return circuit


def cirq_to_pandora(cirq_circuit: cirq.Circuit,
                    last_id: int,
                    label: Optional[str] = None,
                    add_margins=False
                    ) -> tuple[[PandoraGate], int]:
    """
    Fast method which converts a cirq circuit into a list of tuples which can be used as database entries.

    Args:

        cirq_circuit: the circuit that is inserted into the database
        last_id: the id of the first tuple that is inserted in the database.
        label: a string which describes the circuit and can be later used for retrieving the circuit from the database
        add_margins

    Returns:
        A list of tuples where each tuple describes a circuit operation.
    """
    # dict of pandora gates; key is the gate_id, value is the PandoraGate object
    pandora_gates = {}

    # last id concatenated with gate wire on each qubit
    # the convention is that we concatenate to the id a value between 1-3 as follows:
    # * (1) for control or single qubit gate;
    # * (2) for target or second control
    # * (3) for target
    latest_conc_on_qubit = {}

    # the permutation of the qubits depends on the ordering of the In gates
    # sorting works for now
    if add_margins:
        sorted_qubits = sorted(cirq_circuit.all_qubits())
        circuit_in = cirq.Circuit(cirq.Moment(In().on(q) for q in sorted_qubits))
        circuit_out = cirq.Circuit(cirq.Moment(Out().on(q) for q in sorted_qubits))
        cirq_circuit = circuit_in + cirq_circuit + circuit_out

    # iterate through the cirq operations of the cirq circuit
    for moment in cirq_circuit:
        for i, current_operation in enumerate(moment):
            # current gate is an initial gate with no prev values
            if isinstance(current_operation.gate, type(In())):
                latest_conc_on_qubit[current_operation.qubits[0]] = last_id * 10
                pandora_gates[last_id] = PandoraGate(gate_id=last_id,
                                                     gate_code=PandoraGateTranslator.In.value,
                                                     label=label)
                last_id += 1
                continue

            current_op_qubits = current_operation.qubits
            current_pandora_gate = cirq_operation_to_pandora_gate(current_operation)
            current_pandora_gate.id = last_id
            current_pandora_gate.label = label

            # fill out missing 'prev' links for the current pandora gate
            previous_concatenations = [latest_conc_on_qubit[q] for q in current_op_qubits]
            while len(previous_concatenations) < MAX_QUBITS_PER_GATE:
                previous_concatenations.append(None)
            current_pandora_gate.prev_q1 = previous_concatenations[0]
            current_pandora_gate.prev_q2 = previous_concatenations[1]
            current_pandora_gate.prev_q3 = previous_concatenations[2]

            # fill out missing 'next' links for the gates on the left
            for q_idx, q in enumerate(current_op_qubits):
                previous_id, previous_order_qubit = latest_conc_on_qubit[q] // 10, latest_conc_on_qubit[q] % 10

                conc_id = last_id * 10 + q_idx
                if previous_order_qubit == 0:
                    pandora_gates[previous_id].next_q1 = conc_id
                if previous_order_qubit == 1:
                    pandora_gates[previous_id].next_q2 = conc_id
                if previous_order_qubit == 2:
                    pandora_gates[previous_id].next_q3 = conc_id

                latest_conc_on_qubit[q] = conc_id

            pandora_gates[last_id] = current_pandora_gate
            last_id += 1

    return pandora_gates.values(), last_id
import time
from typing import Optional, Iterator, Any
import cirq

from pandora.exceptions import *
from pandora.gate_translator import In, Out, PandoraGateTranslator, \
    TWO_QUBIT_GATES, SINGLE_QUBIT_GATES, MAX_QUBITS_PER_GATE, \
    REQUIRES_ROTATION, REQUIRES_EXPONENT, PYLIQTR_ROTATION_TO_PANDORA

from pandora.gates import PandoraGate, PandoraGateWrapper
from pandora.pandora_util import get_link_id, get_gate_id, get_gate_port
from pandora.qualtran_to_pandora_util import generator_get_pandora_compatible_batch_via_pyliqtr


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


def cirq_operation_to_pandora_gate(operation: cirq.Operation, meas_key_dict: dict) -> PandoraGate:
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
        keys = meas_key_dict.keys()
        if cirq_gate.key not in keys:
            meas_key_dict[cirq_gate.key] = len(keys)
        pandora_gate_code, measurement_key = PandoraGateTranslator.M.value, meas_key_dict[cirq_gate.key]
    else:
        """
            Translation between Cirq and Pandora:
            * get the class name from cirq
            * get a list of all the members of the translator
            * check that the cirq class name is supported by the translator
            * by convention the translated name uses the cirq class name. e.g. cirq._PauliX -> translator._PauliX
        """
        cirq_class_name = cirq_gate.__class__.__name__
        # special pyLIQTR decomposition gate
        if cirq_class_name in ['rx_decomp', 'ry_decomp', 'rz_decomp']:
            cirq_class_name = PYLIQTR_ROTATION_TO_PANDORA[cirq_class_name]
        if cirq_class_name not in list(PandoraGateTranslator.__members__):
            print('Could not decompose gate ', cirq_class_name)
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

    # dictionary of keys
    meas_key_dict = {}

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
                latest_conc_on_qubit[current_operation.qubits[0]] = get_link_id(last_id, 0, PandoraGateTranslator.In.value)
                pandora_gates[last_id] = PandoraGate(gate_id=last_id,
                                                     gate_code=PandoraGateTranslator.In.value,
                                                     label=label)
                last_id += 1
                continue

            current_op_qubits = current_operation.qubits
            current_pandora_gate = cirq_operation_to_pandora_gate(current_operation, meas_key_dict=meas_key_dict)
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
                previous_gate_id = get_gate_id(latest_conc_on_qubit[q])
                previous_port_number = get_gate_port(latest_conc_on_qubit[q])

                # conc_id = last_id * 10 + q_idx
                n_link_id = get_link_id(last_id, q_idx, current_pandora_gate.type)

                setattr(pandora_gates[previous_gate_id], f'next_q{previous_port_number + 1}', n_link_id)
                latest_conc_on_qubit[q] = n_link_id

            pandora_gates[last_id] = current_pandora_gate
            last_id += 1

    # with open(f'meas_keys_{label}.json', 'w') as fp:
    #   json.dump(meas_key_dict, fp)

    return pandora_gates.values(), last_id


def windowed_cirq_to_pandora_from_op_list(op_list: list[cirq.Operation],
                                          pandora_dictionary: dict[int, PandoraGate],
                                          latest_conc_on_qubit: dict[cirq.Qid, int],
                                          last_id: int,
                                          label: Optional[str] = None,
                                          is_test: bool = False
                                          ) -> tuple[dict[int, PandoraGate], dict[cirq.Qid, int], int]:
    """
    Fast method which converts a cirq circuit into a list of tuples which can be used as database entries.

    Args:
        is_test: if test, keep initial qubit ordering in the test table to ensure reconstruction is perfect
        latest_conc_on_qubit: last id concatenated with gate wire on each qubit
                last id concatenated with gate wire on each qubit
                the convention is that we concatenate to the id a value between 1-3 as follows:
                * (1) for control or single qubit gate;
                * (2) for target or second control
                * (3) for target (three qubit gates)
        pandora_dictionary: dict of pandora gates; key is the gate_id, value is the PandoraGate object
        op_list: list of operations which need to be inserted into the database
        last_id: the id of the first tuple that is inserted in the database.
        label: a string which describes the circuit and can be later used for retrieving the circuit from the database

    Returns:
        A list of tuples where each tuple describes a circuit operation.
    """

    # dictionary of keys
    meas_key_dict = {}
    # iterate through the cirq operations of the cirq circuit
    for i, current_operation in enumerate(op_list):
        current_op_qubits = current_operation.qubits
        for qub in current_op_qubits:
            if qub not in latest_conc_on_qubit.keys():
                pandora_dictionary[last_id] = PandoraGate(gate_id=last_id,
                                                          gate_code=PandoraGateTranslator.In.value,
                                                          label=label)
                if is_test:
                    pandora_dictionary[last_id].qubit_name = str(qub)

                latest_conc_on_qubit[qub] = last_id * 10
                last_id += 1

        current_pandora_gate = cirq_operation_to_pandora_gate(current_operation, meas_key_dict=meas_key_dict)
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
            setattr(pandora_dictionary[previous_id], f'next_q{previous_order_qubit + 1}', conc_id)
            latest_conc_on_qubit[q] = conc_id

        pandora_dictionary[last_id] = current_pandora_gate
        last_id += 1

    return pandora_dictionary, latest_conc_on_qubit, last_id


def cirq_to_pandora_from_op_list(op_list: list[cirq.Operation] | Iterator[list[cirq.Operation]],
                                 label: int = None,
                                 ) -> list[PandoraGate]:
    """
    This method inserts a list of operations as if it's a single circuit.

    Args:
        op_list: list of operations which need to be inserted into the database
        label: the id of the batch

    Returns:
        A list of tuples where each tuple describes a circuit operation.
    """
    last_id = 0
    # dict of pandora gates; key is the gate_id, value is the PandoraGate object
    pandora_gates = {}

    # last id concatenated with gate wire on each qubit
    # the convention is that we concatenate to the id a value between 1-3 as follows:
    # * (1) for control or single qubit gate;
    # * (2) for target or second control
    # * (3) for target
    latest_conc_on_qubit = {}

    # dictionary of keys
    meas_key_dict = {}

    # iterate through the cirq operations of the cirq circuit
    for i, current_operation in enumerate(op_list):
        current_op_qubits = current_operation.qubits
        for qub in current_op_qubits:
            if qub not in latest_conc_on_qubit.keys():
                pandora_gates[last_id] = PandoraGate(gate_id=last_id,
                                                     gate_code=PandoraGateTranslator.In.value,
                                                     label=label)

                latest_conc_on_qubit[qub] = last_id * 10
                last_id += 1

        current_pandora_gate = cirq_operation_to_pandora_gate(current_operation, meas_key_dict=meas_key_dict)
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
            setattr(pandora_gates[previous_id], f'next_q{previous_order_qubit + 1}', conc_id)
            latest_conc_on_qubit[q] = conc_id

        pandora_gates[last_id] = current_pandora_gate
        last_id += 1

    # append Out gates at the end, this is the barrier at the end
    for q in latest_conc_on_qubit.keys():
        pandora_gates[last_id] = PandoraGate(gate_id=last_id,
                                             gate_code=PandoraGateTranslator.Out.value,
                                             label=label)

        previous_id, previous_order_qubit = latest_conc_on_qubit[q] // 10, latest_conc_on_qubit[q] % 10
        conc_id = last_id * 10
        setattr(pandora_gates[previous_id], f'next_q{previous_order_qubit + 1}', conc_id)
        last_id += 1

    return list(pandora_gates.values())


def windowed_cirq_to_pandora(circuit: Any,
                             window_size: int,
                             is_test: bool = False,
                             ) \
        -> Iterator[tuple[list[PandoraGate], float]]:
    """
    This method traverses a cirq circuit in windows of arbitrary size and returns the PandoraGate operations equivalent
    to the cirq operations in the window. Especially useful for very large circuits which do not fit into memory. The
    list of qubits in the resulting circuit will be a permutation of the original one.
    Args:
        is_test: boolean which takes qubit ordering into account during testing for 1:1 reconstruction.
        circuit: the high-level cirq circuit
        window_size: the size of each decomposition window
    Returns:
        Generator over the PandoraGate objects of each batch.
    """
    if window_size <= 1:
        raise WindowSizeError

    qubit_set = set()
    pandora_dictionary = dict()
    latest_conc_on_qubit = dict()
    last_id = 0

    batches = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=circuit,
                                                                 window_size=window_size)
    for i, (current_batch, cliff_decomp_time) in enumerate(batches):
        for op in current_batch:
            qubit_set.update(set(list(op.qubits)))

        start_cirq_to_pandora = time.time()
        # the idea is to add anything that is not null on "next link" from the pandora gates dictionary
        pandora_dictionary, latest_conc_on_qubit, last_id = windowed_cirq_to_pandora_from_op_list(
            op_list=current_batch,
            pandora_dictionary=pandora_dictionary,
            latest_conc_on_qubit=latest_conc_on_qubit,
            last_id=last_id,
            label='x',
            is_test=is_test
        )
        dictionary_copy = pandora_dictionary.copy()
        batch_elements: list[PandoraGate] = []
        for pandora_gate in dictionary_copy.values():
            if (pandora_gate.type in SINGLE_QUBIT_GATES
                and pandora_gate.next_q1 is not None) \
                    or (pandora_gate.type in TWO_QUBIT_GATES
                        and pandora_gate.next_q1 is not None
                        and pandora_gate.next_q2 is not None):
                batch_elements.append(pandora_gate)
                pandora_dictionary.pop(pandora_gate.id)

        yield batch_elements, time.time() - start_cirq_to_pandora + cliff_decomp_time

    start_final = time.time()
    final_batch: list[cirq.Operation] = [Out().on(q) for q in qubit_set]
    pandora_out_gates, _, _ = windowed_cirq_to_pandora_from_op_list(
        op_list=final_batch,
        pandora_dictionary=pandora_dictionary,
        latest_conc_on_qubit=latest_conc_on_qubit,
        last_id=last_id,
        label='x',
        is_test=is_test)
    yield list(pandora_out_gates.values()), time.time() - start_final

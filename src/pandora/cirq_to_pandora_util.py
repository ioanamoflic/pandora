import time
from typing import Optional, Iterator, Any
import cirq

from pandora.exceptions import *
from pandora.gate_translator import In, Out, PandoraGateTranslator, \
    TWO_QUBIT_GATES, SINGLE_QUBIT_GATES, MAX_QUBITS_PER_GATE, \
    REQUIRES_ROTATION, REQUIRES_EXPONENT, PYLIQTR_ROTATION_TO_PANDORA

from pandora.gates import PandoraGate, get_link_id, get_gate_id, get_gate_port
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

def cirq_to_pandora(cirq_circuit: cirq.Circuit,
                    last_id: int,
                    label: Optional[str] = None,
                    add_margins=False
                    ) -> tuple[[PandoraGate], int]:

    it = windowed_cirq_to_pandora(cirq_circuit, window_size=100, label=label)

    ret = []
    for l, last_id in it:
        ret.extend(l)

    return ret, last_id

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
    # the permutation of the qubits depends on the ordering of the In gates
    # sorting works for now
    if add_margins:
        sorted_qubits = sorted(cirq_circuit.all_qubits())

        # Add In and Out gates
        circuit_in = cirq.Circuit(cirq.Moment(In().on(q) for q in sorted_qubits))
        circuit_out = cirq.Circuit(cirq.Moment(Out().on(q) for q in sorted_qubits))

        # Merge the layers
        cirq_circuit = circuit_in + cirq_circuit + circuit_out


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
    for moment in cirq_circuit:
        for i, current_operation in enumerate(moment):
            # current gate is an initial gate with no prev values
            if isinstance(current_operation.gate, type(In())):
                pandora_gates[last_id] = PandoraGate(gate_id=last_id,
                                                     gate_type=PandoraGateTranslator.In.value,
                                                     label=label)
                latest_conc_on_qubit[current_operation.qubits[0]] = get_link_id(last_id, 0, PandoraGateTranslator.In.value)
                last_id += 1
                continue


            last_id = cirq_op_to_pandora_gate(current_operation, label, last_id, latest_conc_on_qubit, meas_key_dict,
                                              pandora_gates)

    # with open(f'meas_keys_{label}.json', 'w') as fp:
    #   json.dump(meas_key_dict, fp)

    return pandora_gates.values(), last_id


def cirq_op_to_pandora_gate(cirq_op, label: str | None, last_id: int | Any, qubit2link: dict[Any, Any],
                            meas2intkey: dict[Any, Any], id2gate: dict[Any, Any]) -> int | Any:

    # gate object in cirq
    cirq_gate = cirq_op.without_classical_controls().gate

    # cirq gate class name will be used by the pandora gate translator
    if isinstance(cirq_gate, cirq.MeasurementGate):
        # has this key been encountered before?
        if cirq_gate.key not in meas2intkey.keys():
            meas2intkey[cirq_gate.key] = len(meas2intkey.keys())

        pandora_gate_type = PandoraGateTranslator.M.value
        measurement_key = meas2intkey[cirq_gate.key]
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
        pandora_gate_type = eval(f'PandoraGateTranslator.{cirq_class_name}.value')
        measurement_key = None

    parameter = 0
    global_shift = 0
    if pandora_gate_type in REQUIRES_ROTATION:
        parameter = cirq_gate._rads
    if pandora_gate_type in REQUIRES_EXPONENT:
        parameter = cirq_gate.exponent
        global_shift = cirq_gate.global_shift


    # Boolean value which tells whether the operation is classically controlled or not
    is_classically_controlled = len(cirq_op.classical_controls) > 0
    # TODO: CNOT direction (control up or down). This looks wrong! Switch should disappear anyway.
    switch = False if len(cirq_op.qubits) != 2 else (cirq_op.qubits[0] < cirq_op.qubits[1])

    """
        Create the Pandora gate
    """
    new_gate = PandoraGate(gate_type=pandora_gate_type,
                       gate_parameter=parameter,
                       switch=switch,
                       global_shift=global_shift,
                       is_classically_controlled=is_classically_controlled,
                       measurement_key=measurement_key)
    new_gate.id = last_id
    new_gate.label = label

    """
        Backwards links:
        - Get the links on the operation's qubits
        - These will be the `previous`/backward links
    """
    previous_links = [qubit2link[q] for q in cirq_op.qubits]
    while len(previous_links) < MAX_QUBITS_PER_GATE:
        previous_links.append(None)

    new_gate.prev_q1 = previous_links[0]
    new_gate.prev_q2 = previous_links[1]
    new_gate.prev_q3 = previous_links[2]

    """
        Forwards links:
        - fill out missing 'next' links for the gates appearing before the new one
    """
    for q_idx, q in enumerate(cirq_op.qubits):
        previous_gate_id = get_gate_id(qubit2link[q])
        previous_port_number = get_gate_port(qubit2link[q])

        n_link_id = get_link_id(last_id, q_idx, new_gate.type)

        setattr(id2gate[previous_gate_id], f'next_q{previous_port_number + 1}', n_link_id)
        qubit2link[q] = n_link_id


    # Store the gate in the list
    id2gate[last_id] = new_gate
    last_id += 1

    return last_id


# def windowed_cirq_to_pandora_from_op_list(op_list: list[cirq.Operation],
#                                           pandora_dictionary: dict[int, PandoraGate],
#                                           latest_connection_on_qubit: dict[cirq.Qid, int],
#                                           last_id: int,
#                                           label: Optional[str] = None,
#                                           is_test: bool = False
#                                           ) -> tuple[dict[int, PandoraGate], dict[cirq.Qid, int], int]:
#     """
#     Fast method which converts a cirq circuit into a list of tuples which can be used as database entries.
#
#     Args:
#         is_test: if test, keep initial qubit ordering in the test table to ensure reconstruction is perfect
#         latest_connection_on_qubit: last id concatenated with gate wire on each qubit
#                 last id concatenated with gate wire on each qubit
#                 the convention is that we concatenate to the id a value between 1-3 as follows:
#                 * (1) for control or single qubit gate;
#                 * (2) for target or second control
#                 * (3) for target (three qubit gates)
#         pandora_dictionary: dict of pandora gates; key is the gate_id, value is the PandoraGate object
#         op_list: list of operations which need to be inserted into the database
#         last_id: the id of the first tuple that is inserted in the database.
#         label: a string which describes the circuit and can be later used for retrieving the circuit from the database
#
#     Returns:
#         A list of tuples where each tuple describes a circuit operation.
#     """
#
#     # dictionary of keys
#     meas_key_dict = {}
#     # iterate through the cirq operations of the cirq circuit
#     for cirq_op in op_list:
#
#         # Check that the qubits of this operation have been initialized
#         # This qubit has not been initialized, so it needs an In gate
#         for qub in cirq_op.qubits:
#             if qub not in latest_connection_on_qubit.keys():
#                 pandora_dictionary[last_id] = PandoraGate(gate_id=last_id,
#                                                           gate_code=PandoraGateTranslator.In.value,
#                                                           label=label)
#                 if is_test:
#                     pandora_dictionary[last_id].qubit_name = str(qub)
#
#                 latest_connection_on_qubit[qub] = get_link_id(last_id, 0, PandoraGateTranslator.In.value)
#                 last_id += 1
#
#         last_id = some_duplicate_method(cirq_op.qubits, cirq_op, label, last_id, latest_connection_on_qubit,
#                                         meas_key_dict, pandora_dictionary)
#
#     return pandora_dictionary, latest_connection_on_qubit, last_id


def cirq_to_pandora_from_op_list(op_list: list[cirq.Operation] | Iterator[list[cirq.Operation]],
                                 label: int = None,
                                 ) -> list[PandoraGate]:

    it = windowed_cirq_to_pandora(op_list, window_size=100, label=label)

    ret = []
    for l, _ in it:
        ret.extend(l)
    return ret

    # """
    # This method inserts a list of operations as if it's a single circuit.
    #
    # Args:
    #     op_list: list of operations which need to be inserted into the database
    #     label: the id of the batch
    #
    # Returns:
    #     A list of tuples where each tuple describes a circuit operation.
    # """
    # last_id = 0
    #
    # # dict of pandora gates; key is the gate_id, value is the PandoraGate object
    # pandora_gates = {}
    #
    # # last id concatenated with gate wire on each qubit
    # # the convention is that we concatenate to the id a value between 1-3 as follows:
    # # * (1) for control or single qubit gate;
    # # * (2) for target or second control
    # # * (3) for target
    # latest_conc_on_qubit = {}
    #
    # # dictionary of keys
    # meas_key_dict = {}
    #
    # # iterate through the cirq operations of the cirq circuit
    # for i, current_operation in enumerate(op_list):
    #     current_op_qubits = current_operation.qubits
    #     for qub in current_op_qubits:
    #         if qub not in latest_conc_on_qubit.keys():
    #             pandora_gates[last_id] = PandoraGate(gate_id=last_id,
    #                                                  gate_type=PandoraGateTranslator.In.value,
    #                                                  label=label)
    #
    #             latest_conc_on_qubit[qub] = get_link_id(last_id, 0, PandoraGateTranslator.In.value)
    #             last_id += 1
    #
    #     last_id = cirq_op_to_pandora_gate(current_operation, label, last_id, latest_conc_on_qubit, meas_key_dict,
    #                                       pandora_gates)
    #
    # # append Out gates at the end, this is the barrier at the end
    # for q in latest_conc_on_qubit.keys():
    #     pandora_gates[last_id] = PandoraGate(gate_id=last_id,
    #                                          gate_type=PandoraGateTranslator.Out.value,
    #                                          label=label)
    #
    #     previous_id, previous_order_qubit = latest_conc_on_qubit[q] // 10, latest_conc_on_qubit[q] % 10
    #     conc_id = last_id * 10
    #     setattr(pandora_gates[previous_id], f'next_q{previous_order_qubit + 1}', conc_id)
    #     last_id += 1
    #
    # return list(pandora_gates.values())


def windowed_cirq_to_pandora(circuit: Any, window_size: int, label=None) \
        -> Iterator[tuple[list[PandoraGate], int]]:
    """
    This method traverses a cirq circuit in windows of arbitrary size and returns the PandoraGate operations equivalent
    to the cirq operations in the window. Especially useful for very large circuits which do not fit into memory. The
    list of qubits in the resulting circuit will be a permutation of the original one.
    Args:
        circuit: the high-level cirq circuit
        window_size: the size of each decomposition window
    Returns:
        Generator over the PandoraGate objects of each batch.
    """
    if window_size <= 1:
        raise WindowSizeError

    # We assume that the IDs of the Pandora gates are starting from zero
    # and we increment these IDs for each gate enocuntered in the Cirq circuit
    curr_gate_id = 0

    # Having the ID, we create a PandoraGate and store in a dictionary where the ID is the key
    id2gate = dict()

    # The list of circuit qubits is dynamically updated
    # because we are starting from a high-level circuit and decomposing it into Clifford+T
    # and teleported gates etc, so ancilla qubits might appear
    # circuit_qubits = set()
    # Each qubit has the latest Pandora Link associated
    qubit2link = dict()

    # Cirq measurements have a string key attached
    # Here we translate those strings to unique int keys for storage into the tables
    meas2intkey = dict()

    """
        The Clifford+T gates are obtained here by using a decomposing generator.
    """
    op_list_batches = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=circuit, window_size=window_size)

    for (op_list, cliff_decomp_time) in op_list_batches:

        start_cirq_to_pandora = time.time()

        """
            The In gates are added, if needed
        """
        for cirq_op in op_list:

            # Check that the qubits of this operation have been initialized
            # This qubit has not been initialized, so it needs an In gate
            for qub in cirq_op.qubits:
                if qub not in qubit2link.keys():
                    # New gates, potentially new qubits -> update the set of qubits
                    id2gate[curr_gate_id] = PandoraGate(gate_id=curr_gate_id,
                                                        gate_type=PandoraGateTranslator.In.value,
                                                        label=label)

                    # This is used only for tests -- not stored in the DB, for the moment
                    id2gate[curr_gate_id].qubit_name = str(qub)

                    qubit2link[qub] = get_link_id(curr_gate_id, 0, PandoraGateTranslator.In.value)
                    curr_gate_id += 1

        """
            The gates are converted
        """
        for cirq_op in op_list:
            curr_gate_id = cirq_op_to_pandora_gate(cirq_op, label, curr_gate_id, qubit2link, meas2intkey, id2gate)

        """
            In order to ensure that the buffers are inter-connected, one needs to 
            insert into Pandora only the gates for which the connections 
            into the future are known.
            
            Gates without a link into the future are not insert/added into the batch,
            and are kept for the next batch.
        """
        # TODO: This might have to be improved for performance
        dictionary_copy = id2gate.copy()
        batch_elements: list[PandoraGate] = []
        for pandora_gate in dictionary_copy.values():
            if (pandora_gate.type in SINGLE_QUBIT_GATES
                and pandora_gate.next_q1 is not None) \
                    or (pandora_gate.type in TWO_QUBIT_GATES
                        and pandora_gate.next_q1 is not None
                        and pandora_gate.next_q2 is not None):
                batch_elements.append(pandora_gate)
                id2gate.pop(pandora_gate.id)

        if len(batch_elements) > 0:
            yield batch_elements, curr_gate_id# time.time() - start_cirq_to_pandora + cliff_decomp_time

    """
        Finally, add the Out gates
    """
    start_final = time.time()
    final_op_list: list[cirq.Operation] = [Out().on(q) for q in qubit2link.keys()]

    # dictionary of keys -- is this used somehow?
    for cirq_op in final_op_list:
        curr_gate_id = cirq_op_to_pandora_gate(cirq_op, label, curr_gate_id, qubit2link, meas2intkey, id2gate)

    ml = list(id2gate.values())
    if len(ml) > 0:
        yield ml, curr_gate_id#time.time() - start_final

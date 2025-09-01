import cirq
import qiskit

from pandora.exceptions import PandoraGateOrderingError, PandoraWrappedGateMissingLinks
from pandora.gate_translator import SINGLE_QUBIT_GATES, TWO_QUBIT_GATES, THREE_QUBIT_GATES, PandoraGateTranslator
from pandora.gates import PandoraGateWrapper, PandoraGate


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


def sort_pandora_wrapped_by_moment(pandora_gate_id_map: dict[int, PandoraGateWrapper],
                                   original_qubits_test: dict[str, int] = None,
                                   is_test=False):
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
            nr_qubits = -1
            if current_gate_code in SINGLE_QUBIT_GATES:
                nr_qubits = 1
            elif current_gate_code in TWO_QUBIT_GATES:
                nr_qubits = 2
            elif current_gate_code in THREE_QUBIT_GATES:
                nr_qubits = 3

            assert(nr_qubits != -1)

            for i in range(nr_qubits):
                if current_wrapped_gate.prev_id[i] not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError

                # if current_wrapped_gate.prev_id[1] not in pandora_gate_id_map.keys():
                #     raise PandoraGateOrderingError

            prev_wrapped_gate_qs = [pandora_gate_id_map[current_wrapped_gate.prev_id[i]].moment for i in range(nr_qubits)]

            # prev_wrapped_gate_q1 = pandora_gate_id_map[current_wrapped_gate.prev_id[0]]
            # prev_wrapped_gate_q2 = pandora_gate_id_map[current_wrapped_gate.prev_id[1]]

            # prev_q1_id = prev_wrapped_gate_q1.pandora_gate.id
            # prev_q2_id = prev_wrapped_gate_q2.pandora_gate.id

            # if prev_q1_id == prev_q2_id:
            #     if default_moment != prev_wrapped_gate_q1.moment:
            #         current_wrapped_gate.moment = prev_wrapped_gate_q1.moment + 1
            #     else:
            #         all_are_marked = False
            #
            # # two qubit gate following some other gates
            # # if prev_q1_id != prev_q2_id:
            # else:
            if default_moment not in prev_wrapped_gate_qs:#[prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment]:
                current_wrapped_gate.moment = max(prev_wrapped_gate_qs) + 1
                # current_wrapped_gate.moment = max(prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment) + 1
            else:
                all_are_marked = False

    assert all([wrapped.moment != default_moment for wrapped in pandora_gate_id_map.values()])
    if is_test:
        return sorted(pandora_gate_id_map.values(), key=lambda wrapped: (wrapped.moment,
                                                                         original_qubits_test[
                                                                             wrapped.pandora_gate.qubit_name]
                                                                         if wrapped.pandora_gate.type
                                                                            == PandoraGateTranslator.In.value
                                                                         else wrapped.pandora_gate.id))
    return sorted(pandora_gate_id_map.values(), key=lambda wrapped: (wrapped.moment,
                                                                     wrapped.pandora_gate.id))


def pandora_wrapped_to_qiskit_circuit(wrapped_gates: list[PandoraGateWrapper],
                                      n_qubits: int) -> qiskit.QuantumCircuit:
    """
    Take a list of PandoraGateWrapper objects and return the corresponding qiskit QuantumCircuit.
    """
    circuit = qiskit.QuantumCircuit(n_qubits)
    q = list(range(n_qubits))

    for wrapped in wrapped_gates:
        if wrapped.prev_id[0] is None and wrapped.next_id[0] is None:
            raise PandoraWrappedGateMissingLinks
        qiskit_gate = wrapped.to_qiskit_gate()
        qiskit_qubits = wrapped.get_gate_qubits_from_list(q)
        circuit.append(qiskit_gate, qiskit_qubits)

    return circuit


def pandora_wrapped_to_cirq_circuit(wrapped_gates: list[PandoraGateWrapper],
                                    n_qubits: int) -> cirq.Circuit:
    """
    Take a list of PandoraGateWrapper objects and return the corresponding cirq Circuit.
    """
    circuit = cirq.Circuit()
    q = [cirq.NamedQubit(str(j)) for j in range(n_qubits)]

    for wrapped in wrapped_gates:
        if wrapped.prev_id[0] is None and wrapped.next_id[0] is None:
            raise PandoraWrappedGateMissingLinks

        cirq_op = wrapped.to_cirq_operation()
        cirq_qubits = wrapped.get_gate_qubits_from_list(q)
        circuit.append(cirq_op.on(*cirq_qubits))

    return circuit


def pandora_to_circuit(pandora_gates: list[PandoraGate],
                       circuit_type: ['cirq', 'qiskit'] = 'cirq',
                       original_qubits_test: dict[str, int] = None,
                       is_test=False) \
        -> cirq.Circuit | qiskit.QuantumCircuit:
    """
    Takes a list of Pandora gates (unwrapped) and returns the corresponding cirq Circuit or qiskit QuantumCircuit.
    """
    pandora_gate_id_map = wrap_pandora_gates(pandora_gates=pandora_gates)

    for gate in pandora_gates:
        print(
            f"id={gate.id:2d} | "
            f"prev_q1={str(gate.prev_q1):>4} | prev_q2={str(gate.prev_q2):>4} | prev_q3={str(gate.prev_q3):>4} | "
            f"type={gate.type:>4} | "
            f"next_q1={str(gate.next_q1):>4} | next_q2={str(gate.next_q2):>4} | next_q3={str(gate.next_q3):>4}"
    )

    # TODO - Make it work for three qubit gates
    sorted_gates = sort_pandora_wrapped_by_moment(pandora_gate_id_map, original_qubits_test, is_test)
    sorted_ids = [wrapped.pandora_gate.id for wrapped in sorted_gates]

    rh = dict(zip(sorted_ids, sorted_gates))

    nr_circuit_qubits = 0
    for wrapped in rh.values():
        if wrapped.pandora_gate.type == PandoraGateTranslator.In.value:
            wrapped.q[0] = nr_circuit_qubits
            nr_circuit_qubits += 1

    for wrapped in rh.values():

        wrapped_id = wrapped.pandora_gate.id
        nr_qubits = 0

        # find q1 for single qubit gate
        if wrapped.pandora_gate.type in SINGLE_QUBIT_GATES and wrapped.pandora_gate.type != PandoraGateTranslator.In.value:
            nr_qubits = 1
        elif wrapped.pandora_gate.type in TWO_QUBIT_GATES:
            nr_qubits = 2
        elif wrapped.pandora_gate.type in THREE_QUBIT_GATES:
            nr_qubits = 3

        for port_i in range(nr_qubits):
            prev_wrapped_gate = rh[wrapped.prev_id[port_i]]
            # each gate has three ports. check all three
            for i in range(3):
                if prev_wrapped_gate.next_id[i] == wrapped_id:
                    # TODO: aici nu functioneaza la 3 porturi pentru ca nu leaga bine control la target
                    wrapped.q[port_i] = prev_wrapped_gate.q[i]

    for wrapped in rh.values():
        print(wrapped)

    wrapped_gates = list(rh.values())
    if circuit_type == 'cirq':
        circuit = pandora_wrapped_to_cirq_circuit(wrapped_gates=wrapped_gates, n_qubits=nr_circuit_qubits)
    else:
        circuit = pandora_wrapped_to_qiskit_circuit(wrapped_gates=wrapped_gates, n_qubits=nr_circuit_qubits)

    return circuit

import numpy as np
import qiskit
import cirq

from pandora.exceptions import *
from pandora.exceptions import PandoraGateOrderingError, PandoraWrappedGateMissingLinks
from pandora.gate_translator import PandoraGateTranslator, PANDORA_TO_CIRQ, CAN_HAVE_KEY, REQUIRES_EXPONENT, \
    REQUIRES_ROTATION, SINGLE_QUBIT_GATES, TWO_QUBIT_GATES, THREE_QUBIT_GATES, PANDORA_TO_QISKIT, IS_IO

"""
    LinkID has the following format *IPTT where:
    - unlimited number of digits for the gateid I
    - one digit for the port P. For example, a CNOT gate has 2 ports, a Toffoli has 3 ports etc.
    - two digits for the gate type T. For example, a Toffoli is 23, a CNOT is 15/18 etc.

    Considering the LinkID X, in order to:
    - get the gateid: X / 1000 will return the *I digits
    - get the port number: (X / 100) % 10 will return the P digit
    - get the type: X % 100 will return the T digits
"""

def get_link_id(gate_id, gate_port, gate_type):
    return gate_id * 1000 + gate_port * 100 + gate_type


def get_gate_id(link_id):
    return link_id // 1000


def get_gate_port(link_id):
    return (link_id // 100) % 10


def get_gate_type(link_id):
    return link_id % 100


class PandoraGate:
    def __init__(self,
                 gate_id: int = None,
                 prev_q1: int = None,
                 prev_q2: int = None,
                 prev_q3: int = None,
                 gate_code: int = None,
                 gate_parameter: float = 0,
                 global_shift: float = 0,
                 switch: bool = False,
                 next_q1: int = None,
                 next_q2: int = None,
                 next_q3: int = None,
                 # visited: bool = False,
                 visited: int = -1,
                 label: str = None,
                 is_classically_controlled: bool = False,
                 measurement_key: int = None,
                 qubit_name: str = None):
        # self.auto_id = None
        self.id = gate_id

        self.prev_q1 = prev_q1 #self.remove_type_from_link(prev_q1)
        self.prev_q2 = prev_q2 #self.remove_type_from_link(prev_q2)
        self.prev_q3 = prev_q3 #self.remove_type_from_link(prev_q3)

        self.next_q1 = next_q1 #self.remove_type_from_link(next_q1)
        self.next_q2 = next_q2 #self.remove_type_from_link(next_q2)
        self.next_q3 = next_q3 #self.remove_type_from_link(next_q3)

        """
            Information used to annotate the Pandora gates
        """
        self.moment = None
        self.q1 = None
        self.q2 = None
        self.q3 = None

        # pre-compute the ids of previous gates
        self.prev_id1 = get_gate_id(self.prev_q1) if self.prev_q1 is not None else None
        self.prev_id2 = get_gate_id(self.prev_q2) if self.prev_q2 is not None else None
        self.prev_id3 = get_gate_id(self.prev_q3) if self.prev_q3 is not None else None
        # pre-compute the ids of next gates
        self.next_id1 = get_gate_id(self.next_q1) if self.next_q1 is not None else None
        self.next_id2 = get_gate_id(self.next_q2) if self.next_q2 is not None else None
        self.next_id3 = get_gate_id(self.next_q3) if self.next_q3 is not None else None

        self.type = gate_code
        self.param = gate_parameter
        self.global_shift = global_shift
        self.switch = switch

        self.visited = visited
        self.label = label
        self.cl_ctrl = is_classically_controlled
        self.meas_key = measurement_key
        self.qubit_name = qubit_name

    def __str__(self):
        return f'1: {self.prev_q1}<---------->{self.next_q1}\n' \
               f'2: {self.prev_q2}<--t-{self.type}(id-{self.id})-->{self.next_q2}\n' \
               f'3: {self.prev_q3}<---------->{self.next_q3}'

    # @staticmethod
    # def remove_type_from_link(link):
    #     # if link is not none and next type is not In/Out
    #     if link is not None and link > 100:
    #         return link // 100
    #     return link
    #
    # get_gate_type()

    def get_insert_query(self, table_name):
        columns = self.__dict__.keys()
        n_columns = len(columns)
        ls = ['%s,' for _ in range(n_columns)]
        mogrify_arg = '(' + " ".join(ls) + ')'

        psql_insert = f"INSERT INTO {table_name}{tuple(columns)}"
        return mogrify_arg, psql_insert

    def to_tuple(self, is_test=False):
        if not is_test:
            return (self.id,
                    self.prev_q1,
                    self.prev_q2,
                    self.prev_q3,
                    self.type,
                    self.param,
                    self.global_shift,
                    self.switch,
                    self.next_q1,
                    self.next_q2,
                    self.next_q3,
                    self.visited,
                    self.label,
                    self.cl_ctrl,
                    self.meas_key)
        return (self.id,
                self.prev_q1,
                self.prev_q2,
                self.prev_q3,
                self.type,
                self.param,
                self.global_shift,
                self.switch,
                self.next_q1,
                self.next_q2,
                self.next_q3,
                self.visited,
                self.label,
                self.cl_ctrl,
                self.meas_key,
                self.qubit_name)

    def get_gate_qubits_from_list(self, qubit_list) -> list:
        """
        Given a list of arbitrary cirq qubits, return the values of the qubits in that list which correspond to
        indices q1, q2, q3.
        """

        print(self)
        print("qubit1: ", self.q1)
        print("")

        if self.type in SINGLE_QUBIT_GATES:
            if self.q1 is None:
                raise PandoraGateWrappedMissingQubits
            return [qubit_list[self.q1]]
        if self.type in TWO_QUBIT_GATES:
            if self.q1 is None or self.q2 is None:
                raise PandoraGateWrappedMissingQubits
            return [qubit_list[self.q1], qubit_list[self.q2]]
        if self.type in THREE_QUBIT_GATES:
            if self.q1 is None or self.q2 is None or self.q3 is None:
                raise PandoraGateWrappedMissingQubits
            return [qubit_list[self.q1], qubit_list[self.q2], qubit_list[self.q3]]

    def to_cirq_operation(self) -> cirq.GateOperation:
        """
        Convert the pandora wrapped gate to a qiskit CircuitOperation object without assigned qubits.
        """
        cirq_op = PANDORA_TO_CIRQ[self.type]

        if self.type in REQUIRES_ROTATION:
            cirq_op = cirq_op(rads=self.param * np.pi)

        if self.type in REQUIRES_EXPONENT:
            cirq_op = cirq_op(exponent=self.param,
                              global_shift=self.global_shift)

        if self.type in CAN_HAVE_KEY and self.meas_key is not None:
            if self.type == PandoraGateTranslator.M.value:
                # Measurement gate has no setter for key --> could use .with_key(key)
                cirq_op = cirq.MeasurementGate(num_qubits=1, key=str(self.meas_key))
            else:
                cirq_op.key = self.meas_key

        return cirq_op

    def to_qiskit_gate(self) -> qiskit.circuit.Gate:
        """
        Convert the pandora wrapped gate to a qiskit Gate object without assigned qubits.
        """
        gate_type = self.type

        qiskit_gate_class = PANDORA_TO_QISKIT[gate_type]

        if gate_type in REQUIRES_ROTATION:
            return qiskit_gate_class(phi=self.param)

        if gate_type in IS_IO:
            return qiskit_gate_class
        return qiskit_gate_class()

def sort_pandora_by_moment(pandora_gate_id_map: dict[int, PandoraGate],
                           original_qubits_test: dict[str, int] = None,
                           is_test=False):
    """
    TODO: Maybe this should be performed in SQL. Directly in the tables.

    This method receives a dictionary of (id, PandoraGateWrapped) and returns a list of PandoraGateWrapped objects
    sorted by the moment each pandora gate would appear in the reconstructed cirq Circuit.

    Note that this only works for gates acting on at most two qubits.
    """
    default_moment = -1
    all_are_marked = False

    while all_are_marked is False:
        all_are_marked = True
        for current_gate in pandora_gate_id_map.values():
            # gate already has an assigned moment
            if current_gate.moment != default_moment:
                continue

            current_gate_code = current_gate.type

            # single qubit case
            if current_gate_code in SINGLE_QUBIT_GATES:
                if current_gate.prev_id1 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError
                prev_wrapped_gate = pandora_gate_id_map[current_gate.prev_id1]
                if prev_wrapped_gate.moment != default_moment:
                    current_gate.moment = prev_wrapped_gate.moment + 1
                else:
                    all_are_marked = False

            # two qubit case
            if current_gate_code in TWO_QUBIT_GATES:
                # two qubit gate following two qubit gate
                if current_gate.prev_id1 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError

                if current_gate.prev_id2 not in pandora_gate_id_map.keys():
                    raise PandoraGateOrderingError

                prev_wrapped_gate_q1 = pandora_gate_id_map[current_gate.prev_id1]
                prev_wrapped_gate_q2 = pandora_gate_id_map[current_gate.prev_id2]
                prev_q1_id = prev_wrapped_gate_q1.id
                prev_q2_id = prev_wrapped_gate_q2.id

                if prev_q1_id == prev_q2_id:
                    if prev_wrapped_gate_q1.moment != default_moment:
                        current_gate.moment = prev_wrapped_gate_q1.moment + 1
                    else:
                        all_are_marked = False

                # two qubit gate following some other gates
                if prev_q1_id != prev_q2_id:
                    if default_moment not in [prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment]:
                        current_gate.moment = max(prev_wrapped_gate_q1.moment, prev_wrapped_gate_q2.moment) + 1
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


def pandora_to_qiskit_circuit(wrapped_gates: list[PandoraGate],
                              n_qubits: int) -> qiskit.QuantumCircuit:
    """
    Take a list of PandoraGateWrapper objects and return the corresponding qiskit QuantumCircuit.
    """
    circuit = qiskit.QuantumCircuit(n_qubits)
    q = list(range(n_qubits))

    for wrapped in wrapped_gates:
        if wrapped.prev_id1 is None and wrapped.next_id1 is None:
            raise PandoraWrappedGateMissingLinks
        qiskit_gate = wrapped.to_qiskit_gate()
        qiskit_qubits = wrapped.get_gate_qubits_from_list(q)
        circuit.append(qiskit_gate, qiskit_qubits)

    return circuit


def pandora_to_cirq_circuit(gates: list[PandoraGate],
                            n_qubits: int) -> cirq.Circuit:
    """
    Take a list of PandoraGateWrapper objects and return the corresponding cirq Circuit.
    """
    circuit = cirq.Circuit()
    q = [cirq.NamedQubit(str(j)) for j in range(n_qubits)]

    for pandora_gate in gates:
        if pandora_gate.prev_id1 is None and pandora_gate.next_id1 is None:
            raise PandoraWrappedGateMissingLinks

        cirq_op = pandora_gate.to_cirq_operation()
        cirq_qubits = pandora_gate.get_gate_qubits_from_list(q)
        circuit.append(cirq_op.on(*cirq_qubits))
                       #.with_tags(str(wrapped.pandora_gate.id)))

    return circuit


def annotate_pandora_gates(pandora_gates: list[PandoraGate],
                           original_qubits_test: dict[str, int] = None,
                           is_test=False):
    """
        Takes a list of Pandora gates (unwrapped) and returns a list of gates which include moment and qubit information
    """

    # Wrap the Pandora gates
    pandora_gate_id_map = {}
    for gate in pandora_gates:
        # wrapped = PandoraGateWrapper(pandora_gate=gate)
        if gate.type == PandoraGateTranslator.In.value:
            gate.moment = 0
        pandora_gate_id_map[gate.id] = gate

    sorted_gates = sort_pandora_by_moment(pandora_gate_id_map, original_qubits_test, is_test)
    sorted_ids = [gate.id for gate in sorted_gates]

    rh = dict(zip(sorted_ids, sorted_gates))

    """
        - Set q1 to the inputs
        - Count the number of qubits this circuit is operating on
    """
    n_qubits = 0
    for gate in rh.values():
        if gate.type == PandoraGateTranslator.In.value:
            gate.q1 = n_qubits
            n_qubits += 1

    for gate in rh.values():
        gate_id = gate.id

        # find q1 for single qubit gate
        if gate.type in SINGLE_QUBIT_GATES:
            if gate.type != PandoraGateTranslator.In.value:
                prev_wrapped_gate = rh[gate.prev_id1]
                if prev_wrapped_gate.next_id1 == gate_id:
                    gate.q1 = prev_wrapped_gate.q1
                elif prev_wrapped_gate.next_id2 == gate_id:
                    gate.q1 = prev_wrapped_gate.q2

        # find q1, q2 for two qubit gate
        if gate.type in TWO_QUBIT_GATES:
            # previous gate is two qubit gate on same q1 q2
            if gate.prev_id1 == gate.prev_id2:
                previous_wrapped_gate = rh[gate.prev_id1]
                if previous_wrapped_gate.switch == gate.switch:
                    gate.q1, gate.q2 = previous_wrapped_gate.q1, previous_wrapped_gate.q2
                else:
                    gate.q1, gate.q2 = previous_wrapped_gate.q2, previous_wrapped_gate.q1
            else:
                # previous gates are different for q1 q2
                previous_wrapped_q1 = rh[gate.prev_id1]
                previous_wrapped_q2 = rh[gate.prev_id2]

                if previous_wrapped_q1.next_id1 == gate_id:
                    gate.q1 = previous_wrapped_q1.q1
                elif previous_wrapped_q1.next_id2 == gate_id:
                    gate.q1 = previous_wrapped_q1.q2

                if previous_wrapped_q2.next_id1 == gate_id:
                    gate.q2 = previous_wrapped_q2.q1
                elif previous_wrapped_q2.next_id2 == gate_id:
                    gate.q2 = previous_wrapped_q2.q2

    return list(rh.values()), n_qubits

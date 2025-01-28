import numpy as np

from pandora.exceptions import *
from pandora.gate_translator import PandoraGateTranslator, PANDORA_TO_CIRQ, CAN_HAVE_KEY, REQUIRES_EXPONENT, \
    REQUIRES_ROTATION, SINGLE_QUBIT_GATES, TWO_QUBIT_GATES, THREE_QUBIT_GATES
import cirq


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
                 visited: bool = False,
                 label: str = None,
                 is_classically_controlled: bool = False,
                 measurement_key: int = None,
                 qubit_name: str = None):
        self.id = gate_id
        self.prev_q1 = prev_q1
        self.prev_q2 = prev_q2
        self.prev_q3 = prev_q3
        self.type = gate_code
        self.param = gate_parameter
        self.global_shift = global_shift
        self.switch = switch
        self.next_q1 = next_q1
        self.next_q2 = next_q2
        self.next_q3 = next_q3
        self.visited = visited
        self.label = label
        self.cl_ctrl = is_classically_controlled
        self.meas_key = measurement_key
        self.qubit_name = qubit_name

    def __str__(self):
        return f'{self.prev_q1}<---------->{self.next_q1}\n' \
               f'{self.prev_q2}<--{self.type}({self.id})-->{self.next_q2}\n' \
               f'{self.prev_q3}<---------->{self.next_q3}\n'

    def get_insert_query(self, table_name):
        columns = self.__dict__.keys()
        n_columns = len(columns)
        ls = ['%s,' for _ in range(n_columns)]
        mogrify_arg = '(' + " ".join(ls) + ')'

        psql_insert = f"INSERT INTO {table_name}{tuple(columns)}"
        return mogrify_arg, psql_insert

    def to_tuple(self, is_test=False):
        if is_test:
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
                self.meas_key
                )


class PandoraGateWrapper:
    def __init__(self,
                 pandora_gate: PandoraGate,
                 q1: int = None,
                 q2: int = None,
                 q3: int = None,
                 moment: int = -1):

        self.pandora_gate = pandora_gate
        self.moment = moment
        self.q1 = q1
        self.q2 = q2
        self.q3 = q3
        # pre-compute the ids of previous gates
        self.prev_id1 = self.get_neighbour_gate_id(pandora_gate.prev_q1)
        self.prev_id2 = self.get_neighbour_gate_id(pandora_gate.prev_q2)
        self.prev_id3 = self.get_neighbour_gate_id(pandora_gate.prev_q3)
        # pre-compute the ids of next gates
        self.next_id1 = self.get_neighbour_gate_id(pandora_gate.next_q1)
        self.next_id2 = self.get_neighbour_gate_id(pandora_gate.next_q2)
        self.next_id3 = self.get_neighbour_gate_id(pandora_gate.next_q3)

    def __str__(self):
        return f'{self.pandora_gate.type}({self.q1}, {self.q2}, {self.q3})'

    @staticmethod
    def get_neighbour_gate_id(connection_value) -> [None, int]:
        """
        Returns the id of the neighbour gate on a link with value = connection_value.
        """
        if connection_value is None:
            return connection_value
        return connection_value // 10

    def get_gate_qubits_from_list(self, cirq_qubit_list) -> list:
        """
        Given a list of arbitrary cirq qubits, return the values of the qubits in that list which correspond to
        indices q1, q2, q3.
        """
        if self.pandora_gate.type in SINGLE_QUBIT_GATES:
            if self.q1 is None:
                raise PandoraGateWrappedMissingQubits
            return [cirq_qubit_list[self.q1]]
        if self.pandora_gate.type in TWO_QUBIT_GATES:
            if self.q1 is None or self.q2 is None:
                raise PandoraGateWrappedMissingQubits
            return [cirq_qubit_list[self.q1], cirq_qubit_list[self.q2]]
        if self.pandora_gate.type in THREE_QUBIT_GATES:
            if self.q1 is None or self.q2 is None or self.q3 is None:
                raise PandoraGateWrappedMissingQubits
            return [cirq_qubit_list[self.q1], cirq_qubit_list[self.q2], cirq_qubit_list[self.q3]]

    def to_cirq_operation(self) -> cirq.GateOperation:
        """
        Convert the pandora wrapped gate to a cirq GateOperation object without assigned qubits.
        """
        cirq_op = PANDORA_TO_CIRQ[self.pandora_gate.type]

        if self.pandora_gate.type in REQUIRES_ROTATION:
            cirq_op = cirq_op(rads=self.pandora_gate.param * np.pi)

        if self.pandora_gate.type in REQUIRES_EXPONENT:
            cirq_op = cirq_op(exponent=self.pandora_gate.param,
                              global_shift=self.pandora_gate.global_shift)

        if self.pandora_gate.type in CAN_HAVE_KEY and self.pandora_gate.meas_key is not None:
            if self.pandora_gate.type == PandoraGateTranslator.M.value:
                # Measurement gate has no setter for key --> could use .with_key(key)
                cirq_op = cirq.MeasurementGate(num_qubits=1, key=str(self.pandora_gate.meas_key))
            else:
                cirq_op.key = self.pandora_gate.meas_key

        return cirq_op

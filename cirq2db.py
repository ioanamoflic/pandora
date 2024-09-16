import sys
from abc import ABC
from typing import List, Optional

import numpy as np
import cirq
from qualtran.bloqs.mcmt import And


class In(cirq.Gate):
    def __init__(self, is_classic=False, init_val=None):
        super(In, self)
        if init_val is None:
            self.gate = 'In'
        else:
            self.gate = init_val
        self.is_classic = is_classic

    def _num_qubits_(self):
        return 1

    def _unitary_(self):
        return np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ])

    def _circuit_diagram_info_(self, args):
        return self.gate

    def __str__(self):
        return self.gate


class Out(cirq.Gate):
    def __init__(self, is_classic=False, init_val=None):
        super(Out, self)
        self.is_classic = is_classic
        if init_val is None:
            self.gate = 'Out'
        else:
            self.gate = init_val

    def _num_qubits_(self):
        return 1

    def _unitary_(self):
        return np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ])

    def _circuit_diagram_info_(self, args):
        return self.gate

    def __str__(self):
        return self.gate


SINGLE_QUBIT_GATES = {
    'Rx': cirq.ops.common_gates.Rx,
    'Ry': cirq.ops.common_gates.Ry,
    'Rz': cirq.ops.common_gates.Rz,
    'XPowGate': cirq.XPowGate,
    'ZPowGate': cirq.ZPowGate,
    'YPowGate': cirq.YPowGate,
    'HPowGate': cirq.HPowGate,
    '_PauliX': cirq.X,
    '_PauliZ': cirq.Z,
    '_PauliY': cirq.Y,
    'GlobalPhaseGate': cirq.GlobalPhaseGate,
    'ResetChannel': cirq.ResetChannel(),
    'In': In(),
    'Out': Out(),
    'Inc': In(is_classic=True),
    'Outc': Out(is_classic=True),
    'M': cirq.MeasurementGate(1),
}

TWO_QUBIT_GATES = {'CNOT': cirq.CX,
                   'CZ': cirq.CZ,
                   'CZPowGate': cirq.CZPowGate,
                   'CXPowGate': cirq.CXPowGate,
                   'XXPowGate': cirq.XXPowGate,
                   'ZZPowGate': cirq.ZZPowGate}

THREE_QUBIT_GATES = {'TOFFOLI': cirq.CCX,
                     'AND': And,
                     'TOFFOLI**-1': cirq.CCX,
                     'AND**-1': And}

ALL_GATES = {**SINGLE_QUBIT_GATES, **TWO_QUBIT_GATES, **THREE_QUBIT_GATES}

for gate in ['HPowGate', 'XPowGate', 'ZPowGate', 'YPowGate']:
    for param in [0.25, -0.25, 0.5, -0.5, -1.0]:
        SINGLE_QUBIT_GATES[f'{gate}**{param}'] = eval(f'cirq.{gate}')(exponent=param)

for gate in ['CXPowGate', 'CZPowGate', 'XXPowGate', 'ZZPowGate']:
    for param in [0.25, -0.25, 0.5, -0.5, -1.0]:
        TWO_QUBIT_GATES[f'{gate}**{param}'] = eval(f'cirq.{gate}')(exponent=param)

for param in [0.25, -0.25, 0.5, -0.5, -1.0]:
    THREE_QUBIT_GATES[f'CCXPowGate**{param}'] = cirq.CCXPowGate(exponent=param)

N_DB_COLUMNS = 17
MAX_QUBITS_PER_GATE = 3
DB_COLUMNS = ['prev_q1', 'prev_q2', 'prev_q3', 'type', 'param', 'switch', 'next_q1', 'next_q2', 'next_q3',
              'visited', 'label', 'cl_ctrl', 'meas_key', 'qub_1', 'qub_2', 'qub_3']


def get_cirq_gate_attr(operation: cirq.Operation):
    is_classically_controlled = len(operation.classical_controls) > 0
    gate = operation.without_classical_controls().gate
    switch = operation.qubits[0] < operation.qubits[1] if len(operation.qubits) == 2 else False

    gate_name, measurement_key = (gate.__class__.__name__, None) \
        if not isinstance(gate, cirq.MeasurementGate) else ('M', gate.key)

    parameter = 0
    if isinstance(gate, (cirq.ops.common_gates.Rz, cirq.ops.common_gates.Ry, cirq.ops.common_gates.Rx)):
        parameter = gate._rads
    if isinstance(gate, (cirq.HPowGate, cirq.XPowGate, cirq.YPowGate, cirq.ZPowGate,
                         cirq.CXPowGate, cirq.CZPowGate, cirq.CCXPowGate)):
        parameter = gate.exponent
        if parameter in [0.25, -0.25, 0.5, -0.5, -1.0]:
            gate_name = gate_name + f'**{parameter}'

    return gate_name, parameter, switch, is_classically_controlled, measurement_key


def order_db_tuples(db_tuples):
    db_tuples = [tup + (0,) if tup[4] == 'In' else tup for tup in db_tuples]
    all_are_marked = False

    while all_are_marked is False:
        all_are_marked = True
        for current_tup in db_tuples:
            if len(current_tup) == N_DB_COLUMNS + 1:
                continue
            # single qubit case
            if current_tup[4] in SINGLE_QUBIT_GATES.keys():
                # this should just return one tuple or none if there is a bug
                prev_tup = [tup for tup in db_tuples if tup[0] == current_tup[1] // 10]
                if len(prev_tup[0]) == N_DB_COLUMNS + 1:
                    db_tuples = [tup + (prev_tup[0][N_DB_COLUMNS] + 1,) if tup == current_tup else tup for tup in
                                 db_tuples]
                else:
                    all_are_marked = False
            # two qubit case
            else:
                # this should return two tuples
                prev_tup_q1 = [tup for tup in db_tuples if tup[0] == current_tup[1] // 10]
                prev_tup_q2 = [tup for tup in db_tuples if tup[0] == current_tup[2] // 10]
                # two qubit gate following two qubit gate
                if prev_tup_q1 == prev_tup_q2:
                    if len(prev_tup_q1[0]) == N_DB_COLUMNS + 1:
                        db_tuples = [tup + (prev_tup_q1[0][N_DB_COLUMNS] + 1,) if tup == current_tup else tup for tup in
                                     db_tuples]
                    else:
                        all_are_marked = False
                # two qubit gate following two single qubit gates
                elif len(prev_tup_q1[0]) == N_DB_COLUMNS + 1 and len(prev_tup_q2[0]) == N_DB_COLUMNS + 1:
                    db_tuples = [tup + (
                        max(prev_tup_q1[0][N_DB_COLUMNS],
                            prev_tup_q2[0][N_DB_COLUMNS]) + 1,) if tup == current_tup else tup
                                 for tup in db_tuples]
                else:
                    all_are_marked = False

    assert all([len(tup) == N_DB_COLUMNS + 1 for tup in db_tuples])
    return db_tuples


def db_to_cirq(db_tuples, with_tags=False):
    db_tuples = order_db_tuples(db_tuples=db_tuples)
    # sort by moment to ensure correctness
    db_tuples = sorted(db_tuples, key=lambda tup: (tup[N_DB_COLUMNS], tup[0]))
    rh = {}
    n_qubits = 0
    for gate in db_tuples:
        gate_id = gate[0]
        if gate[4] == 'In':
            rh[gate_id] = {
                "id": gate_id,
                "prev_q1": 0,
                "prev_q2": None,
                "prev_q3": None,
                "type": gate[4],
                "param": gate[5],
                "switch": gate[6],
                "next_q1": gate[7],
                "next_q2": gate[8],
                "next_q3": gate[9],
                "visited": gate[10],
                "label": gate[11],
                "cl_ctrl": gate[12],
                "meas_key": gate[13],
                "qub_1": gate[14],
                "qub_2": gate[15],
                "qub_3": gate[16]

            }
            rh[gate_id]['q1'] = n_qubits
            rh[gate_id]['q2'], rh[gate_id]['q3'] = None, None
            n_qubits = n_qubits + 1
        else:
            rh[gate_id] = {
                "id": gate_id,
                "prev_q1": gate[1],
                "prev_q2": gate[2],
                "prev_q3": gate[3],
                "type": gate[4],
                "param": gate[5],
                "switch": gate[6],
                "next_q1": gate[7] if gate[7] is not None else 0,
                "next_q2": gate[8] if gate[8] is not None else 0,
                "next_q3": gate[9] if gate[9] is not None else 0,
                "visited": gate[10],
                "label": gate[11],
                "cl_ctrl": gate[12],
                "meas_key": gate[13],
                "qub_1": gate[14],
                "qub_2": gate[15],
                "qub_3": gate[16],
            }

    for g in db_tuples:
        gate_id = g[0]
        # single qubit case
        if rh[gate_id]['type'] in SINGLE_QUBIT_GATES.keys():
            # 1.1 single qubit gate followed by another single qubit gate or
            # 1.2 two-qubit gate where control qubit is followed by single qubit gate
            if rh[gate_id]['type'] != 'In':
                previous_gate_id = rh[gate_id]['prev_q1'] // 10
                if rh[previous_gate_id]['next_q1'] // 10 == gate_id:
                    rh[gate_id]['q1'] = rh[previous_gate_id]['q1']
                # 2.1 two-qubit gate where target qubit is followed by single qubit gate
                elif rh[previous_gate_id]['next_q2'] // 10 == gate_id:
                    rh[gate_id]['q1'] = rh[previous_gate_id]['q2']
            rh[gate_id]['q2'], rh[gate_id]['q3'] = None, None
        # two-qubit case
        elif rh[gate_id]['type'] in TWO_QUBIT_GATES.keys():
            previous_gate_id_ctrl = rh[gate_id]['prev_q1'] // 10
            previous_gate_id_tgt = rh[gate_id]['prev_q2'] // 10
            if previous_gate_id_ctrl is None:
                rh[gate_id]['q1'] = n_qubits
                n_qubits = n_qubits + 1
            if previous_gate_id_tgt is None:
                rh[gate_id]['q2'] = n_qubits
                n_qubits = n_qubits + 1
            # two qubit gate following two qubit gate
            if previous_gate_id_ctrl == previous_gate_id_tgt:
                if rh[gate_id]['switch'] == rh[previous_gate_id_ctrl]['switch']:
                    rh[gate_id]['q1'] = rh[previous_gate_id_ctrl]['q1']
                    rh[gate_id]['q2'] = rh[previous_gate_id_ctrl]['q2']
                else:
                    rh[gate_id]['q1'] = rh[previous_gate_id_ctrl]['q2']
                    rh[gate_id]['q2'] = rh[previous_gate_id_ctrl]['q1']
            else:
                # 3.1 find previous qubit for the control
                if 'q1' not in rh[gate_id].keys():
                    if rh[previous_gate_id_ctrl]['next_q1'] // 10 == gate_id:
                        rh[gate_id]['q1'] = rh[previous_gate_id_ctrl]['q1']
                    elif rh[previous_gate_id_ctrl]['next_q2'] // 10 == gate_id:
                        rh[gate_id]['q1'] = rh[previous_gate_id_ctrl]['q2']
                # 3.2 find previous qubit for the target
                if 'q2' not in rh[gate_id].keys():
                    if rh[previous_gate_id_tgt]['next_q1'] // 10 == gate_id:
                        rh[gate_id]['q2'] = rh[previous_gate_id_tgt]['q1']
                    elif rh[previous_gate_id_tgt]['next_q2'] // 10 == gate_id:
                        rh[gate_id]['q2'] = rh[previous_gate_id_tgt]['q2']
            rh[gate_id]['q3'] = None

    circuit = db_dictionary_to_circuit(dictionary=rh, n_qubits=n_qubits)
    return circuit


def db_dictionary_to_circuit(dictionary: dict, n_qubits):
    circuit = cirq.Circuit()
    q = [cirq.NamedQubit(str(j)) for j in range(n_qubits)]
    for k, v in dictionary.items():
        if v['type'] == 'In' or v['type'] == 'Out':
            if v["meas_key"] is None:
                cirq_gate = eval(f'{v["type"]}()').on(q[v['q1']])
            else:
                cirq_gate = eval(f'{v["type"]}(init_val="{v["meas_key"]}")').on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == '_PauliX':
            cirq_gate = cirq.X.on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == '_PauliY':
            cirq_gate = cirq.Y.on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == '_PauliZ':
            cirq_gate = cirq.Z.on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == 'Rx':
            cirq_gate = cirq.Rx(rads=v['param'] * np.pi).on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == 'Rz':
            cirq_gate = cirq.Rz(rads=v['param'] * np.pi).on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == 'Ry':
            cirq_gate = cirq.Ry(rads=v['param'] * np.pi).on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == 'M':
            cirq_gate = cirq.MeasurementGate(num_qubits=1, key=v['meas_key']).on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] == 'ResetChannel':
            cirq_gate = cirq.ResetChannel().on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] in SINGLE_QUBIT_GATES.keys():
            cirq_gate_name = v["type"].split('**')[0]
            cirq_gate = eval(f'cirq.{cirq_gate_name}(exponent={v["param"]})').on(q[v['q1']])
            circuit.append(cirq_gate)
            continue
        if v['type'] in TWO_QUBIT_GATES.keys():
            cirq_gate_name = v["type"].split('**')[0]
            cirq_gate = eval(f'cirq.{cirq_gate_name}(exponent={v["param"]})').on(q[v['q1']], q[v['q2']])

        circuit.append(cirq_gate)

    return circuit


def cirq_to_db(cirq_circuit: cirq.Circuit,
               last_id: int,
               label: Optional[str] = None,
               add_margins=False
               ) -> tuple[List[tuple], int]:
    """
    Fast method which converts a cirq circuit into a list of tuples which can be used as database entries.

    Args:

        cirq_circuit: the circuit that is inserted into the database
        last_id: the id of the first tuple that is inserted in the database.
        label: a string which describes the circuit and can be later used for retrieving the circuit from the database

    Returns:
        A list of tuples where each tuple describes a circuit operation.
    """
    # db specs for every circuit operation
    op_db_specs = {}

    # last id concatenated with gate wire on each qubit
    # the convention is that we concatenate to the id a value between 1-3 as follows:
    # * (1) for control or single qubit gate;
    # * (2) for target or second control
    # * (3) for target
    latest_conc_on_qubit = {}
    in_values = [None, None, None, 'In', 0, False, None, None, None, False, label, None, None, None, None, None]

    # the permutation of the qubits depends on the ordering of the In gates
    # sorting works for now
    if add_margins:
        circuit_in = cirq.Circuit(cirq.Moment(In().on(q) for q in sorted(cirq_circuit.all_qubits())))
        circuit_out = cirq.Circuit(cirq.Moment(Out().on(q) for q in sorted(cirq_circuit.all_qubits())))
        cirq_circuit = circuit_in + cirq_circuit + circuit_out

    # assume tuples will have elements in this order: id(0), prev_q1(1), prev_q2(2), prev_q3(3), gate_name(4),
    # gate_param(5), switch(6), next_q1(7), next_q2(8), next_q3(9), visited(10), label(11), cl_ctrl(12)
    qubit_map = dict(zip(cirq_circuit.all_qubits(), list(range(len(cirq_circuit.all_qubits())))))
    for moment in cirq_circuit:
        for i, current_operation in enumerate(moment):
            # current gate is an initial gate with no prev values
            if isinstance(current_operation.gate, type(In())):
                latest_conc_on_qubit[current_operation.qubits[0]] = last_id * 10
                op_db_specs[last_id] = dict(zip(DB_COLUMNS, in_values))
                last_id += 1
                continue

            current_op_qubits = current_operation.qubits
            gate_name, gate_param, switch, is_classically_controlled, mes_key = get_cirq_gate_attr(current_operation)
            previous_concatenations = [latest_conc_on_qubit[q] for q in current_op_qubits]
            qubit_ids = [qubit_map[q] for q in current_op_qubits]
            while len(previous_concatenations) < MAX_QUBITS_PER_GATE:
                previous_concatenations.append(None)
                qubit_ids.append(None)

            # fill out missing 'next' links for the gates on the left
            for q_idx, q in enumerate(current_op_qubits):
                previous_id, previous_order_qubit = latest_conc_on_qubit[q] // 10, latest_conc_on_qubit[q] % 10
                op_db_specs[previous_id][f'next_q{previous_order_qubit + 1}'] = last_id * 10 + q_idx
                latest_conc_on_qubit[q] = last_id * 10 + q_idx

            current_values = [*previous_concatenations, gate_name, gate_param, switch,
                              None, None, None, False, label, is_classically_controlled, mes_key, *qubit_ids]

            op_db_specs[last_id] = dict(zip(DB_COLUMNS, current_values))
            last_id += 1

    db_tuples = [(k, *v.values()) for (k, v) in op_db_specs.items()]
    return db_tuples, last_id

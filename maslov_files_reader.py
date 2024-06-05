import re
import requests
from _connection import *


class Gate:
    def __init__(self, id, prev_q1, prev_q2, prev_q3, type, param, switch,
                 next_q1, next_q2, next_q3, visited, cl_ctrl, meas_key):
        self.id = id
        self.prev_q1 = prev_q1
        self.prev_q2 = prev_q2
        self.prev_q3 = prev_q3
        self.type = type
        self.param = param
        self.switch = switch
        self.next_q1 = next_q1
        self.next_q2 = next_q2
        self.next_q3 = next_q3
        self.visited = visited
        self.cl_ctrl = cl_ctrl
        self.meas_key = meas_key


def read_markov_file(circuit_url):
    circuit_lines = []

    if circuit_url.startswith("http"):
        response = requests.get(circuit_url)
        if response.status_code:
            data = response.text
        if data is not None:
            for line in enumerate(data.split('\n')):
                circuit_lines.append(line[1])
    else:
        with open(circuit_url, "r") as file:
            circuit_lines = [s.strip() for s in file.readlines()]

    return circuit_lines


def markov_file_to_tuples(url, gate_id, label):
    circuit_lines = read_markov_file(circuit_url=url)

    n_qubits = len(circuit_lines[0].split(','))
    db_tuples = []

    for line in circuit_lines:
        if line.startswith("QInit0"):
            n_qubits += 1

    gates_on_qubits = [j * 10 for j in range(n_qubits)]

    for id in range(n_qubits):
        db_tuples.append(Gate(gate_id, None, None, None, 'In', 0, False, None, None, None, False, None, None))
        gate_id += 1

    # gate_id += 1

    for line in circuit_lines:
        if line.startswith("QGate"):
            gate_name, controls = tuple(re.findall(r'\[.*?\]', line))
            target = re.findall(r'\(.*?\)', line)
            if eval(gate_name)[0] == 'not':
                control_qubits = eval(controls)
                target = eval(target[0])

                # 1.1 CNOT case
                if len(control_qubits) == 1:
                    control = control_qubits[0]
                    # NOT gate before first empty control
                    if control < 0:
                        control = control * -1
                        x_to_add = Gate(gate_id, gates_on_qubits[control], None, None, "_PauliX", 1, False,
                                        (gate_id + 1) * 10, None, None, False, None, None)
                        for gate in db_tuples:
                            if gate.id == gates_on_qubits[control] // 10:
                                setattr(gate, f'next_q{gates_on_qubits[control] % 10 + 1}', x_to_add.id * 10)
                        gates_on_qubits[control] = x_to_add.id * 10
                        db_tuples.append(x_to_add)
                        gate_id += 1

                    cx_to_add = Gate(gate_id, gates_on_qubits[control], gates_on_qubits[target], None, 'CXPowGate', 1,
                                     control < target, None, None, None, False, None, None)

                    prev_control_mod = gates_on_qubits[control] % 10
                    prev_control_id = gates_on_qubits[control] // 10

                    prev_target_mod = gates_on_qubits[target] % 10
                    prev_target_id = gates_on_qubits[target] // 10

                    # set previous links accordingly
                    for gate in db_tuples:
                        if gate.id == prev_control_id:
                            setattr(gate, f'next_q{prev_control_mod + 1}', cx_to_add.id * 10)
                        if gate.id == prev_target_id:
                            setattr(gate, f'next_q{prev_target_mod + 1}', cx_to_add.id * 10 + 1)

                    gates_on_qubits[control] = cx_to_add.id * 10
                    gates_on_qubits[target] = cx_to_add.id * 10 + 1
                    db_tuples.append(cx_to_add)
                    gate_id += 1

                    # NOT gate after empty control
                    if control_qubits[0] < 0:
                        x_to_add = Gate(gate_id, gates_on_qubits[control], None, None, "_PauliX", 1, False, None, None,
                                        None, False, None, None)
                        setattr(cx_to_add, f'next_q1', x_to_add.id * 10)
                        db_tuples.append(x_to_add)
                        gates_on_qubits[control] = x_to_add.id * 10
                        gate_id += 1

                # Toffoli gate
                elif len(control_qubits) == 2:
                    control_1, control_2 = control_qubits[0], control_qubits[1]
                    id_increment = 0
                    if control_qubits[0] < 0:
                        id_increment += 1
                    if control_qubits[1] < 0:
                        id_increment += 1

                    # NOT gate before first empty control
                    if control_qubits[0] < 0:
                        control_1 = control_qubits[0] * -1
                        x_to_add = Gate(gate_id, gates_on_qubits[control_1], None, None, "_PauliX", 1, False,
                                        (gate_id + id_increment) * 10, None, None, False, None, None)
                        for gate in db_tuples:
                            if gate.id == gates_on_qubits[control_1] // 10:
                                setattr(gate, f'next_q{gates_on_qubits[control_1] % 10 + 1}', x_to_add.id * 10)
                        gates_on_qubits[control_1] = x_to_add.id * 10
                        db_tuples.append(x_to_add)

                    # NOT gate before second empty control
                    if control_qubits[1] < 0:
                        control_2 = control_qubits[1] * -1
                        x_to_add = Gate(gate_id + id_increment - 1, gates_on_qubits[control_2], None, None, "_PauliX", 1,
                                        False, (gate_id + id_increment) * 10 + 1, None, None, False, None, None)
                        for gate in db_tuples:
                            if gate.id == gates_on_qubits[control_2] // 10:
                                setattr(gate, f'next_q{gates_on_qubits[control_2] % 10 + 1}', x_to_add.id * 10)
                        gates_on_qubits[control_2] = x_to_add.id * 10
                        db_tuples.append(x_to_add)

                    gate_id += id_increment
                    ccx_to_add = Gate(gate_id, gates_on_qubits[control_1], gates_on_qubits[control_2],
                                      gates_on_qubits[target], 'CCXPowGate', 1, False, None, None, None, False, None, None)

                    # set previous links accordingly
                    for gate in db_tuples:
                        if gate.id == gates_on_qubits[control_1] // 10:
                            setattr(gate, f'next_q{gates_on_qubits[control_1] % 10 + 1}', ccx_to_add.id * 10)
                        if gate.id == gates_on_qubits[control_2] // 10:
                            setattr(gate, f'next_q{gates_on_qubits[control_2] % 10 + 1}', ccx_to_add.id * 10 + 1)
                        if gate.id == gates_on_qubits[target] // 10:
                            setattr(gate, f'next_q{gates_on_qubits[target] % 10 + 1}', ccx_to_add.id * 10 + 2)

                    gates_on_qubits[control_1] = ccx_to_add.id * 10
                    gates_on_qubits[control_2] = ccx_to_add.id * 10 + 1
                    gates_on_qubits[target] = ccx_to_add.id * 10 + 2

                    db_tuples.append(ccx_to_add)

                    gate_id += 1

                    # NOT gate after first empty control
                    if control_qubits[0] < 0:
                        x_to_add = Gate(gate_id, gates_on_qubits[control_1], None, None, "_PauliX", 1, False, None, None,
                                        None, False, None, None)
                        setattr(ccx_to_add, f'next_q1', x_to_add.id * 10)
                        gates_on_qubits[control_1] = x_to_add.id * 10
                        db_tuples.append(x_to_add)

                    # NOT gate after second empty control
                    if control_qubits[1] < 0:
                        x_to_add = Gate(gate_id + id_increment - 1, gates_on_qubits[control_2], None, None, "_PauliX", 1,
                                        False, None, None, None, False, None, None)
                        setattr(ccx_to_add, f'next_q2', x_to_add.id * 10)
                        gates_on_qubits[control_2] = x_to_add.id * 10
                        db_tuples.append(x_to_add)

                    gate_id += id_increment

    for i in range(n_qubits):
        db_tuples.append(Gate(gate_id, gates_on_qubits[i], None, None, 'Out', 0, False, None, None, None, False, None, None))
        for gate in db_tuples:
            if gate.id == gates_on_qubits[i] // 10:
                setattr(gate, f'next_q{gates_on_qubits[i] % 10 + 1}', gate_id * 10)
        gate_id += 1

    return [
        (t.id, t.prev_q1, t.prev_q2, t.prev_q3, t.type, t.param, t.switch, t.next_q1, t.next_q2, t.next_q3, t.visited,
         label, t.cl_ctrl, t.meas_key)
        for t in db_tuples], gate_id


def get_maslov_adder(conn, n_bits):
    create_linked_table(conn=conn, clean=True)
    refresh_all_stored_procedures(conn=conn)

    url = f'https://raw.githubusercontent.com/njross/optimizer/master/QFT_and_Adders/Adder{n_bits}_before'
    db_tuples, _ = markov_file_to_tuples(url, gate_id=0, label=f'Adder{n_bits}')
    return db_tuples

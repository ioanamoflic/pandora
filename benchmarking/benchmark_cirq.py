import random
import cirq
from cirq2db import In, Out

"""Define a custom single-qubit gate."""


@cirq.transformer
def remove_double_hadamards(circuit, context=None) \
        -> list[tuple[int, int, cirq.Qid]] | cirq.Circuit:
    """Applies circuit identity b) to all locations of the circuit that permit it

    Args:
        circuit (cirq.Circuit): original circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit gotten by applying the identity
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    removals = []
    for moment_ind in range(len(mutated_circuit) - 1):
        for operation in mutated_circuit[moment_ind].operations:
            if operation.gate != cirq.H or (moment_ind, operation) in removals:
                continue

            qubit = operation.qubits[0]
            moment_ind_2 = mutated_circuit.next_moment_operating_on(qubits=[qubit],
                                                                    start_moment_index=moment_ind + 1)

            if (moment_ind_2 is not None and
                    operation in mutated_circuit[moment_ind_2] and
                    (moment_ind_2, operation) not in removals):
                removals.extend([(moment_ind, operation), (moment_ind_2, operation)])

    mutated_circuit.batch_remove(removals)
    mutated_circuit = cirq.drop_empty_moments(mutated_circuit)
    return mutated_circuit


@cirq.transformer
def remove_double_cnots(circuit, context=None):
    """Applies circuit identity c) to all locations of the circuit that permit it

    Args:
        circuit (cirq.Circuit): original circuit
    Returns:
        mutated_circuit (cirq.Circuit): circuit gotten by applying the identity
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    removals = []
    for moment_ind in range(len(mutated_circuit) - 1):
        for operation in mutated_circuit[moment_ind].operations:
            if operation.gate != cirq.CNOT or (moment_ind, operation) in removals:
                continue

            control_qubit = operation.qubits[0]
            moment_inds_2 = mutated_circuit.next_moments_operating_on(qubits=operation.qubits,
                                                                      start_moment_index=moment_ind + 1)
            if (moment_inds_2[control_qubit] != len(mutated_circuit) and
                operation in mutated_circuit[moment_inds_2[control_qubit]] and
                moment_inds_2[control_qubit], operation) not in removals:
                removals.extend([(moment_ind, operation), (moment_inds_2[control_qubit], operation)])

    mutated_circuit.batch_remove(removals)
    mutated_circuit = cirq.drop_empty_moments(mutated_circuit)
    return mutated_circuit


def add_two_hadamards(circuit, qubits):
    """Adds two Hadamard gates to a randomly chosen qubit of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which Hadamards are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added Hadamards
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    random_qubit = random.choice(qubits)
    mutated_circuit.append([cirq.H(random_qubit), cirq.H(random_qubit)])

    return mutated_circuit


def add_t_t_dag(circuit, qubits):
    """Adds two Hadamard gates to a randomly chosen qubit of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which Hadamards are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added Hadamards
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    random_qubit = random.choice(qubits)
    mutated_circuit.append([cirq.T(random_qubit), cirq.T(random_qubit) ** -1])
    return mutated_circuit


def add_t_cx(circuit, qubits):
    """Adds two Hadamard gates to a randomly chosen qubit of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which Hadamards are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added Hadamards
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    control_qubit, target_qubit = random.sample(qubits, 2)
    mutated_circuit.append([cirq.T(control_qubit), cirq.CNOT(control_qubit, target_qubit)])
    return mutated_circuit


def add_cx_t(circuit, qubits):
    """Adds two Hadamard gates to a randomly chosen qubit of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which Hadamards are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added Hadamards
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    control_qubit, target_qubit = random.sample(qubits, 2)
    mutated_circuit.append([cirq.CNOT(control_qubit, target_qubit), cirq.T(control_qubit)])
    return mutated_circuit


def add_two_cnots(circuit, qubits):
    """Adds a two CNOT-gates to a randomly chosen pair of qubits of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which 2 CNOTs are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added CNOTs
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    control_qubit, target_qubit = random.sample(qubits, 2)
    mutated_circuit.append([cirq.CNOT(control_qubit, target_qubit),
                            cirq.CNOT(control_qubit, target_qubit)])
    return mutated_circuit


def add_toffoli(circuit, qubits):
    """Adds a two CNOT-gates to a randomly chosen pair of qubits of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which 2 CNOTs are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added CNOTs
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    # control_qubit_1, control_qubit_2, target_qubit = random.sample(qubits, 3)
    control_qubit_1, control_qubit_2, target_qubit = qubits[0], qubits[1], qubits[2]
    mutated_circuit.append(cirq.CCNOT(control_qubit_1, control_qubit_2, target_qubit))

    return mutated_circuit


def add_base_change(circuit, qubits):
    """Adds a CNOT-gate and four surrounding Hadamards to a randomly chosen pair of qubits of
    the input circuit.

    Args:
        circuit (cirq.Circuit): circuit to which 4 Hadamards and one CNOT are added
        qubits (list(cirq.LineQubit)): qubits of the circuit

    Returns:
        mutated_circuit (cirq.Circuit): circuit with added gates
    """
    mutated_circuit = circuit.unfreeze(copy=True)
    control_qubit, target_qubit = random.sample(qubits, 2)
    mutated_circuit.append([cirq.H(control_qubit), cirq.H(target_qubit),
                            cirq.CNOT(control_qubit, target_qubit),
                            cirq.H(control_qubit), cirq.H(target_qubit)])
    return mutated_circuit


def get_gate_count(circuit):
    counter: int = 0
    for moment in circuit:
        counter += len(moment)
    return counter


def create_random_circuit(n_qubits,
                          n_templates,
                          templates=None,
                          add_margins=False):
    """
    Creates a Cirq circuit and adds multiple randomly chosen
    templates (left hand sides of the circuit identities) by
    calling the functions defined above.

    Args:
        n_qubits (int): amount of qubits in the circuit
        n_templates (int): amount of templates added to the circuit
        templates (List[str]): the list of templates to choose from
        add_margins (boolean): whether to add database I/O gates or not

    Returns:
        circuit (cirq.Circuit): the resulted random circuit
    """
    if templates is None:
        templates = ['add_two_hadamards', 'add_two_cnots', 'add_base_change', 'add_t_t_dag', 'add_t_cx', 'add_cx_t',
                     'add_toffoli']

    function_list = [eval(t) for t in templates]

    qubits = cirq.LineQubit.range(n_qubits)
    circuit = cirq.Circuit()
    for n_qubits in range(n_templates):
        circuit = random.choice(function_list)(circuit, qubits)

    if add_margins:
        circuit_in = cirq.Circuit(cirq.Moment(In().on(q) for q in sorted(circuit.all_qubits())))
        circuit_out = cirq.Circuit(cirq.Moment(Out().on(q) for q in sorted(circuit.all_qubits())))
        circuit = circuit_in + circuit + circuit_out

    circuit = cirq.Circuit(circuit.all_operations(), strategy=cirq.InsertStrategy.EARLIEST)
    return circuit


def make_oracle(input_qubits, output_qubit, secret):
    for qubit, bit in zip(input_qubits, secret):
        if bit == '1':
            yield cirq.CNOT(qubit, output_qubit)


def bernstein_vazirani(nr_bits=2, secret="11"):
    # n - number of bits
    # secret - the bit string called 'a' in some algorithm descriptions
    # Returns an n+1 qubit circuit, where the (n+1)-th qubit is for phase kickback

    input_qubits = [cirq.NamedQubit(str(i)) for i in range(nr_bits)]
    output_qubit = cirq.NamedQubit(str(nr_bits))

    circuit = cirq.Circuit()

    circuit.append(
        [
            cirq.X(output_qubit),
            cirq.H(output_qubit),
            cirq.H.on_each(input_qubits),
        ]
    )

    oracle = make_oracle(input_qubits, output_qubit, secret)

    circuit.append(oracle)

    # circuit.append([cirq.H.on_each(input_qubits), cirq.measure(*input_qubits, key='result')])
    circuit.append(cirq.H.on_each(input_qubits))

    return circuit
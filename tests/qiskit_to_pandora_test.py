import time

from qiskit.quantum_info import random_clifford

from pandora.pandora_util import pandora_to_circuit
from pandora.qiskit_to_pandora_util import convert_qiskit_to_pandora, remove_io_gates


def test_random_reconstruction(n_circuits=100):
    for i in range(n_circuits):
        print(f'Random test {i}')
        start_time = time.time()
        initial_circuit = random_clifford(num_qubits=4).to_circuit()

        print(initial_circuit.draw())

        print(f'Time for create_random_circuit: {time.time() - start_time}')

        start_time = time.time()
        db_tuples, last_id = convert_qiskit_to_pandora(qiskit_circuit=initial_circuit,
                                                       label='t',
                                                       add_margins=True)
        print(f'Time for qiskit_to_db: {time.time() - start_time}')

        start_time = time.time()
        reconstructed_circuit = pandora_to_circuit(pandora_gates=db_tuples,
                                                   circuit_type='qiskit')

        reconstructed_circuit = remove_io_gates(reconstructed_circuit)

        print(reconstructed_circuit.draw())

        print(f'Time for db_to_qiskit: {time.time() - start_time}')

        start_time = time.time()

        assert initial_circuit == reconstructed_circuit

        print(f'Time for assertion: {time.time() - start_time}')
        print('Test passed!')


if __name__ == "__main__":
    test_random_reconstruction(n_circuits=5)

import cirq

from pandora.translation.circuit_to_dag import PandoraWindowedBuilder
from pandora.translation.dag_to_circuit import pandora_to_circuit
from pandora.translation.link import LinkID
from pandora.util.circuit_util import remove_io_gates


def test_parallel_builders_preserve_circuits_and_use_disjoint_gate_ids():
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.T(q1), cirq.X(q0))
    all_ids = set()
    workers = 12
    for worker in range(workers):
        builder = PandoraWindowedBuilder(
            label=str(worker), window_size=2, id_start=worker, id_step=workers,
        )
        gates = [gate for batch in builder.consume(circuit) for gate in batch]
        gates.extend(builder.finalize())
        ids = {gate.id for gate in gates}
        assert len(ids) == len(gates)
        assert not all_ids.intersection(ids)
        all_ids.update(ids)
        assert all(gate.label == str(worker) for gate in gates)
        for gate in gates:
            for link in (gate.prev_q1, gate.prev_q2, gate.prev_q3,
                         gate.next_q1, gate.next_q2, gate.next_q3):
                if link is not None:
                    assert LinkID.gate_id(link) in ids
        reconstructed = remove_io_gates(pandora_to_circuit(gates))
        # Round trips rename qubits; restore the original line-qubit names.
        reconstructed = reconstructed.transform_qubits(
            dict(zip(sorted(reconstructed.all_qubits()), (q0, q1)))
        )
        cirq.testing.assert_same_circuits(circuit, reconstructed)

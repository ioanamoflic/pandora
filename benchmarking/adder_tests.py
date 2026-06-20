import asyncio

from qiskit import QuantumCircuit

from benchmarking.benchmark_adders import get_adder, decompose_toffoli_qiskit
from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora import PandoraOptimiser, PandoraService
from pandora.translation.translator import PandoraGateTranslator


def decompose_toffoli_qiskit_reverse(qc, c0, c1, t):
    qc.h(t)

    qc.t(t)
    qc.t(c1)
    qc.t(c0)

    qc.cx(c0, c1)
    qc.tdg(c1)

    qc.cx(c0, c1)
    qc.cx(c0, t)

    qc.tdg(t)
    qc.cx(c1, t)

    qc.t(t)
    qc.cx(c0, t)

    qc.tdg(t)
    qc.cx(c1, t)

    qc.h(t)


def decompose_toffoli_qiskit_reverse_dagger(qc, c0, c1, t):
    qc.h(t)

    qc.tdg(t)
    qc.tdg(c1)
    qc.tdg(c0)

    qc.cx(c0, c1)
    qc.t(c1)

    qc.cx(c0, c1)
    qc.cx(c0, t)

    qc.t(t)
    qc.cx(c1, t)

    qc.tdg(t)
    qc.cx(c0, t)

    qc.t(t)
    qc.cx(c1, t)

    qc.h(t)


def replace_all_toffolis_qiskit(qc, case: int):
    new_qc = QuantumCircuit(qc.num_qubits)

    qubit_map = {qb: i for i, qb in enumerate(qc.qubits)}

    for i, inst in enumerate(qc.data):
        op = inst.operation
        qargs = inst.qubits
        cargs = inst.clbits

        if op.name == "ccx":
            c0 = qubit_map[qargs[0]]
            c1 = qubit_map[qargs[1]]
            t = qubit_map[qargs[2]]

            if i % 2 == 0:
                decompose_toffoli_qiskit(new_qc, c0, c1, t)
            else:
                if case == 0:
                    decompose_toffoli_qiskit_reverse(new_qc, c0, c1, t)
                elif case == 1:
                    decompose_toffoli_qiskit_reverse_dagger(new_qc, c0, c1, t)
        else:
            new_qc.append(op, qargs, cargs)

    return new_qc


async def run_optimiser(adder_circuit):
    db = PandoraDB()
    await db.connect()

    try:
        pandora_optimizer = PandoraOptimiser(
            db=db,
            pass_count=int(2e9),
            timeout=1,
            logger_id=1,
        )

        repo = GateRepository(db)
        service = PandoraService(db=db,
                                 repo=repo)

        await service.build_circuit(
            circuit=adder_circuit
        )

        H = PandoraGateTranslator.HPowGate
        Z = PandoraGateTranslator._PauliZ
        X = PandoraGateTranslator._PauliX
        CX = PandoraGateTranslator.CXPowGate
        T = PandoraGateTranslator.T
        T_dag = PandoraGateTranslator.T_dag
        S = PandoraGateTranslator.S
        S_dag = PandoraGateTranslator.S_dag

        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(H, H),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(Z, Z),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(T, T_dag),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(T_dag, T),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(S, S_dag),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(S_dag, S),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.cancel_single_qubit_gates(
            gate_types=(X, X),
            gate_params=(0, 0),
            dedicated_nproc=1,
        )

        pandora_optimizer.cancel_two_qubit_gates(
            gate_types=(CX, CX),
            gate_param=0,
            dedicated_nproc=1,
        )

        pandora_optimizer.fuse_single_qubit_gates(
            gate_types=(T, T, S),
            gate_params=(0, 0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.fuse_single_qubit_gates(
            gate_types=(T_dag, T_dag, S_dag),
            gate_params=(0, 0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.fuse_single_qubit_gates(
            gate_types=(S, S, Z),
            gate_params=(0, 0, 0),
            dedicated_nproc=1,
        )
        pandora_optimizer.fuse_single_qubit_gates(
            gate_types=(S_dag, S_dag, Z),
            gate_params=(0, 0, 0),
            dedicated_nproc=1,
        )

        pandora_optimizer.commute_rotation_with_control_left(
            gate_type=Z,
            gate_param=0,
            dedicated_nproc=1,
        )
        pandora_optimizer.commute_rotation_with_control_left(
            gate_type=S,
            gate_param=0,
            dedicated_nproc=1,
        )
        pandora_optimizer.commute_rotation_with_control_left(
            gate_type=S_dag,
            gate_param=0,
            dedicated_nproc=1,
        )
        pandora_optimizer.commute_rotation_with_control_left(
            gate_type=T,
            gate_param=0,
            dedicated_nproc=1,
        )
        pandora_optimizer.commute_rotation_with_control_left(
            gate_type=T_dag,
            gate_param=0,
            dedicated_nproc=1,
        )

        pandora_optimizer.hhcxhh_to_cx(dedicated_nproc=1)
        pandora_optimizer.log()

        await pandora_optimizer.start()
        await pandora_optimizer.generate_csv(logger_id=1)

        return await service.load_circuit(circuit_type='qiskit')

    finally:
        await db.close()


async def main():
    adder_circuit = get_adder(n_bits=1)
    adder_circuit = replace_all_toffolis_qiskit(adder_circuit, case=0)
    print("Before:")
    print(adder_circuit)
    extracted_circuit = await run_optimiser(adder_circuit)
    print("After:")
    print(extracted_circuit)

    adder_circuit = get_adder(n_bits=1)
    adder_circuit = replace_all_toffolis_qiskit(adder_circuit, case=1)
    print("Before:")
    print(adder_circuit)
    extracted_circuit = await run_optimiser(adder_circuit)
    print("After:")
    print(extracted_circuit)

    assert len(extracted_circuit.data) == 6  # I/O gates


if __name__ == "__main__":
    asyncio.run(main())

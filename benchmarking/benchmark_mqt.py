import asyncio
import csv
import random
import sys
import time

import qiskit.qasm3
from mqt.qcec import verify
from mqt.qcec.pyqcec import EquivalenceCriterion
from qiskit import QuantumCircuit

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.optimisation.optimiser import PandoraOptimiser
from pandora.translation.translator import PandoraGateTranslator


def generate_random_cnot_circuit(num_qubits: int = 2, num_gates: int = 8) -> QuantumCircuit:
    if num_qubits < 2:
        num_qubits = 2

    circuit = QuantumCircuit(num_qubits, num_qubits)

    for _ in range(num_gates):
        control = random.randint(0, num_qubits - 1)
        target = control
        while target == control:
            target = random.randint(0, num_qubits - 1)

        circuit.cx(control, target)

    return circuit


def remove_random_gate(circuit: QuantumCircuit) -> QuantumCircuit:
    if not circuit.data:
        return circuit.copy()

    remove_index = random.randint(0, len(circuit.data) - 1)
    new_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

    for i, instruction in enumerate(circuit.data):
        if i == remove_index:
            continue
        new_circuit.append(instruction.operation, instruction.qubits, instruction.clbits)

    return new_circuit


def save_qasm(circuit: QuantumCircuit, path: str) -> None:
    with open(path, "w") as f:
        qiskit.qasm3.dump(circuit, f)


def load_benchmark_circuits(num_qubits: int, run_idx: int, is_equiv: int) -> tuple[QuantumCircuit, QuantumCircuit]:
    circ1 = qiskit.qasm3.load(f"circ1_{num_qubits}_{run_idx}_{is_equiv}.qasm")
    if is_equiv == 0:
        circ2 = circ1.copy()
    else:
        circ2 = qiskit.qasm3.load(f"circ2_{num_qubits}_{run_idx}_{is_equiv}.qasm")
    return circ1, circ2


def build_benchmark_circuits(num_qubits: int, run_idx: int, is_equiv: int) -> tuple[QuantumCircuit, QuantumCircuit]:
    circ1 = generate_random_cnot_circuit(num_qubits, num_qubits ** 3)
    save_qasm(circ1, f"circ1_{num_qubits}_{run_idx}_{is_equiv}.qasm")

    if is_equiv == 0:
        circ2 = circ1.copy()
    else:
        circ2 = remove_random_gate(circ1)
        save_qasm(circ2, f"circ2_{num_qubits}_{run_idx}_{is_equiv}.qasm")

    return circ1, circ2


async def pandora_verify(
        nprocs: int,
        circ1: QuantumCircuit,
        circ2: QuantumCircuit,
        timeout_sec: int,
) -> bool:
    concatenated = circ1.compose(circ2.inverse())
    cx_gate = PandoraGateTranslator.CXPowGate

    db = PandoraDB()
    await db.connect()

    try:
        repo = GateRepository(db)
        service = PandoraService(db=db,
                                 repo=repo)

        optimiser = PandoraOptimiser(
            db=db,
            pass_count=int(2e9),
            timeout=timeout_sec,
            logger_id=1,
            max_concurrency=nprocs
        )

        await service.build_circuit(circuit=concatenated)

        optimiser.cancel_two_qubit_gates_equiv(
            gate_types=(cx_gate, cx_gate),
            num_qubits=concatenated.num_qubits,
            dedicated_nproc=nprocs,
        )

        await optimiser.start()

        reduced_circuit = await service.load_circuit(circuit_type="qiskit")
        gate_count = len(reduced_circuit.data)

        return gate_count == 2 * concatenated.num_qubits

    finally:
        await db.close()


def mqt_verify(bench: str, circ1: QuantumCircuit, circ2: QuantumCircuit, timeout_sec: int) -> tuple[
    EquivalenceCriterion, float, float]:
    start = time.time()
    
    if bench == 'zx':
        result = verify(
            circ1,
            circ2,
            timeout=timeout_sec,
            run_simulation_checker=False,
            run_alternating_checker=False,
        )
    elif bench == 'dd':
        result = verify(
            circ1,
            circ2,
            timeout=timeout_sec,
            run_simulation_checker=False,
            run_zx_checker=False,
        )
    wall_time = time.time() - start
    return result.equivalence, wall_time, result.check_time


async def run_pandora_benchmark(
        num_qubits: int,
        run_idx: int,
        is_equiv: int,
        nprocs: int,
        timeout_sec: int,
) -> tuple[bool, float, float]:
    circ1, circ2 = build_benchmark_circuits(num_qubits, run_idx, is_equiv)

    start = time.time()
    equiv = await pandora_verify(
        nprocs=nprocs,
        circ1=circ1,
        circ2=circ2,
        timeout_sec=timeout_sec,
    )
    wall_time = time.time() - start

    return equiv, wall_time, 0.0


def run_mqt_benchmark(
        bench: str,
        num_qubits: int,
        run_idx: int,
        is_equiv: int,
        timeout_sec: int,
) -> tuple[EquivalenceCriterion, float, float]:
    circ1, circ2 = load_benchmark_circuits(num_qubits, run_idx, is_equiv)
    return mqt_verify(bench, circ1, circ2, timeout_sec)


async def main():
    if len(sys.argv) != 4:
        sys.exit(0)

    is_equiv = int(sys.argv[1])
    backend = sys.argv[2]
    exp_id = int(sys.argv[3])

    assert backend in ['pandora', 'dd', 'zx']
    
    timeout_sec = 1000
    nprocs = 1
    nr_runs = 10
    results = []

    for num_qubits in range(32, 33, 2):
        total_time = 0.0

        for run_idx in range(nr_runs):
            correctness = "correct" if is_equiv == 0 else "incorrect"
            print(num_qubits, run_idx, correctness)

            if backend == "pandora":
                equiv, wall_time, backend_check_time = await run_pandora_benchmark(
                    num_qubits=num_qubits,
                    run_idx=run_idx,
                    is_equiv=is_equiv,
                    nprocs=nprocs,
                    timeout_sec=timeout_sec,
                )
                print("Pandora time:", wall_time)
                print("Equiv:", equiv)

            else:
                equiv, wall_time, backend_check_time = run_mqt_benchmark(
                    bench=backend,
                    num_qubits=num_qubits,
                    run_idx=run_idx,
                    is_equiv=is_equiv,
                    timeout_sec=timeout_sec,
                )
                print("MQT time:", wall_time)
                print("Equiv:", equiv)

            total_time += wall_time
            results.append(
                (num_qubits, run_idx, equiv, wall_time, backend_check_time, backend)
            )

        print("-----", total_time / nr_runs)

    out_path = f"{backend}_{is_equiv}_verification_{exp_id}.csv"
    with open(out_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(results)


if __name__ == "__main__":
    asyncio.run(main())

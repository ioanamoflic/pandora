import asyncio

import re

from qiskit import QuantumCircuit

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.translation.translator import PandoraGateTranslator
from pandora import PandoraOptimiser


def parse_controls(ctr_str):
    """
        Parse control qubits list.
        + = filled control
        - = hollow control
    """
    if not ctr_str:
        return []
    ctr = []
    for match in re.finditer(r'([+-])(\d+)', ctr_str):
        polarity, idx = match.groups()
        ctr.append((int(idx), polarity == '+'))
    return ctr


def apply_not_with_controls(qc, target, controls):
    """
        Apply the controlled-NOT gate to the circuit.
        Adds additional X gates for hollow Toffoli controls.
    """
    if not controls:
        qc.x(target)
    elif len(controls) == 1:
        control, polarity = controls[0]
        if polarity:
            qc.cx(control, target)
        else:
            qc.x(control)
            qc.cx(control, target)
            qc.x(control)
    elif len(controls) == 2:
        for c, p in controls:
            if not p:
                qc.x(c)
        control_ids = [cp[0] for cp in controls]
        qc.ccx(*control_ids, target_qubit=target)
        for c, p in controls:
            if not p:
                qc.x(c)
    else:
        raise "Issue occurred, too many controls."


def get_adder(n_bits: int):
    n_qubits = 3 * n_bits
    qc = QuantumCircuit(n_qubits)

    # Adders from https://github.com/njross/optimizer/tree/master/QFT_and_Adders
    with open(f"benchmarking/adders/Adder{n_bits}.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("QGate[\"not\"]"):
                target = int(re.search(r'\((\d+)\)', line).group(1))
                control_match = re.search(r'controls=\[([^\]]*)\]', line)
                control_str = control_match.group(1) if control_match else ''
                controls = parse_controls(control_str)
                apply_not_with_controls(qc, target, controls)
    return qc


def decompose_toffoli_qiskit(qc, c0, c1, t):
    qc.h(t)

    qc.cx(c1, t)
    qc.tdg(t)

    qc.cx(c0, t)
    qc.t(t)

    qc.cx(c1, t)
    qc.tdg(t)

    qc.cx(c0, t)
    qc.cx(c0, c1)

    qc.tdg(c1)
    qc.cx(c0, c1)

    qc.t(c0)
    qc.t(c1)
    qc.t(t)

    qc.h(t)


def replace_all_toffolis_qiskit(qc):
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

            decompose_toffoli_qiskit(new_qc, c0, c1, t)

        else:
            new_qc.append(op, qargs, cargs)

    return new_qc
        
        
async def main():
    # 30 seconds timeout for the optimiser
    timeout = 30
    
    for n_bits in [16, 32, 64, 128, 256, 512, 1024, 2048]:
        adder_circuit = get_adder(n_bits=n_bits)
        adder_circuit = replace_all_toffolis_qiskit(adder_circuit)
        
        db = PandoraDB()
        await db.connect()
        
        try:
            pandora_optimizer = PandoraOptimiser(
                db=db,
                pass_count=int(1e7),
                timeout=timeout,
                logger_id=n_bits,
            )

            repo = GateRepository(db)
            service = PandoraService(db=db, repo=repo)
            
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
            await pandora_optimizer.generate_csv(logger_id=n_bits)

        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())



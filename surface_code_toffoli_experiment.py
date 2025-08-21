#!/usr/bin/env python3
"""
Surface Code Toffoli Experiment (Pandora orchestrator)

Workflow:
1) Generate Stim circuit for rotated memory X, distance=3, rounds=1
2) Import the circuit into Pandora three times on disjoint qubit ranges (skip H gates)
3) Choose first qubit of each block; create a Toffoli with two controls (blocks 0,1) and target (block 2)
4) Insert everything into Pandora

Notes:
- Step 4 (moving Toffoli through CNOTs) depends on specific rewrite procedures; this script prepares the
  circuit and inserts it. You can then run the appropriate Pandora rewrites.
"""

import os
import sys
import subprocess
from typing import List, Tuple

import stim
import cirq

# Ensure this script can import from src when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pandora.import_stim_to_pandora import parse_stim_clifford_gates
from pandora.cirq_to_pandora_util import cirq_to_pandora
from pandora.connection_util import get_connection, insert_in_batches


def generate_stim_surface_code(distance: int = 3, rounds: int = 1, task: str = "rotated_memory_x") -> str:
    """Generate the stim circuit via CLI and return its text."""
    cmd = [
        'stim', 'gen',
        '--code', 'surface_code',
        '--distance', str(distance),
        '--rounds', str(rounds),
        '--task', task
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    text = res.stdout
    out_file = f"surface_code_d{distance}_r{rounds}_{task}.stim"
    with open(out_file, 'w') as f:
        f.write(text)
    return text


def _offset_ops(ops: List[cirq.Operation], offset: int) -> List[cirq.Operation]:
    if offset == 0:
        return ops
    remapped = []
    for op in ops:
        new_qubits = [cirq.LineQubit(q.x + offset) if isinstance(q, cirq.LineQubit) else q for q in op.qubits]
        remapped.append(op.gate.on(*new_qubits))
    return remapped


def _used_qubits_from_ops(ops: List[cirq.Operation]) -> set:
    used = set()
    for op in ops:
        used.update(set(op.qubits))
    return used


def _parse_with_compat(stim_circuit: stim.Circuit, skip_h: bool, offset: int) -> Tuple[List[cirq.Operation], set]:
    try:
        # New signature supports skip_h and offset and returns (ops, used_qubits)
        ops, used = parse_stim_clifford_gates(stim_circuit, skip_h=skip_h, offset=offset)
        return ops, used
    except TypeError:
        # Backward compatibility: old signature without kwargs
        ops = parse_stim_clifford_gates(stim_circuit)
        if skip_h:
            ops = [op for op in ops if op.gate != cirq.H]
        if offset:
            ops = _offset_ops(ops, offset)
        used = _used_qubits_from_ops(ops)
        return ops, used


def build_three_blocks_from_stim(stim_text: str) -> Tuple[cirq.Circuit, List[int], int]:
    """
    Parse the stim circuit; build 3 blocks of cirq operations with disjoint qubits (skip H gates).
    Returns (combined cirq circuit, first_qubits_per_block, block_span).
    """
    base = stim.Circuit(stim_text)
    # First block (offset 0)
    ops0, used0 = _parse_with_compat(base, skip_h=True, offset=0)
    block_span = (max(q.x for q in used0) + 1) if used0 else 0
    # Second and third blocks, offset by span
    ops1, used1 = _parse_with_compat(base, skip_h=True, offset=block_span)
    ops2, used2 = _parse_with_compat(base, skip_h=True, offset=2 * block_span)

    c0 = cirq.Circuit(ops0)
    c1 = cirq.Circuit(ops1)
    c2 = cirq.Circuit(ops2)
    combined = c0 + c1 + c2

    first_qubits = [
        min((q.x for q in used0), default=0),
        min((q.x for q in used1), default=block_span),
        min((q.x for q in used2), default=2 * block_span),
    ]
    return combined, first_qubits, block_span


def add_toffoli_to_circuit(circuit: cirq.Circuit, first_qubits: List[int]) -> cirq.Circuit:
    """Append a CCX using first qubit of block0 and block1 as controls, block2 as target."""
    q_control_0 = cirq.LineQubit(first_qubits[0])
    q_control_1 = cirq.LineQubit(first_qubits[1])
    q_target = cirq.LineQubit(first_qubits[2])
    ccx = cirq.CCX(q_control_0, q_control_1, q_target)
    return circuit + cirq.Circuit(ccx)


def main():
    print("Generating Stim surface code circuit (d=3, r=1, task=rotated_memory_x)...")
    stim_text = generate_stim_surface_code(distance=3, rounds=1, task="rotated_memory_x")

    print("Building three disjoint blocks (skipping H gates)...")
    blocks_circuit, first_qubits, span = build_three_blocks_from_stim(stim_text)
    print(f"Block span: {span}; first qubits per block: {first_qubits}")

    print("Adding Toffoli between blocks: controls from block0/block1, target in block2...")
    full_circuit = add_toffoli_to_circuit(blocks_circuit, first_qubits)

    print("Converting to PandoraGate list and inserting into Pandora...")
    cfg_path = os.path.join(os.path.dirname(__file__), 'default_config.json')
    connection = get_connection(config_file_path=cfg_path)

    # Determine next available id to avoid primary key conflicts on re-runs
    try:
        cursor = connection.cursor()
        cursor.execute("select coalesce(max(id), -1) from linked_circuit")
        (max_id,) = cursor.fetchone()
        next_id = int(max_id) + 1
    except Exception:
        # If table does not exist yet, start from 0
        next_id = 0

    pandora_gates, _ = cirq_to_pandora(full_circuit, last_id=next_id, label="surface_code_toffoli", add_margins=True)
    insert_in_batches(pandora_gates=list(pandora_gates), connection=connection, table_name='linked_circuit')

    print("Done. The circuit with three surface-code blocks and a Toffoli has been inserted into Pandora.")
    print("Next: run your Toffoli/CNOT commute rewrites in Pandora, avoiding H-dependent patterns.")


if __name__ == "__main__":
    main()
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
import argparse

import stim
import cirq

# Ensure this script can import from src when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pandora.import_stim_to_pandora import parse_stim_clifford_gates
from pandora.cirq_to_pandora_util import cirq_to_pandora
from pandora.connection_util import get_connection, insert_in_batches, refresh_all_stored_procedures, drop_and_replace_tables
from pandora.gate_translator import PandoraGateTranslator


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


# -----------------------
# Cirq-level helpers (used only for building input)
# -----------------------

def _is_toffoli(op: cirq.Operation) -> bool:
    gate = op.without_classical_controls().gate
    try:
        from cirq.ops.common_gates import CCXPowGate
        return isinstance(gate, CCXPowGate) and getattr(gate, 'exponent', 1) % 2 == 1
    except Exception:
        return gate.__class__.__name__ in {"CCXPowGate", "CCX"}


# -----------------------
# DB-level rewrites and analysis
# -----------------------

def _toffoli_has_non_toffoli_after(connection) -> bool:
    query = """
        select 1
        from linked_circuit t
        join linked_circuit n on n.id in (
            t.next_q1 / 10,
            t.next_q2 / 10,
            t.next_q3 / 10
        )
        where t.type = 23
          and n.type <> 23
        limit 1;
    """
    cur = connection.cursor()
    cur.execute(query)
    return cur.fetchone() is not None


def apply_toffoli_rewrites_until_stable(connection, max_iters: int = 100) -> int:
    refresh_all_stored_procedures(connection)
    cur = connection.cursor()
    iterations = 0
    while iterations < max_iters:
        iterations += 1
        for proc in ("rewrite_toffoli_pattern_a", "rewrite_toffoli_pattern_b", "rewrite_toffoli_pattern_c", "rewrite_toffoli_pattern_d"):
            cur.execute(f"call {proc}();")
            connection.commit()
        # Stop only when ALL Toffolis are at the terminal suffix.
        # First, quick local check: no Toffoli has a non-Toffoli immediately after it.
        if not _toffoli_has_non_toffoli_after(connection):
            # Then, global check: the ordered end-chain length equals total number of Toffolis.
            cur.execute("select count(*) from linked_circuit where type=23")
            (total_toffolis,) = cur.fetchone()
            end_chain_len = len(_ordered_toffoli_ids_at_end(connection))
            if end_chain_len == total_toffolis:
                break
    return iterations


def _fetch_gate(connection, gate_id: int) -> tuple:
    cur = connection.cursor()
    cur.execute("select id, type, prev_q1, prev_q2, prev_q3, next_q1, next_q2, next_q3 from linked_circuit where id=%s", (gate_id,))
    return cur.fetchone()


def _walk_to_in_gate_id(connection, gate_id: int, prev_concat: int) -> int:
    in_type = PandoraGateTranslator.In.value
    current_id = gate_id
    concat = prev_concat
    while concat is not None:
        prev_id = int(concat) // 10
        prev_idx = int(concat) % 10  # 0-based
        row = _fetch_gate(connection, prev_id)
        if row is None:
            return prev_id
        _, gtype, p1, p2, p3, _, _, _ = row
        if gtype == in_type:
            return prev_id
        concat = [p1, p2, p3][prev_idx] if prev_idx < 3 else None
        current_id = prev_id
    return current_id


def _ordered_toffoli_ids_at_end(connection) -> List[int]:
    cur = connection.cursor()
    cur.execute("select id, next_q1, next_q2, next_q3 from linked_circuit where type=23")
    rows = cur.fetchall()
    if not rows:
        return []
    toffoli_ids = {r[0] for r in rows}
    next_map = {r[0]: (r[1], r[2], r[3]) for r in rows}
    # Build reverse map to find start (no predecessor that is a toffoli)
    successors = {r[0]: (r[1] // 10 if r[1] is not None else None) for r in rows}
    has_pred = {tid: False for tid in toffoli_ids}
    for tid, nxt in successors.items():
        if nxt in toffoli_ids:
            has_pred[nxt] = True
    # Choose a start with no predecessor; if multiple, pick any
    starts = [tid for tid, pred in has_pred.items() if not pred]
    if not starts:
        # Fallback: pick min id
        starts = [min(toffoli_ids)]
    ordered: List[int] = []
    current = starts[0]
    visited = set()
    while current is not None and current not in visited and current in toffoli_ids:
        visited.add(current)
        ordered.append(current)
        nqs = next_map.get(current)
        if not nqs:
            break
        candidate = nqs[0] // 10 if nqs[0] is not None else None
        if candidate in toffoli_ids:
            current = candidate
        else:
            break
    return ordered


def _cancel_adjacent_equal_triples(triples: List[tuple[int, int, int]]) -> List[tuple[int, int, int]]:
    stack: List[tuple[int, int, int]] = []
    for t in triples:
        if stack and stack[-1] == t:
            stack.pop()
        else:
            stack.append(t)
    return stack


def _count_db_toffolis_after_cancel(connection) -> Tuple[int, int]:
    # Build ordered end-chain
    ids = _ordered_toffoli_ids_at_end(connection)
    if not ids:
        return 0, 0
    triples: List[tuple[int, int, int]] = []
    for tid in ids:
        row = _fetch_gate(connection, tid)
        if row is None:
            continue
        _, _, p1, p2, p3, _, _, _ = row
        qA = _walk_to_in_gate_id(connection, tid, p1)
        qB = _walk_to_in_gate_id(connection, tid, p2)
        qC = _walk_to_in_gate_id(connection, tid, p3)
        triples.append((qA, qB, qC))
    after = _cancel_adjacent_equal_triples(triples)
    return len(triples), len(after)


def main():
    parser = argparse.ArgumentParser(description="Surface code Toffoli experiment with DB rewrites")
    parser.add_argument("--rounds", "-r", type=int, default=3, help="Number of rounds (r) to generate and process")
    args = parser.parse_args()

    r = args.rounds

    print("Connecting to Pandora DB...")
    cfg_path = os.path.join(os.path.dirname(__file__), 'default_config.json')
    connection = get_connection(config_file_path=cfg_path)

    print(f"\n--- Rounds r={r} ---")
    # Reset DB once per run (user requested empty DB per r)
    drop_and_replace_tables(connection, clean=True)
    refresh_all_stored_procedures(connection)

    stim_text = generate_stim_surface_code(distance=3, rounds=r, task="rotated_memory_x")
    blocks_circuit, first_qubits, _ = build_three_blocks_from_stim(stim_text)
    circuit = add_toffoli_to_circuit(blocks_circuit, first_qubits)

    # Insert into DB
    try:
        cur = connection.cursor()
        cur.execute("select coalesce(max(id), -1) from linked_circuit")
        (max_id,) = cur.fetchone()
        next_id = int(max_id) + 1
    except Exception:
        next_id = 0
    pandora_gates, _ = cirq_to_pandora(circuit, last_id=next_id, label=f"surface_code_toffoli_r{r}", add_margins=True)
    insert_in_batches(pandora_gates=list(pandora_gates), connection=connection, table_name='linked_circuit')

    # Apply DB rewrites until stable
    iters = apply_toffoli_rewrites_until_stable(connection)
    print(f"DB rewrites completed in {iters} sweeps.")

    # Count Toffolis at end and after cancelling adjacent identical triples
    before_cnt, after_cnt = _count_db_toffolis_after_cancel(connection)
    print(f"Toffolis at end: {before_cnt}; after cancelling repeats: {after_cnt}")


if __name__ == "__main__":
    main()


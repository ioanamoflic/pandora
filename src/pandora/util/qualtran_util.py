import sys
import time
from collections.abc import Iterable, Iterator
from typing import Any

import cirq

from qualtran import Bloq, DecomposeTypeError
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.arithmetic.addition import And
from qualtran.bloqs.basic_gates import TwoBitCSwap
from qualtran.bloqs.cryptography.rsa import RSAPhaseEstimate
from qualtran.bloqs.mod_arithmetic import CModAddK, ModAddK
from qualtran.cirq_interop import BloqAsCirqGate

from pandora.translation.translator import KEEP_RZ
from pandora.pyLIQTR.circuits.operators.AddMod import AddMod as PyLiqtrAddMod
from pandora.pyLIQTR.gate_decomp.cirq_transforms import _perop_clifford_plus_t_direct_transform
from pandora.pyLIQTR.utils.circuit_decomposition import generator_decompose


sys.setrecursionlimit(10_000_000)


BASE_GATES = (
    cirq.Rz,
    cirq.Rx,
    cirq.Ry,
    cirq.MeasurementGate,
    cirq.ResetChannel,
    cirq.GlobalPhaseGate,
    cirq.ZPowGate,
    cirq.XPowGate,
    cirq.YPowGate,
    cirq.HPowGate,
    cirq.CZPowGate,
    cirq.CXPowGate,
    cirq.ZZPowGate,
    cirq.XXPowGate,
    cirq.CCXPowGate,
    cirq.X,
    cirq.Y,
    cirq.Z,
    And,
    cirq.CSwapGate,
)

CIRQ_AND_BLOQ_GATE_SET = cirq.Gateset(
    *BASE_GATES,
    cirq.CCZPowGate,
    cirq.TOFFOLI,
    BloqAsCirqGate,
)

PANDORA_INGESTIBLE_GATE_SET = cirq.Gateset(*BASE_GATES)

PYLIQTR_GATE_SET = cirq.Gateset(
    *BASE_GATES,
    cirq.CCZPowGate,
    cirq.TOFFOLI,
)


RSA_NUMBERS = {
    64: int("18446744073709551605"),
    128: int("340282366920938463463374607431768211457"),
    256: int("115792089237316195423570985008687907853269984665640564039457584007913129639933"),
    330: int(
        "15226050279225333605356183781326374297180681149613"
        "80688657908494580122963258952897654000350692006139"
    ),
    512: int(
        "109417386415705274218097073220403576120037329454492059909138421314763499"
        "84288934784717997257891267332497625752899781833797076537244027146743531593354333897"
    ),
    576: int(
        "18819881292060796383869723946165043980716356337941738270076335642298885971523466548531"
        "9060606504743045317388011303396716199692321205734031879550656996221305168759307650257059"
    ),
    1024: int(
        "135066410865995223349603216278805969938881475605667027524485143851526510604"
        "859533833940287150571909441798207282164471551373680419703964191743046496589"
        "274256239341020864383202110372958725762358509643110564073501508187510676594"
        "629205563685529475213500852879416377328533906109750544334999811150056977236"
        "890927563"
    ),
    2048: int(
        "2519590847565789349402718324004839857142928212620403202777713783604366202070"
        "7595556264018525880784406918290641249515082189298559149176184502808489120072"
        "8449926873928072877767359714183472702618963750149718246911650776133798590957"
        "0009733045974880842840179742910064245869181719511874612151517265463228221686"
        "9987549182422433637259085141865462043576798423387184774447920739934236584823"
        "8242811981638150106748104516603773060562016196762561338441436038339044149526"
        "3443219011465754445417842402092461651572335077870774981712577246796292638635"
        "6373289912154831438167899885040445364023527381951378636564391212010397122822"
        "120720357"
    ),
}


def flatten(items: Iterable[Any]) -> Iterator[Any]:
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item


def _gate_is_inverse_composite(gate: cirq.Gate) -> bool:
    return isinstance(gate, cirq.ops.raw_types._InverseCompositeGate)


def keep_with_gate_set(op: cirq.Operation, gate_set: cirq.Gateset) -> bool:
    gate = op.without_classical_controls().gate

    if gate in gate_set:
        return True

    if _gate_is_inverse_composite(gate):
        return gate._original in gate_set

    return False


def keep(op: cirq.Operation) -> bool:
    return keep_with_gate_set(op, CIRQ_AND_BLOQ_GATE_SET)


def keep_pylam(op: cirq.Operation) -> bool:
    return keep_with_gate_set(op, PYLIQTR_GATE_SET)


def get_cirq_circuit_for_bloq(bloq: Bloq) -> cirq.Circuit:
    cirq_quregs = get_named_qubits(bloq.signature.lefts())
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs)

    context = cirq.DecompositionContext(
        qubit_manager=cirq.GreedyQubitManager(prefix="anc")
    )

    return cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))


def assert_circuit_is_decomposable(circuit: cirq.Circuit) -> None:
    bad_ops = [
        op for op in circuit.all_operations()
        if op.without_classical_controls() not in CIRQ_AND_BLOQ_GATE_SET
    ]

    assert not bad_ops, f"Found non-decomposable operations: {bad_ops[:10]}"


def assert_circuit_is_pandora_ingestible(circuit: cirq.Circuit) -> None:
    bad_ops = [
        op for op in circuit.all_operations()
        if op.without_classical_controls() not in PANDORA_INGESTIBLE_GATE_SET
    ]

    assert not bad_ops, f"Found non-Pandora-ingestible operations: {bad_ops[:10]}"


def assert_op_list_is_pandora_ingestible(op_list: list[cirq.Operation]) -> None:
    flattened_ops = list(flatten(op_list))

    bad_ops = [
        op for op in flattened_ops
        if op.without_classical_controls() not in PANDORA_INGESTIBLE_GATE_SET
    ]

    assert not bad_ops, f"Found non-Pandora-ingestible operations: {bad_ops[:10]}"


def decompose_fredkin(op: cirq.Operation) -> list[cirq.Operation]:
    ctrl, x, y = op.qubits

    return [
        cirq.CNOT(y, x),
        cirq.CNOT(ctrl, x),
        cirq.H(y),
        cirq.T(ctrl),
        cirq.T(x) ** -1,
        cirq.T(y),
        cirq.CNOT(y, x),
        cirq.CNOT(ctrl, y),
        cirq.T(x),
        cirq.CNOT(ctrl, x),
        cirq.T(y) ** -1,
        cirq.T(x) ** -1,
        cirq.CNOT(ctrl, y),
        cirq.CNOT(y, x),
        cirq.T(x),
        cirq.H(y),
        cirq.CNOT(y, x),
    ]


def bloq_to_cirq_circuit(bloq: Bloq) -> cirq.Circuit:
    cirq_quregs = get_named_qubits(bloq.signature.lefts())

    try:
        cbloq = bloq.decompose_bloq()
    except DecomposeTypeError:
        cbloq = bloq.as_composite_bloq()

    return cbloq.to_cirq_circuit(cirq_quregs=cirq_quregs)


def decompose_cmodaddk(op: cirq.Operation) -> Iterator[cirq.Operation]:
    bloq = op.gate.bloq

    add_mod_op = PyLiqtrAddMod(
        bitsize=bloq.bitsize + 1,
        add_val=bloq.k,
        mod=bloq.mod,
        cvs=(),
    ).on(*op.qubits)

    yield from generator_decompose(add_mod_op, keep=keep_pylam)


def decompose_modaddk(op: cirq.Operation) -> Iterator[cirq.Operation]:
    gate = op.gate

    add_mod_op = PyLiqtrAddMod(
        bitsize=gate.bitsize,
        add_val=gate.add_val,
        mod=gate.mod,
        cvs=gate.cvs,
    ).on(*op.qubits)

    yield from generator_decompose(add_mod_op)


def decompose_qualtran_bloq_gate(
    bloq: Bloq,
    window_size: int,
) -> Iterator[list[cirq.Operation]]:
    circuit = bloq_to_cirq_circuit(bloq)
    window_ops: list[cirq.Operation] = []

    for op in generator_decompose(circuit, keep=keep):
        if isinstance(op.gate, BloqAsCirqGate):
            if isinstance(op.gate.bloq, TwoBitCSwap):
                ctrl, x, y = op.qubits
                window_ops.append(cirq.CSWAP(ctrl, x, y))

            elif isinstance(op.gate.bloq, CModAddK):
                window_ops.extend(decompose_cmodaddk(op))

            else:
                window_ops.append(op)
        else:
            window_ops.append(op)

        if len(window_ops) >= window_size:
            yield window_ops
            window_ops = []

    if window_ops:
        yield window_ops


def get_pandora_compatible_circuit(
    circuit: cirq.Circuit,
    decompose_from_high_level: bool = True,
    window_size: int = 10_000,
) -> cirq.Circuit:
    """
    Slow, non-streaming method. Suitable for small circuits only.
    """
    if decompose_from_high_level:
        context = cirq.DecompositionContext(
            qubit_manager=cirq.SimpleQubitManager()
        )
        circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops: list[cirq.Operation] = []

    for op in circuit.all_operations():
        if isinstance(op.gate, BloqAsCirqGate):
            batches = decompose_qualtran_bloq_gate(
                op.gate.bloq,
                window_size=window_size,
            )
            final_ops.extend(flatten(batches))
        else:
            final_ops.append(op)

    return cirq.Circuit(final_ops)


def clifford_plus_t_decompose(op: cirq.Operation) -> list[cirq.Operation]:
    return _perop_clifford_plus_t_direct_transform(
        op,
        use_rotation_decomp_gates=KEEP_RZ,
        use_random_decomp=True,
        warn_if_not_decomposed=True,
    )


def get_batch(
    circuit: cirq.Circuit,
    window_size: int,
) -> Iterator[tuple[list[cirq.Operation], float]]:
    """
    Generator-based windowed decomposition into Clifford+T using pyLIQTR.
    """
    window_ops: list[cirq.Operation] = []

    for dop in generator_decompose(circuit, keep=keep):
        start_time = time.time()

        if isinstance(dop.gate, cirq.GlobalPhaseGate):
            print(f"Encountered GlobalPhaseGate with qubits={dop.qubits}")
            continue

        if isinstance(dop.gate, BloqAsCirqGate):
            batches = decompose_qualtran_bloq_gate(
                dop.gate.bloq,
                window_size=window_size,
            )
            window_ops.extend(flatten(batches))

        elif isinstance(dop.gate, ModAddK):
            for modadd_op in decompose_modaddk(dop):
                window_ops.extend(clifford_plus_t_decompose(modadd_op))

        else:
            window_ops.extend(clifford_plus_t_decompose(dop))

        if len(window_ops) >= window_size:
            window_ops = list(flatten(window_ops))
            assert_op_list_is_pandora_ingestible(window_ops)
            yield window_ops, time.time() - start_time
            window_ops = []

    if window_ops:
        start_time = time.time()
        window_ops = list(flatten(window_ops))
        assert_op_list_is_pandora_ingestible(window_ops)
        yield window_ops, time.time() - start_time


def get_RSA_batch(
    circuit: cirq.Circuit,
    window_size: int,
) -> Iterator[tuple[list[cirq.Operation], float]]:
    window_ops: list[cirq.Operation] = []

    for dop in generator_decompose(circuit, keep=keep):
        start_time = time.time()

        if isinstance(dop.gate, BloqAsCirqGate):
            for batch in decompose_qualtran_bloq_gate(
                dop.gate.bloq,
                window_size=window_size,
            ):
                window_ops.extend(batch)

                if len(window_ops) >= window_size:
                    yield window_ops, time.time() - start_time
                    window_ops = []
        else:
            window_ops.append(dop)

        if len(window_ops) >= window_size:
            yield window_ops, time.time() - start_time
            window_ops = []

    if window_ops:
        start_time = time.time()
        yield window_ops, time.time() - start_time


def get_RSA(n: int) -> cirq.Circuit:
    try:
        big_n = RSA_NUMBERS[n]
    except KeyError as exc:
        raise ValueError(f"Unsupported RSA size: {n}") from exc

    rsa_phase_estimate = RSAPhaseEstimate.make_for_shor(big_n=big_n, g=9)

    return rsa_phase_estimate.as_composite_bloq().to_cirq_circuit(
        cirq_quregs=get_named_qubits(rsa_phase_estimate.signature.lefts())
    )
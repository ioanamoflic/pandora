import sys
import time
from collections.abc import Iterable, Iterator
from typing import Callable

import cirq

from qualtran import Bloq, DecomposeTypeError
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.arithmetic.addition import And
from qualtran.bloqs.basic_gates import TwoBitCSwap
from qualtran.bloqs.cryptography.rsa import RSAPhaseEstimate
from qualtran.bloqs.mod_arithmetic import CModAddK, ModAddK
from qualtran.cirq_interop import BloqAsCirqGate

from pyLIQTR.circuits.operators.AddMod import AddMod as PyLIQTRAddMod
from pyLIQTR.gate_decomp.cirq_transforms import _perop_clifford_plus_t_direct_transform
from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pandora.translation.translator import KEEP_RZ


sys.setrecursionlimit(10_000_000)


AT_MOST_TWO_QUBIT = cirq.Gateset(
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
    cirq.X,
    cirq.Y,
    cirq.Z,
)

AT_MOST_THREE_QUBIT = cirq.Gateset(
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
    cirq.CCZPowGate,
    cirq.TOFFOLI,
    cirq.X,
    cirq.Y,
    cirq.Z,
    And,
    cirq.CSwapGate,
)


def flatten(items: Iterable) -> Iterator:
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item


def _base_gate(op: cirq.Operation):
    return op.without_classical_controls().gate


def _make_keep_predicate(gate_set: cirq.Gateset) -> Callable[[cirq.Operation], bool]:
    def keep_fn(op: cirq.Operation) -> bool:
        gate = _base_gate(op)
        if gate in gate_set:
            return True

        if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
            return gate._original in gate_set

        return False

    return keep_fn


keep_two_qubit_gates = _make_keep_predicate(AT_MOST_TWO_QUBIT)
keep_three_qubit_gates = _make_keep_predicate(AT_MOST_THREE_QUBIT)


def _assert_ops_in_gate_set(ops: Iterable[cirq.Operation], gate_set: cirq.Gateset) -> None:
    bad = []
    for op in ops:
        if op.without_classical_controls() not in gate_set:
            bad.append(op.without_classical_controls().gate)

    if bad:
        for gate in bad:
            print(gate)
        raise AssertionError("Found operations outside target gate set.")


def assert_circuit_is_decomposable(circuit: cirq.Circuit) -> None:
    _assert_ops_in_gate_set(circuit.all_operations(), AT_MOST_TWO_QUBIT)


def assert_circuit_is_pandora_ingestible(circuit: cirq.Circuit) -> None:
    _assert_ops_in_gate_set(circuit.all_operations(), AT_MOST_THREE_QUBIT)


def assert_op_list_is_pandora_ingestible(op_list: list[cirq.Operation]) -> None:
    _assert_ops_in_gate_set(op_list, AT_MOST_THREE_QUBIT)


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


def _decompose_bloq_to_circuit(bloq: Bloq) -> cirq.Circuit:
    cirq_quregs = get_named_qubits(bloq.signature.lefts())
    try:
        return bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs).unfreeze()
    except DecomposeTypeError:
        return bloq.as_composite_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs).unfreeze()


def get_cirq_circuit_for_bloq(bloq: Bloq) -> cirq.Circuit:
    circuit = _decompose_bloq_to_circuit(bloq)
    context = cirq.DecompositionContext(
        qubit_manager=cirq.GreedyQubitManager(prefix="anc")
    )
    return cirq.Circuit(cirq.decompose(circuit, keep=keep_two_qubit_gates, context=context))


def _expand_cmodaddk(op: cirq.Operation) -> list[cirq.Operation]:
    bloq = op.gate.bloq
    top = PyLIQTRAddMod(
        bitsize=bloq.bitsize + 1,
        add_val=bloq.k,
        mod=bloq.mod,
        cvs=(),
    ).on(*op.qubits)
    return list(generator_decompose(top, keep=keep_three_qubit_gates))


def _expand_modaddk(op: cirq.Operation) -> list[cirq.Operation]:
    top = PyLIQTRAddMod(
        bitsize=op.gate.bitsize,
        add_val=op.gate.add_val,
        mod=op.gate.mod,
        cvs=op.gate.cvs,
    ).on(*op.qubits)

    expanded: list[cirq.Operation] = []
    for decomposed in generator_decompose(top):
        expanded.extend(
            _perop_clifford_plus_t_direct_transform(
                decomposed,
                use_rotation_decomp_gates=KEEP_RZ,
                use_random_decomp=True,
                warn_if_not_decomposed=True,
            )
        )
    return expanded


def _expand_regular_op(op: cirq.Operation) -> list[cirq.Operation]:
    return list(
        _perop_clifford_plus_t_direct_transform(
            op,
            use_rotation_decomp_gates=KEEP_RZ,
            use_random_decomp=True,
            warn_if_not_decomposed=True,
        )
    )


def decompose_qualtran_bloq_gate(
    bloq: Bloq,
    window_size: int,
) -> Iterator[list[cirq.Operation]]:
    circuit = _decompose_bloq_to_circuit(bloq)
    window_ops: list[cirq.Operation] = []

    for op in generator_decompose(circuit, keep=keep_two_qubit_gates):
        if isinstance(op.gate, BloqAsCirqGate):
            if isinstance(op.gate.bloq, TwoBitCSwap):
                ctrl, x, y = op.qubits
                window_ops.append(cirq.CSWAP.on(ctrl, x, y))
            elif isinstance(op.gate.bloq, CModAddK):
                window_ops.extend(_expand_cmodaddk(op))
            else:
                window_ops.append(op)
        else:
            window_ops.append(op)

        if len(window_ops) >= window_size:
            yield window_ops
            window_ops = []

    if window_ops:
        yield window_ops


def _expand_for_pandora(op: cirq.Operation, window_size: int) -> list[cirq.Operation]:
    if isinstance(op.gate, cirq.GlobalPhaseGate):
        print(f"Encountered GlobalPhaseGate with qubits = {op.qubits}")
        return []

    if isinstance(op.gate, BloqAsCirqGate):
        return list(flatten(decompose_qualtran_bloq_gate(op.gate.bloq, window_size)))

    if isinstance(op.gate, ModAddK):
        return _expand_modaddk(op)

    return _expand_regular_op(op)


def _expand_for_rsa(op: cirq.Operation, window_size: int) -> list[cirq.Operation]:
    if isinstance(op.gate, BloqAsCirqGate):
        return list(flatten(decompose_qualtran_bloq_gate(op.gate.bloq, window_size)))
    return [op]


def get_pandora_compatible_circuit(
    circuit: cirq.Circuit,
    decompose_from_high_level: bool = True,
) -> cirq.Circuit:
    """
    Slow path for small circuits.
    """
    if decompose_from_high_level:
        context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
        circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep_two_qubit_gates, context=context))

    final_ops: list[cirq.Operation] = []
    for op in circuit.all_operations():
        if isinstance(op.gate, BloqAsCirqGate):
            final_ops.extend(flatten(decompose_qualtran_bloq_gate(op.gate.bloq, sys.maxsize)))
        else:
            final_ops.append(op)

    return cirq.Circuit(final_ops)


def _yield_windowed_ops(
    source_ops: Iterable[cirq.Operation],
    window_size: int,
    expand_fn: Callable[[cirq.Operation, int], list[cirq.Operation]],
    validate: bool,
) -> Iterator[tuple[list[cirq.Operation], float]]:
    window_ops: list[cirq.Operation] = []
    batch_start = time.time()

    for op in source_ops:
        window_ops.extend(expand_fn(op, window_size))

        if len(window_ops) >= window_size:
            batch = list(flatten(window_ops))
            if validate:
                assert_op_list_is_pandora_ingestible(batch)
            yield batch, time.time() - batch_start
            window_ops = []
            batch_start = time.time()

    if window_ops:
        batch = list(flatten(window_ops))
        if validate:
            assert_op_list_is_pandora_ingestible(batch)
        yield batch, time.time() - batch_start


def get_batch(
    circuit: cirq.Circuit,
    window_size: int,
) -> Iterator[tuple[list[cirq.Operation], float]]:
    return _yield_windowed_ops(
        source_ops=generator_decompose(circuit, keep=keep_two_qubit_gates),
        window_size=window_size,
        expand_fn=_expand_for_pandora,
        validate=True,
    )


def get_RSA_batch(
    circuit: cirq.Circuit,
    window_size: int,
) -> Iterator[tuple[list[cirq.Operation], float]]:
    return _yield_windowed_ops(
        source_ops=generator_decompose(circuit, keep=keep_two_qubit_gates),
        window_size=window_size,
        expand_fn=_expand_for_rsa,
        validate=False,
    )


def get_RSA(n):
    if n == 64:
        big_n = int("18446744073709551605")

    elif n == 128:
        big_n = int("340282366920938463463374607431768211457")

    elif n == 256:
        big_n = int("115792089237316195423570985008687907853269984665640564039457584007913129639933")

    elif n == 330:
        big_n = int("15226050279225333605356183781326374297180681149613"
                    "80688657908494580122963258952897654000350692006139")
    elif n == 512:
        big_n = int("109417386415705274218097073220403576120037329454492059909138421314763499"
                    "84288934784717997257891267332497625752899781833797076537244027146743531593354333897")
    elif n == 576:
        big_n = int("18819881292060796383869723946165043980716356337941738270076335642298885971523466548531"
                    "9060606504743045317388011303396716199692321205734031879550656996221305168759307650257059")
    elif n == 1024:
        big_n = int("135066410865995223349603216278805969938881475605667027524485143851526510604"
                    "859533833940287150571909441798207282164471551373680419703964191743046496589"
                    "274256239341020864383202110372958725762358509643110564073501508187510676594"
                    "629205563685529475213500852879416377328533906109750544334999811150056977236"
                    "890927563")
    elif n == 2048:
        big_n = int("2519590847565789349402718324004839857142928212620403202777713783604366202070"
                    "7595556264018525880784406918290641249515082189298559149176184502808489120072"
                    "8449926873928072877767359714183472702618963750149718246911650776133798590957"
                    "0009733045974880842840179742910064245869181719511874612151517265463228221686"
                    "9987549182422433637259085141865462043576798423387184774447920739934236584823"
                    "8242811981638150106748104516603773060562016196762561338441436038339044149526"
                    "3443219011465754445417842402092461651572335077870774981712577246796292638635"
                    "6373289912154831438167899885040445364023527381951378636564391212010397122822"
                    "120720357")
    else:
        raise Exception("Requested n not here.")

    rsa_pe_small = RSAPhaseEstimate.make_for_shor(big_n=big_n, g=9)
    circuit = rsa_pe_small.as_composite_bloq() \
        .to_cirq_circuit(cirq_quregs=get_named_qubits(rsa_pe_small.signature.lefts()))

    return circuit

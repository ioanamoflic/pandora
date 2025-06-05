import time
from typing import Iterator

import cirq
import sys

from qualtran import Bloq, DecomposeTypeError
from qualtran.bloqs.mod_arithmetic import ModAddK, CModAddK
from qualtran.bloqs.arithmetic.addition import Add, And
from qualtran.bloqs.basic_gates import CNOT, TwoBitCSwap, XGate, CZ
from qualtran.cirq_interop import BloqAsCirqGate
from qualtran._infra.gate_with_registers import get_named_qubits
from qualtran.bloqs.cryptography.rsa import RSAPhaseEstimate

from pyLIQTR.circuits.operators.AddMod import AddMod as pyLAM

from pyLIQTR.gate_decomp.cirq_transforms import _perop_clifford_plus_t_direct_transform

from pyLIQTR.utils.circuit_decomposition import generator_decompose

from pandora.cirq_to_pandora_util import windowed_cirq_to_pandora_from_op_list
from pandora.exceptions import WindowSizeError
from pandora.gate_translator import In, Out, SINGLE_QUBIT_GATES, TWO_QUBIT_GATES, KEEP_RZ
from pandora.gates import PandoraGate

sys.setrecursionlimit(10000000)
# Increase recursion limit from default since adder bloq has a recursive implementation.

cirq_and_bloq_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry,
    cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate,
    cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate,
    cirq.ZZPowGate, cirq.XXPowGate,
    cirq.CCXPowGate, cirq.CCZPowGate, cirq.TOFFOLI,
    cirq.X, cirq.Y, cirq.Z,
    And,
    BloqAsCirqGate,
    cirq.CSwapGate)

pandora_ingestible_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry, cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate, cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate, cirq.ZZPowGate, cirq.XXPowGate, cirq.CCXPowGate,
    And,
    cirq.CSwapGate,
    cirq.X, cirq.Y, cirq.Z,
)

pylam_gate_set = cirq.Gateset(
    cirq.Rz, cirq.Rx, cirq.Ry,
    cirq.MeasurementGate, cirq.ResetChannel,
    cirq.GlobalPhaseGate,
    cirq.ZPowGate, cirq.XPowGate, cirq.YPowGate, cirq.HPowGate,
    cirq.CZPowGate, cirq.CXPowGate,
    cirq.ZZPowGate, cirq.XXPowGate,
    cirq.CCXPowGate, cirq.CCZPowGate, cirq.TOFFOLI,
    cirq.X, cirq.Y, cirq.Z,
    And,
    cirq.CSwapGate)


def flatten(nested: list):
    for i in nested:
        if isinstance(i, list):
            for j in flatten(i):
                yield j
        else:
            yield i


def keep(op: cirq.Operation):
    gate = op.without_classical_controls().gate
    ret = gate in cirq_and_bloq_gate_set
    if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
        ret |= op.gate._original in cirq_and_bloq_gate_set
    return ret


def keep_pylam(op: cirq.Operation):
    gate = op.without_classical_controls().gate
    ret = gate in pylam_gate_set
    if isinstance(gate, cirq.ops.raw_types._InverseCompositeGate):
        ret |= op.gate._original in pylam_gate_set
    return ret


def get_cirq_circuit_for_bloq(bloq: Bloq):
    # Get a cirq circuit containing only this operation.
    circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=get_named_qubits(bloq.signature.lefts()))
    # Decompose the operation until all gates are in the target gate set.
    context = cirq.DecompositionContext(qubit_manager=cirq.GreedyQubitManager(prefix='anc'))
    return cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))


def assert_circuit_is_decomposable(circuit: cirq.Circuit):
    # Assert that all operations in the decomposed circuit are part of the target gate set.
    assert all(op.without_classical_controls() in cirq_and_bloq_gate_set for op in circuit.all_operations())


def assert_circuit_is_pandora_ingestible(circuit: cirq.Circuit):
    # Assert that all operations in the decomposed circuit are part of the target gate set.
    for op in circuit.all_operations():
        if op.without_classical_controls() not in pandora_ingestible_gate_set:
            print(op.without_classical_controls().gate)
    assert all(op.without_classical_controls() in pandora_ingestible_gate_set for op in circuit.all_operations())


def assert_op_list_is_pandora_ingestible(op_list: list):
    # Assert that all operations are part of the target gate set.
    for op in op_list:
        if isinstance(op, list):
            op = op[0]
        if op.without_classical_controls() not in pandora_ingestible_gate_set:
            print(op.without_classical_controls().gate)
    assert all(op.without_classical_controls() in pandora_ingestible_gate_set for op in op_list)


def decompose_fredkin(op: cirq.Operation):
    ops = []
    ctrl, x, y = op.qubits
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.CNOT(ctrl, x), cirq.H(y)]
    ops += [cirq.T(ctrl), cirq.T(x) ** -1, cirq.T(y)]
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.CNOT(ctrl, y), cirq.T(x)]
    ops += [cirq.CNOT(ctrl, x), cirq.T(y) ** -1]
    ops += [cirq.T(x) ** -1, cirq.CNOT(ctrl, y)]
    ops += [cirq.CNOT(y, x)]
    ops += [cirq.T(x), cirq.H(y)]
    ops += [cirq.CNOT(y, x)]
    return ops


def decompose_qualtran_bloq_gate(bloq: Bloq, window_size: int):
    cirq_quregs = get_named_qubits(bloq.signature.lefts())
    try:
        circuit = bloq.decompose_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs)
    except DecomposeTypeError:
        # there could be a specific error for atomic ops?
        circuit = bloq.as_composite_bloq().to_cirq_circuit(cirq_quregs=cirq_quregs)

    window_ops = []
    for op in generator_decompose(circuit, keep=keep):
        if isinstance(op.gate, BloqAsCirqGate):
            if isinstance(op.gate.bloq, TwoBitCSwap):
                ctrl, x, y = op.qubits
                window_ops.append(cirq.CSWAP.on(ctrl, x, y))
            elif isinstance(op.gate.bloq, CModAddK):
                top = pyLAM(bitsize=op.gate.bloq.bitsize + 1,
                            add_val=op.gate.bloq.k,
                            mod=op.gate.bloq.mod,
                            cvs=()).on(*op.qubits)
                for d_top in generator_decompose(top, keep=keep_pylam):
                    window_ops.append(d_top)
            else:
                window_ops.append(op)
        else:
            window_ops.append(op)

        if len(window_ops) >= window_size:
            yield window_ops
            window_ops.clear()

    if len(window_ops) > 0:
        yield window_ops
        window_ops.clear()


def get_pandora_compatible_circuit(circuit: cirq.Circuit, decompose_from_high_level=True) -> cirq.Circuit:
    """
    Takes a Cirq circuit as input and outputs a logically equivalent circuit with operations acting on at most three
    qubits which can be ingested into Pandora.

    This is the SLOW method. For small circuits only.
    """
    if decompose_from_high_level:
        context = cirq.DecompositionContext(qubit_manager=cirq.SimpleQubitManager())
        circuit = cirq.Circuit(cirq.decompose(circuit, keep=keep, context=context))

    final_ops = []
    for op in circuit.all_operations():
        if isinstance(op.gate, BloqAsCirqGate):
            atomic_ops = list(decompose_qualtran_bloq_gate(op.gate.bloq))
            final_ops = final_ops + atomic_ops
        else:
            final_ops.append(op)

    decomposed_circuit = cirq.Circuit(final_ops)
    return decomposed_circuit


def generator_get_pandora_compatible_batch_via_pyliqtr(circuit: cirq.Circuit,
                                                       window_size: int) -> Iterator[list[cirq.Operation]]:
    """
    This is a generator-based (windowed) decomposition into Clifford+T build on top of pyLIQTR's generator
    decomposition method. The method yields a batch of window_size elements.
    Args:
        circuit: the high-level cirq circuit
        window_size: size of the window

    Returns:
        Generator over the tuples consisting of the cirq operations contained in the batch.
    """
    window_ops = []

    for dop in generator_decompose(circuit, keep=keep):
        start_dop = time.time()
        if isinstance(dop.gate, cirq.GlobalPhaseGate):
            print(f'Encountered GlobalPhaseGate with qubits = {dop.qubits}')
            pass
        elif isinstance(dop.gate, BloqAsCirqGate):
            atomic_ops = decompose_qualtran_bloq_gate(dop.gate.bloq)
            window_ops.extend(atomic_ops)
        elif isinstance(dop.gate, ModAddK):
            top = pyLAM(bitsize=dop.gate.bitsize,
                        add_val=dop.gate.add_val,
                        mod=dop.gate.mod,
                        cvs=dop.gate.cvs).on(*dop.qubits)
            for d_top in generator_decompose(top):
                atomic_ops = _perop_clifford_plus_t_direct_transform(d_top,
                                                                     use_rotation_decomp_gates=KEEP_RZ,
                                                                     use_random_decomp=True,
                                                                     warn_if_not_decomposed=True)
                window_ops.extend(atomic_ops)
        else:
            atomic_ops = _perop_clifford_plus_t_direct_transform(dop,
                                                                 use_rotation_decomp_gates=KEEP_RZ,
                                                                 use_random_decomp=True,
                                                                 warn_if_not_decomposed=True)
            window_ops.extend(atomic_ops)

        if len(window_ops) >= window_size:
            window_ops = list(flatten(window_ops))
            assert_op_list_is_pandora_ingestible(window_ops)
            yield window_ops, time.time() - start_dop
            window_ops.clear()

    start_last = time.time()
    if len(window_ops) > 0:
        window_ops = list(flatten(window_ops))
        assert_op_list_is_pandora_ingestible(window_ops)
        yield window_ops, time.time() - start_last


def generator_get_RSA_compatible_batch(circuit: cirq.Circuit,
                                       window_size: int) -> Iterator[list[cirq.Operation]]:
    window_ops = []

    for dop in generator_decompose(circuit, keep=keep):
        start_dop = time.time()
        if isinstance(dop.gate, BloqAsCirqGate):
            window_batches = decompose_qualtran_bloq_gate(dop.gate.bloq, window_size=window_size)

            for window_batch in window_batches:
                window_ops.extend(window_batch)

                if len(window_ops) >= window_size:
                    yield window_ops, time.time() - start_dop
                    window_ops.clear()
        else:
            window_ops.append(dop)

        if len(window_ops) >= window_size:
            yield window_ops, time.time() - start_dop
            window_ops.clear()

    start_last = time.time()
    if len(window_ops) > 0:
        yield window_ops, time.time() - start_last


def windowed_cirq_to_pandora(circuit: cirq.Circuit | Bloq, window_size: int, is_test: bool = False) \
        -> Iterator[tuple[list[PandoraGate], float]]:
    """
    This method traverses a cirq circuit in windows of arbitrary size and returns the PandoraGate operations equivalent
    to the cirq operations in the window. Especially useful for very large circuits which do not fit into memory. The
    list of qubits in the resulting circuit will be a permutation fo the original one.
    Args:
        is_test: boolean which takes qubit ordering into account during testing for 1:1 reconstruction.
        circuit: the high-level cirq circuit
        window_size: the size of each decomposition window
    Returns:
        Generator over the PandoraGate objects of each batch.
    """
    if window_size <= 1:
        raise WindowSizeError

    qubit_set = set()
    pandora_dictionary = dict()
    latest_conc_on_qubit = dict()
    last_id = 0

    batches = generator_get_pandora_compatible_batch_via_pyliqtr(circuit=circuit,
                                                                 window_size=window_size)
    for i, (current_batch, cliff_decomp_time) in enumerate(batches):
        for op in current_batch:
            qubit_set.update(set(list(op.qubits)))

        start_cirq_to_pandora = time.time()
        # the idea is to add anything that is not null on "next link" from the pandora gates dictionary
        pandora_dictionary, latest_conc_on_qubit, last_id = windowed_cirq_to_pandora_from_op_list(
            op_list=current_batch,
            pandora_dictionary=pandora_dictionary,
            latest_conc_on_qubit=latest_conc_on_qubit,
            last_id=last_id,
            label='x',
            is_test=is_test
        )
        dictionary_copy = pandora_dictionary.copy()
        batch_elements: list[PandoraGate] = []
        for pandora_gate in dictionary_copy.values():
            if (pandora_gate.type in SINGLE_QUBIT_GATES
                and pandora_gate.next_q1 is not None) \
                    or (pandora_gate.type in TWO_QUBIT_GATES
                        and pandora_gate.next_q1 is not None
                        and pandora_gate.next_q2 is not None):
                batch_elements.append(pandora_gate)
                pandora_dictionary.pop(pandora_gate.id)

        yield batch_elements, time.time() - start_cirq_to_pandora + cliff_decomp_time

    start_final = time.time()
    final_batch: list[cirq.Operation] = [Out().on(q) for q in qubit_set]
    pandora_out_gates, _, _ = windowed_cirq_to_pandora_from_op_list(
        op_list=final_batch,
        pandora_dictionary=pandora_dictionary,
        latest_conc_on_qubit=latest_conc_on_qubit,
        last_id=last_id,
        label='x',
        is_test=is_test)
    yield list(pandora_out_gates.values()), time.time() - start_final


def get_RSA(n):
    print(n)
    if n == 100:
        big_n = int("15226050279225333605356183781326374297180681149613"
                    "80688657908494580122963258952897654000350692006139")
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
        raise f"Requested {n} not here."

    rsa_pe_small = RSAPhaseEstimate.make_for_shor(big_n=big_n, g=9)
    circuit = rsa_pe_small.as_composite_bloq() \
        .to_cirq_circuit(cirq_quregs=get_named_qubits(rsa_pe_small.signature.lefts()))

    return circuit

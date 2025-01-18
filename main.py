import sys
import time

from pyLIQTR.BlockEncodings import VALID_ENCODINGS
from pyLIQTR.BlockEncodings.getEncoding import getEncoding
from pyLIQTR.ProblemInstances.getInstance import getInstance
from pyLIQTR.clam.lattice_definitions import SquareLattice

from pandora import Pandora, PandoraConfig
from pandora.qualtran_to_pandora_util import assert_circuit_is_pandora_ingestible, \
    get_pandora_compatible_circuit_via_pyliqtr, get_pandora_compatible_circuit

if __name__ == "__main__":

    if len(sys.argv) == 1:
        print("!!!")
        sys.exit(0)

    next_arg = 1

    config = PandoraConfig()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith(".json"):
            config.update_from_file(sys.argv[1])
            next_arg = 2

    sys.stdout.flush()

    pandora = Pandora(pandora_config=config, max_time=3600)

    sys.stdout.flush()

    import os
    hrl_data_path = os.path.abspath("./circuitsharing")

    # this needs multiple virtual machines, each with its own main call
    if sys.argv[next_arg] == "adder":
        n_bits = int(sys.argv[next_arg + 1])
        pandora.build_qualtran_adder(n_bits)
    elif sys.argv[next_arg] == "hub2d":
        N = int(sys.argv[next_arg + 1])
        J = -1.0
        U = 4.0
        shape = (N, N)
        model = getInstance('FermiHubbard', shape=shape, J=J, U=U, cell=SquareLattice)
        block_encoding = getEncoding(VALID_ENCODINGS.FermiHubbardSquare)(model)
        circuit = block_encoding.circuit

        start = time.time()
        final_cirq = get_pandora_compatible_circuit(circuit=circuit, decompose_from_high_level=True)
        print(f'Time to decompose circuit {time.time() - start}')
        assert_circuit_is_pandora_ingestible(final_cirq)
        print(f'Number of operations: {len(list(final_cirq.all_operations()))}')
    elif sys.argv[next_arg] == "fh":
        N = int(sys.argv[next_arg + 1])
        pandora.build_fh_circuit(N=N, p_algo=0.9999999904, times=0.01)
        pandora.populate_layered()
    elif sys.argv[next_arg] == "mg":
        pandora.build_mg_coating_walk_op(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "o3":
        pandora.build_cyclic_o3(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "hc":
        pandora.build_hc_circuit(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "ising":
        N = int(sys.argv[next_arg + 1])
        pandora.build_traverse_ising(N=N)

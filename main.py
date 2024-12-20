import sys

from pandora import Pandora

if __name__ == "__main__":

    if len(sys.argv) == 1:
        sys.exit(0)

    pandora = Pandora(max_time=3600)

    import os
    hrl_data_path = os.path.abspath("./circuitsharing")

    # this needs multiple virtual machines, each with its own main call
    if sys.argv[1] == "adder":
        n_bits = int(sys.argv[2])
        pandora.build_qualtran_adder(n_bits)
    if sys.argv[1] == "fh":
        N = int(sys.argv[2])
        pandora.build_fh_circuit(N=N)
    if sys.argv[1] == "mg":
        pandora.build_mg_coating_walk_op(data_path=hrl_data_path)
    if sys.argv[1] == "o3":
        pandora.build_cyclic_o3()
    if sys.argv[1] == "hc":
        pandora.build_hc_circuit()
    if sys.argv[1] == "ising":
        N = int(sys.argv[2])
        pandora.build_traverse_ising(N=N)

import sys
import os
import time

from pandora import Pandora, PandoraConfig
from pandora.widgetization.union_find import UnionFindWidgetizer

if __name__ == "__main__":

    if len(sys.argv) == 1:
        sys.exit(0)

    next_arg = 1

    config = PandoraConfig()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith(".json"):
            config.update_from_file(sys.argv[1])
            next_arg = 2

    pandora = Pandora(pandora_config=config,
                      max_time=3600,
                      decomposition_window_size=1000000)

    hrl_data_path = os.path.abspath(".")

    if sys.argv[next_arg] == "adder":
        n_bits = int(sys.argv[next_arg + 1])
        pandora.build_qualtran_adder(n_bits)
    elif sys.argv[next_arg] == "qrom":
        n_bits = int(sys.argv[next_arg + 1])
    elif sys.argv[next_arg] == "qpe":
        num_sites = int(sys.argv[next_arg + 1])
        pandora.build_qualtran_qpe(num_sites)
    elif sys.argv[next_arg] == "hubbard":
        N = int(sys.argv[next_arg + 1])
        pandora.build_qualtran_hubbard_2d(dim=(N, N))
    elif sys.argv[next_arg] == "fh":
        N = int(sys.argv[next_arg + 1])
        pandora.build_fh_circuit(N=N, p_algo=0.9999999904, times=0.01)
        # pandora.widgetize(max_t=10, max_d=100, fh_N=N)
    elif sys.argv[next_arg] == "mg":
        pandora.build_mg_coating_walk_op(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "o3":
        pandora.build_cyclic_o3(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "hc":
        pandora.build_hc_circuit(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "ising":
        N = int(sys.argv[next_arg + 1])
        pandora.build_traverse_ising(N=N)
    elif sys.argv[next_arg] == "example":
        pandora.build_example()

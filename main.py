import sys

from pandora import Pandora, PandoraConfig

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
    elif sys.argv[next_arg] == "fh":
        N = int(sys.argv[next_arg + 1])
        pandora.build_fh_circuit(N=N)
    elif sys.argv[next_arg] == "mg":
        pandora.build_mg_coating_walk_op(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "o3":
        pandora.build_cyclic_o3(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "hc":
        pandora.build_hc_circuit(data_path=hrl_data_path)
    elif sys.argv[next_arg] == "ising":
        N = int(sys.argv[next_arg + 1])
        pandora.build_traverse_ising(N=N)

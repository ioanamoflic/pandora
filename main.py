import sys
import os

from pandora import PandoraConfig, Pandora

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

    # only FH for now
    if sys.argv[next_arg] == "fh":
        N = int(sys.argv[next_arg + 1])
        NPROC = int(sys.argv[next_arg + 2])
        print(f"Starting FH {N}x{N} with {NPROC} processes.")
        abs_path = os.path.abspath(sys.argv[1])
        pandora.build_circuit_in_parallel(nprocs=NPROC,
                                          N=N,
                                          config_file_path=abs_path,
                                          window_size=10000,
                                          conn_lifetime=120)
    elif sys.argv[next_arg] == 'rsa':
        NPROC = int(sys.argv[next_arg + 1])
        CONTAINER_ID = int(sys.argv[next_arg + 2])
        print(f"Starting RSA with {NPROC} processes.")
        # abs_path = os.path.abspath(sys.argv[1])
        abs_path = None
        n_containers = 11
        pandora.build_circuit_in_parallel(nprocs=NPROC,
                                          container_id=CONTAINER_ID,
                                          n_containers=n_containers,
                                          N=None,
                                          config_file_path=abs_path,
                                          window_size=10000,
                                          conn_lifetime=120)

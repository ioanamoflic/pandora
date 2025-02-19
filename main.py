'''
    Example startup script for Pandora
'''

import sys
import os

import cirq
import pyLIQTR

from pandora import Pandora, PandoraConfig
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pandora.targeted_decomposition import find_target_gate, \
    chain_decompose_multi, add_cache_db

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

    # Example
    print("Initialising circuit")
    circuit = make_fh_circuit(N=10, p_algo=0.9999999904, times=0.01)
    print("initialised circuit")

    moment = iter(circuit)
    qsvt = next(iter(next(moment)))

    circuit = cirq.Circuit()
    circuit.append(qsvt)

    DECOMP_LEVEL = 4
    decomposed_circuit = chain_decompose_multi(
        circuit,
        DECOMP_LEVEL
    )
    target = find_target_gate(
        decomposed_circuit,
        pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU
    )

    # Add a new table for this gate
    conn = add_cache_db(pandora, target, 'lcu')

    #  # Example widgetisation
    #  widgets = conn.widgetize(max_t=10,
    #  max_d=100,
    #  batch_size=100,
    #  add_gin_per_widget=True)
    #  for widget in widgets:
    #      print(widget)

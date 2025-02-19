import sys
import os

from pandora import Pandora, PandoraConfig
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pandora.targeted_decomposition import collect_gates, find_target_gate, chain_decompose_multi, add_cache_db
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
import qualtran

import cirq
import pyLIQTR

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


    def find_target_gate(dec, target):
        for i in iter(dec):
            for j in iter(i):
                print(j.gate.__class__)
                if isinstance(j.gate, target):
                    print(f"Found: {j.gate.__class__}")
                    return j
        print("Failed to find target")
        raise Exception

    decomp_level = 4
    decomposed_circuit = chain_decompose_multi(circuit, decomp_level)  
    target = find_target_gate(decomposed_circuit, pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU)
    print(target)

    # Add a new table for this gate
    lcu_conn = add_cache_db(pandora, target, 'lcu')

    #widgets = pandora.widgetize(max_t=10, max_d=100, batch_size=100, add_gin_per_widget=True)
    #for widget in widgets:
    #    print(widget)

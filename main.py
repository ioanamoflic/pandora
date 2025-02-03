import sys
import os

from pandora import Pandora, PandoraConfig
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
import qualtran
    
import cirq
import pyLIQTR
from qualtran._infra.adjoint import Adjoint

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

   

    def add_cache_db(circuit, decomp, target, db_name):
        print("Starting decomp")
        dec = circuit_decompose_multi(circuit, decomp)  
        print("Finished decomp, searching")

        target = Adjoint  

        gate = find_target_gate(dec, target)
        decomp_circuit = cirq.Circuit()
        decomp_circuit.append(gate)

        conn = pandora.spawn(db_name)
        conn.build_pyliqtr_circuit(pyliqtr_circuit=decomp_circuit)

    add_cache_db(circuit, 3, Adjoint, 'adjoint')
    add_cache_db(circuit, 3, pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU, 'lcu')

    #widgets = pandora.widgetize(max_t=10, max_d=100, batch_size=100, add_gin_per_widget=True)
    #for widget in widgets:
    #    print(widget)

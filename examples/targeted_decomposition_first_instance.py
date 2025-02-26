from pandora.targeted_decomposition import collect_gates, find_target_gate, chain_decompose_multi 
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
    
import pyLIQTR

# Example
# We will be collecting all adjoint gates and PauliStringLCU gates

circuit = make_fh_circuit(N=10, p_algo=0.9999999904, times=0.01)

decomp_level = 4
decomposed_circuit = chain_decompose_multi(circuit, decomp_level)  

target = find_target_gate(decomposed_circuit, pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU)
print(target)

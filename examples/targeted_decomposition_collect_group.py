from pandora.targeted_decomposition import collect_gates
from pandora.pyliqtr_to_pandora_util import make_fh_circuit
from pyLIQTR.utils.circuit_decomposition import circuit_decompose_multi
import qualtran
    
import cirq
import pyLIQTR
from qualtran._infra.adjoint import Adjoint

# Example
# We will be collecting all adjoint gates and PauliStringLCU gates
targets = [Adjoint, pyLIQTR.BlockEncodings.PauliStringLCU.PauliStringLCU]

circuit = make_fh_circuit(N=10, p_algo=0.9999999904, times=0.01)
collected_gates = collect_gates(circuit, targets, 3)
print(collected_gates)

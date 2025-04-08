from monkey_patching.lazy_load import *

from pandora.pyliqtr_to_pandora_util import make_fh_circuit

from pyLIQTR.utils.circuit_decomposition import generator_decompose

print("Trying to build FH circuit, this should first lazily instantiate QSVT_real_polynomial")
proc_circuit = make_fh_circuit(N=2, p_algo=0.9999999904, times=0.01)

for dop in generator_decompose(proc_circuit, max_decomposition_passes=2):
    print(dop.__class__.__name__)

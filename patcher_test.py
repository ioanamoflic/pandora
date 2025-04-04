import pyLIQTR.qubitization.qsvt
from monkey_patching.lazy_load import lazy_QSVT_real_polynomial
pyLIQTR.qubitization.qsvt.QSVT_real_polynomial = lazy_QSVT_real_polynomial


from pandora.pyliqtr_to_pandora_util import make_fh_circuit

print("Trying to build FH circuit, this should first lazily instantiate QSVT_real_polynomial")
proc_circuit = make_fh_circuit(N=2, p_algo=0.9999999904, times=0.01)



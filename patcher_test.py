from pyLIQTR.BlockEncodings import VALID_ENCODINGS
from pyLIQTR.BlockEncodings.getEncoding import getEncoding
from pyLIQTR.ProblemInstances.getInstance import getInstance
from pyLIQTR.clam.lattice_definitions import SquareLattice
from pyLIQTR.qubitization.qsvt_dynamics import simulation_phases

from monkey_patching.lazy_load import *

# monkey-patch
print("Monkey-patching")
QSVT_real_polynomial = lambda *args, **kwargs: LazyProxy(*args, **kwargs)

p_algo = 0.95
times = 0.1
J = -1.0
U = 2.0
N = 2
eps = (1 - p_algo) / 2
model = getInstance("FermiHubbard", shape=(N, N), J=J, U=U, cell=SquareLattice)
scaled_times = times * model.alpha
phases = simulation_phases(times=scaled_times, eps=eps, precompute=False, phase_algorithm="random")

# this should not call the constructor of GateOperation
print("Declaring obj, not yet instantiating")
bloq = QSVT_real_polynomial(block_encoding=getEncoding(VALID_ENCODINGS.PauliLCU),
                            instance=model,
                            phis=phases[0])
# the constructor is called now
print("Accessing member of QSVT_real_polynomial")
print(bloq.decompose_from_registers(context=None))

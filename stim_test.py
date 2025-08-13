import stim
from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

prob = 0.001
circuit = stim.Circuit.generated(
    "color_code:memory_xyz",
    distance=7,
    rounds=7,
    after_clifford_depolarization=prob,
    before_round_data_depolarization=prob,
    before_measure_flip_probability=prob,
    after_reset_flip_probability=prob,
)

sat_instance = circuit.shortest_error_sat_problem()
# print(sat_instance)

wcnf = WCNF(from_string=sat_instance)

with RC2(wcnf) as rc2:
    print(rc2.compute())
    print("distance ", rc2.cost)

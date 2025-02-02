import sys
import os

from pandora import Pandora, PandoraConfig
from pandora.pyliqtr_to_pandora_util import make_fh_circuit

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

    circuit = make_fh_circuit(N=2, p_algo=0.9999999904, times=0.01)
    pandora.build_pyliqtr_circuit(pyliqtr_circuit=circuit)

    widgets = pandora.widgetize(max_t=10, max_d=100, batch_size=100, add_gin_per_widget=True)
    for widget in widgets:
        print(widget)

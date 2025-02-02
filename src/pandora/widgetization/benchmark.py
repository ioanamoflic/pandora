import time

from pandora.connection_util import add_inputs, update_widgetisation_results
from union_find import WidgetizationReturnCodes, WidgetUtils, \
    UnionFindWidgetizer
from pandora import Pandora, PandoraConfig


import sys

if __name__ == "__main__":

    wutils = WidgetUtils()

    if sys.argv[1] == "build":
        # this is a pandora config object. If no specific .json config file is given, the connection will be tried
        # out with default Postgres credentials. The Postgres server should be running on the machine at this stage.
        config = PandoraConfig()
        if len(sys.argv) > 1:
            if sys.argv[1].endswith(".json"):
                config.update_from_file(sys.argv[1])
                next_arg = 2

        # create a Pandora object instance
        pandora = Pandora(pandora_config=config,
                          max_time=3600,
                          decomposition_window_size=1000000)
        # build Pandora
        pandora.build_pandora()
        # decompose and insert a circuit into Pandora (if this is not already done)
        pandora.build_qualtran_adder(bitsize=3)
        # build the edge list of the decomposed circuit.
        pandora.build_edge_list()

    elif sys.argv[1] == "uf":
        ret_code_stats = {WidgetizationReturnCodes.OK: 0,
                          WidgetizationReturnCodes.EXIST: 0,
                          WidgetizationReturnCodes.TCOUNT: 0,
                          WidgetizationReturnCodes.DEPTH: 0}

        config = PandoraConfig()
        if len(sys.argv) > 1:
            if sys.argv[1].endswith(".json"):
                config.update_from_file(sys.argv[1])
                next_arg = 2

        pandora = Pandora(pandora_config=config,
                          max_time=3600,
                          decomposition_window_size=3)

        start_time = time.time()
        batch_edges = pandora.get_batched_edge_list(batch_size=10)

        for i, batch_of_edges in enumerate(batch_edges):
            if i != 0:
                batch_of_edges = add_inputs(batch_of_edges)
            batch_start = time.time()
            id_set = []
            for (s, t) in batch_of_edges:
                id_set.append(s)
                id_set.append(t)

            ids_start = time.time()
            pandora_gates = pandora.get_pandora_gates_by_id(list(set(id_set)))
            print(f'Getting ids took {time.time() - ids_start}')

            uf = UnionFindWidgetizer(edges=batch_of_edges,
                                     pandora_gates=pandora_gates,
                                     max_t=5,
                                     max_d=10)

            for node1, node2 in batch_of_edges:
                ret = uf.union(node1, node2)
                ret_code_stats[ret] = ret_code_stats[ret] + 1

            pandora_gate_dict = dict([(pandora_gate.id, pandora_gate) for pandora_gate in pandora_gates])
            print(ret_code_stats)

            nr_widgets, avd, avt, full_count = uf.compute_widgets_and_properties()
            print(f"Avg. depth={avd},  Avg. T depth={avt} for Nr. widgets={nr_widgets}, Full count={full_count}")
            print(f"Widgetising batch {i} of pandora edges took {time.time() - batch_start}")

            wutils.generate_d3_json_for_uf(uf_widgetizer=uf,
                                           pandora_gate_dict=pandora_gate_dict,
                                           batch_id=str(i),
                                           file_path="../../../vis")
            # update_widgetisation_results(connection=connection,
            #                              id=fh_N,
            #                              widgetisation_time=total_union_time,
            #                              widget_count=total_widget_count,
            #                              extraction_time=total_extraction_time)
        print(f'Time it took to widgetize Adder = {time.time() - start_time}')




import csv
import random
import time
from union_find import WidgetizationReturnCodes, BFSWidgetization, WidgetUtils, \
    UnionFindWidgetizer

# from widget_plot import plot3dsurface
from pandora import Pandora, PandoraConfig


import sys

if __name__ == "__main__":

    wutils = WidgetUtils()

    # if sys.argv[1] == "plot":
    #     plot3dsurface()
    if sys.argv[1] == "build":
        # Build a circuit in the Pandora
        config = PandoraConfig()
        if len(sys.argv) > 1:
            if sys.argv[1].endswith(".json"):
                config.update_from_file(sys.argv[1])
                next_arg = 2

        pandora = Pandora(pandora_config=config,
                          max_time=3600,
                          decomposition_window_size=1000000)
        pandora.build_pandora()
        pandora.build_edge_list()

        # print("Connecting...")
        # connection = get_connection()
        # cursor = connection.cursor()

        # print("Get Edge List...")
        # max_node_id = 0
        # edges = get_edge_list(connection)

        # for tup in edges:
        #     s, t = tup
        #     max_node_id = max(max_node_id, max(s, t))
        # num_elem = max_node_id + 1

        # gate_labels = get_gate_types(connection, num_elem)
        # connection.close()

        # file1 = open('edges.txt', 'w')
        # file1.write(f"{num_elem}\n")
        # file1.write(f"{len(edges)}\n")
        # for tup in edges:
        #     file1.write(f"{tup[0]},{tup[1]}\n")
        # for i in range(num_elem):
        #     file1.write(f"{gate_labels[i]}\n")
        # file1.close()

    elif sys.argv[1] == "test_bfs":
        # Read the file
        num_elem = 0
        edges = []
        gate_labels = []

        file1 = open('edges.txt', 'r')
        num_elem = int(file1.readline())
        num_edges = int(file1.readline())
        for tup in range(num_edges):
            s = file1.readline().split(",")
            edges.append((int(s[0]), int(s[1])))

        for i in range(num_elem):
            gate_labels.append(file1.readline().strip())

        print("Start widget find...")
        """
            Stats
        """
        ret_code_stats = {WidgetizationReturnCodes.OK: 0,
                          WidgetizationReturnCodes.EXIST: 0,
                          WidgetizationReturnCodes.TCOUNT: 0,
                          WidgetizationReturnCodes.DEPTH: 0}
        widget_count = []
        n_overlapping = []
        times = []
        record_t = []
        record_d = []

        # t_counts = [x for x in range(0, 1000, 200)][1:]
        # depths = [100, 1000, 10000]

        t_counts = [50]
        depths = [100]

        nodes = []

        for t_count_i in t_counts:
            for depth_i in depths:

                start_time = time.time()

                # uf = UnionFindWidgetization(num_elem,
                #                             max_t=t_count_i,
                #                             max_d=depth_i,
                #                             all_edges=edges,
                #                             node_labels=gate_labels)
                # # random.shuffle(edges)
                # for node1, node2 in edges:
                #     ret = uf.union(node1, node2)
                #     #update stats
                #     ret_code_stats[ret] = ret_code_stats[ret] + 1

                bfsw = BFSWidgetization(num_elem, edges, gate_labels)
                nr_potential_roots = len(bfsw.get_potential_roots())
                while nr_potential_roots > 0:
                    root = random.choice(bfsw.get_potential_roots())

                    ret = bfsw.widgetize(root, t_count_i, depth_i)
                    ret_code_stats[ret] += 1

                    nr_potential_roots = len(bfsw.get_potential_roots())

                end_time = time.time()

                # nrwidgets, avs, avt = uf.compute_widgets_and_properties()
                nrwidgets, avs, avt = bfsw.compute_widgets_and_properties()
                print(f"Started with {t_count_i} and {depth_i} -> {nrwidgets} avgsize={avs} avt={avt}")
                print(f"     Time union = {end_time - start_time}")

                record_t.append(t_count_i)
                record_d.append(depth_i)
                widget_count.append(nrwidgets)

                # start_overlap = time.time()
                # n_overlapping.append(uf.overlap_count())
                # print(f"Time overlap = {time.time() - start_overlap}")
                times.append(end_time - start_time)

                wutils.generate_d3_json(bfsw, file_path=".")

        print(ret_code_stats)

        # rows = zip(t_counts, depths, widget_count, n_overlapping, times)
        rows = zip(record_t, record_d, widget_count, times)
        with open('widget_bench.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['record_t', 'record_d', 'widget_count', 'times'])
            for row in rows:
                writer.writerow(row)

        # Finally, plot the results
        # plot3dsurface()

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
                          decomposition_window_size=1000000)

        start_time = time.time()
        pandora.build_pandora()
        pandora.build_qualtran_adder(bitsize=2)
        pandora.build_edge_list()
        batch_edges = pandora.get_batched_edge_list(batch_size=2000000)

        for i, batch_of_edges in enumerate(batch_edges):
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
                                           file_path="../../../vis")
        print(f'Time it took to widgetize FH (2) = {time.time() - start_time}')




import csv
import random
import time
from connection_util import *
from union_find import UnionFindWidgetization, WidgetizationReturnCodes, BFSWidgetization, WidgetUtils

from widget_plot import plot3dsurface

import sys

if __name__ == "__main__":

    wutils = WidgetUtils()

    if sys.argv[1] == "plot":
        plot3dsurface()

    elif sys.argv[1] == "build":

        # Build a circuit in the Pandora
        wutils.build_pandora(bit_size=15)

        print("Connecting...")
        connection = get_connection()
        cursor = connection.cursor()

        print("Get Edge List...")
        max_node_id = 0
        edges = get_edge_list(connection)

        for tup in edges:
            s, t = tup
            max_node_id = max(max_node_id, max(s, t))
        num_elem = max_node_id + 1

        gate_labels = get_gate_types(connection, num_elem)
        connection.close()

        file1 = open('edges.txt', 'w')
        file1.write(f"{num_elem}\n")
        file1.write(f"{len(edges)}\n")
        for tup in edges:
            file1.write(f"{tup[0]},{tup[1]}\n")
        for i in range(num_elem):
            file1.write(f"{gate_labels[i]}\n")
        file1.close()

    elif sys.argv[1] == "union":

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
        ret_code_stats = {}
        ret_code_stats[WidgetizationReturnCodes.OK] = 0
        ret_code_stats[WidgetizationReturnCodes.EXIST] = 0
        ret_code_stats[WidgetizationReturnCodes.TCOUNT] = 0
        ret_code_stats[WidgetizationReturnCodes.DEPTH] = 0

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

                wutils.generate_d3_json(bfsw)

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


import random
import time

import igraph as ig
from qualtran2db import *
from _connection import *
import json

sys.setrecursionlimit(1000000)

from enum import Enum

class WidgetizationReturnCodes(Enum):
    OK = 0
    EXIST = 1
    TCOUNT = 2
    DEPTH = 3

class BFSWidgetization:


    def __init__(self, num_elem, edges, node_labels):
        self.parent = [x for x in range(num_elem)]

        self.g = ig.Graph()
        self.g.add_vertices(num_elem)
        self.g.add_edges(edges)

        self.edges = edges
        self.not_visited_nodes = set(range(num_elem))
        self.widget = list(range(num_elem))
        self.node_labels = node_labels

        self.size = {}
        self.t_count = {}

    def get_potential_roots(self):
        return list(self.not_visited_nodes)
    def is_tgate(self, index):
        label = self.node_labels[index]
        return label == "Z**0.25" or label == "Z**-0.25"

    def widgetize(self, root, max_tcount, max_size):

        tcount = 0
        for vertex, dist, parent in self.g.dfsiter(root, advanced=True):

            if vertex.index not in self.not_visited_nodes:
                continue

            self.not_visited_nodes.remove(vertex.index)
            self.widget[vertex.index] = root

            if root not in self.size:
                self.size[root] = 0
            if root not in self.t_count:
                self.t_count[root] = 0

            self.size[root] = 1 + self.size[root]

            if parent is None:
                # print(f"Widget from {vertex.index}")
                True
            else:
                # print(f"Vertex {vertex.index} reached at distance {dist} from vertex {parent.index}")
                if self.is_tgate(vertex.index):
                    self.t_count[root] = 1 + self.t_count[root]

                if self.t_count[root] == max_tcount:
                    # print("... found")
                    return WidgetizationReturnCodes.TCOUNT

                if self.size[root] == max_size:
                    # print("... found")
                    return WidgetizationReturnCodes.DEPTH

        return WidgetizationReturnCodes.OK

    def compute_widgets_and_properties(self):

        # Create a set of all the unique widgets
        widgets = set(self.widget)

        self.widget_count = len(widgets) + 1

        sss = [self.size[w] for w in widgets]
        avg_size = sum(sss) / len(sss)

        ttt = [self.t_count[w] for w in widgets]
        avg_t = sum(ttt) / len(ttt)

        return self.widget_count, avg_size, avg_t

class UnionFindWidgetization:
    def __init__(self, num_elem, max_t, max_d, all_edges, node_labels):
        self.widget = [x for x in range(num_elem)]
        self.size = [1] * num_elem
        self.depth = [1] * num_elem
        self.t_count = [1 if t == "Z**0.25" or t == "Z**-0.25" else 0 for t in node_labels]
        self.widget_count = 0
        self.max_t_count = max_t
        self.max_depth = max_d
        self.edges = all_edges
        self.node_labels = node_labels

    def find(self, node):
        # Path compression. The union-find way
        while node != self.widget[node]:
            # path compression
            self.widget[node] = self.widget[self.widget[node]]
            node = self.widget[node]

        return node

    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)

        t_count1 = self.t_count[root1]
        t_count2 = self.t_count[root2]

        depth1 = self.depth[root1]
        depth2 = self.depth[root2]

        # already in the same set
        if root1 == root2:
            return WidgetizationReturnCodes.EXIST

        if t_count1 + t_count2 > self.max_t_count:
            return WidgetizationReturnCodes.TCOUNT

        if depth1 + depth2 > self.max_depth:
            return WidgetizationReturnCodes.DEPTH

        if self.size[root1] > self.size[root2]:
            # Root1 is large
            self.update_properties(root1, root2)
        else:
            # Root2 is large
            self.update_properties(root2, root1)

        return WidgetizationReturnCodes.OK

    def update_properties(self, root_large, root_small):
        self.widget[root_small] = root_large

        self.size[root_large] += self.size[root_small]
        self.depth[root_large] += self.depth[root_small]
        self.t_count[root_large] += self.t_count[root_small]

    def compute_widgets_and_properties(self):

        # Compress all the possible paths
        for node in range(len(self.widget)):
            self.find(node)

        # Create a set of all the unique widgets
        widgets = set(self.widget)

        self.widget_count = len(widgets) + 1

        sss = [self.size[w] for w in widgets]
        avg_size = sum(sss) / len(sss)

        ttt = [self.t_count[w] for w in widgets]
        avg_t = sum(ttt) / len(ttt)

        return self.widget_count, avg_size, avg_t

    def print_components(self, verbose=False):
        components = {}
        for i, node in enumerate(self.widget):
            if node == i:
                components[node] = [node]

        for i, parent in enumerate(self.widget):
            if parent in components.keys():
                components[parent].append(i)

        if verbose:
            for (k, v) in components.items():
                print(f"Component {k} has elements {v}")

        return components

    def overlap_count(self):
        n_overlapping = 0
        component_types = {}
        for i, node in enumerate(self.widget):
            if node == i:
                component_types[node] = [self.node_labels[node]]
        for i, parent in enumerate(self.widget):
            if parent in component_types.keys():
                component_types[parent].append(self.node_labels[i])

        all_components = component_types.values()
        for i, c_i in enumerate(all_components):
            for j, c_j in enumerate(all_components):
                if i != j and set(c_i) == set(c_j) and len(c_i) == len(c_j):
                    n_overlapping += 1

        return n_overlapping

    def display_png_graph(self):
        components = self.print_components()
        color_map = {}
        g = ig.Graph(edges=self.edges, directed=True)
        g.vs["label"] = self.node_labels
        for root in components.keys():
            color_map[root] = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        g.vs["color"] = [color_map[self.widget[i]] if self.widget[i] in color_map.keys() else "white" for i in
                         range(len(self.widget))]

        # make it look like an actual circuit
        layout = g.layout_reingold_tilford(root=[0], mode="all")
        layout = [[y, -x] for x, y in layout]

        ig.plot(
            g,
            layout=layout,
            target="graph.png",
            vertex_size=30,
            vertex_color=g.vs["color"],
            vertex_label=g.vs["label"],
        )

class WidgetUtils:
    def generate_d3_json(self, widgetizer):
        json_dict = {}
        nodes = []
        links = []
        for node_id in range(len(widgetizer.widget)):
            d = {"id": f'{widgetizer.node_labels[node_id]} ({node_id})', "group": widgetizer.widget[node_id]}
            nodes.append(d)
        json_dict["nodes"] = nodes

        for source, target in widgetizer.edges:
            d = {"source": f'{widgetizer.node_labels[source]} ({source})', "target": f'{widgetizer.node_labels[target]} ({target})',
                 "value": 1}
            links.append(d)
        json_dict["links"] = links

        json_data = json.dumps(json_dict)
        with open("circuit.json", "w") as f:
            f.write(json_data)

    def build_pandora(self, bit_size=3000):
        connection = get_connection()
        cursor = connection.cursor()

        create_linked_table(connection, clean=True)
        refresh_all_stored_procedures(connection)

        start_time = time.time()
        bloq = Add(QUInt(bit_size))
        circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
        assert_circuit_in_clifford_plus_t(circuit)
        db_tuples, _ = cirq2db.cirq_to_db(cirq_circuit=circuit,
                                          last_id=0,
                                          label=f'Adder{bit_size}',
                                          add_margins=True)

        insert_in_batches(db_tuples=db_tuples, connection=connection, batch_size=1000000, reset_id=True)
        print(f"Time needed for compiling {bit_size} bit adder {time.time() - start_time}")
        cursor.execute("call linked_toffoli_decomp()")
        thread_procedures = [(1, f"call generate_edge_list()")]
        db_multi_threaded(thread_proc=thread_procedures)
        print("done.")


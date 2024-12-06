import random
import time

import igraph as ig
from qualtran2db import *
from _connection import *
import json

sys.setrecursionlimit(1000000)

from enum import Enum

class UnionReturnCodes(Enum):
    OK = 0
    EXIST = 1
    TCOUNT = 2
    DEPTH = 3

class UnionFindWidgetization:
    def __init__(self, num_elem, max_t, max_d, all_edges, node_labels):
        self.parent = [x for x in range(num_elem)]
        self.size = [1] * num_elem
        self.depth = [1] * num_elem
        self.t_count = [1 if t == "Z**0.25" or t == "Z**-0.25" else 0 for t in node_labels]
        self.widget_count = 0
        self.max_t_count = max_t
        self.max_depth = max_d
        self.edges = all_edges
        self.node_labels = node_labels

    def find(self, node):
        while node != self.parent[node]:
            # path compression
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    """
       Returns 0 - everything ok
       1 - already same union
       2 - tcount overflow
       3 - gatecount overflow 
    """
    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)

        t_count1 = self.t_count[root1]
        t_count2 = self.t_count[root2]

        depth1 = self.depth[root1]
        depth2 = self.depth[root2]

        # already in the same set
        if root1 == root2:
            return UnionReturnCodes.EXIST

        if t_count1 + t_count2 > self.max_t_count:
            return UnionReturnCodes.TCOUNT

        if depth1 + depth2 > self.max_depth:
            return UnionReturnCodes.DEPTH

        if self.size[root1] > self.size[root2]:
            # Root1 is large
            self.update_properties(root1, root2)
        else:
            # Root2 is large
            self.update_properties(root2, root1)

        return UnionReturnCodes.OK

    def update_properties(self, root_large, root_small):
        self.parent[root_small] = root_large

        self.size[root_large] += self.size[root_small]
        self.depth[root_large] += self.depth[root_small]
        self.t_count[root_large] += self.t_count[root_small]

    def compute_widgets_and_properties(self):

        # Compress all the possible paths
        for node in range(len(self.parent)):
            self.find(node)

        # Create a set of all the unique widgets
        widgets = set(self.parent)

        self.widget_count = len(widgets) + 1

        sss = [self.size[w] for w in widgets]
        avg_size = sum(sss) / len(sss)

        ttt = [self.t_count[w] for w in widgets]
        avg_t = sum(ttt) / len(ttt)

        return self.widget_count, avg_size, avg_t

    def print_components(self, verbose=False):
        components = {}
        for i, node in enumerate(self.parent):
            if node == i:
                components[node] = [node]

        for i, parent in enumerate(self.parent):
            if parent in components.keys():
                components[parent].append(i)

        if verbose:
            for (k, v) in components.items():
                print(f"Component {k} has elements {v}")

        return components

    def overlap_count(self):
        n_overlapping = 0
        component_types = {}
        for i, node in enumerate(self.parent):
            if node == i:
                component_types[node] = [self.node_labels[node]]
        for i, parent in enumerate(self.parent):
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
        g.vs["color"] = [color_map[self.parent[i]] if self.parent[i] in color_map.keys() else "white" for i in
                         range(len(self.parent))]

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

    def generate_d3_json(self):
        json_dict = {}
        nodes = []
        links = []
        for node_id in range(len(self.parent)):
            d = {"id": f'{self.node_labels[node_id]} ({node_id})', "group": self.parent[node_id]}
            nodes.append(d)
        json_dict["nodes"] = nodes

        for source, target in self.edges:
            d = {"source": f'{self.node_labels[source]} ({source})', "target": f'{self.node_labels[target]} ({target})',
                 "value": 1}
            links.append(d)
        json_dict["links"] = links

        json_data = json.dumps(json_dict)
        with open("widgetization/circuit.json", "w") as f:
            f.write(json_data)

    def build_pandora(self):
        bit_size = 3000

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


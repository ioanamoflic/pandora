import random
import time

import igraph as ig
from qualtran2db import *
from _connection import *
import json
sys.setrecursionlimit(100000)


class UnionFind:
    def __init__(self, num_elem, max_t, max_d, all_edges, node_labels, t_loc):
        self.parent = self.make_set(num_elem)
        self.size = [1] * num_elem
        self.depth = [1] * num_elem
        self.count_t = t_loc
        self.count = num_elem
        self.max_t_count = max_t
        self.max_depth = max_d
        self.edges = all_edges
        self.node_labels = node_labels

    def make_set(self, num_elem):
        return [x for x in range(num_elem)]

    def find(self, node):
        while node != self.parent[node]:
            # path compression
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)

        t_count1 = self.count_t[root1]
        t_count2 = self.count_t[root2]

        depth1 = self.depth[root1]
        depth2 = self.depth[root2]

        # already in the same set
        if root1 == root2:
            return

        if t_count1 + t_count2 > self.max_t_count:
            return

        if depth1 + depth2 > self.max_depth:
            return

        if self.size[root1] > self.size[root2]:
            self.parent[root2] = root1
            self.size[root1] += 1
            self.depth[root1] += 1
            self.count_t[root1] += t_count2
        else:
            self.parent[root1] = root2
            self.size[root2] += 1
            self.depth[root2] += 1
            self.count_t[root2] += t_count1

        self.count -= 1

    def print_components(self):
        components = {}
        for i, node in enumerate(self.parent):
            if node == i:
                components[node] = []

        for i, parent in enumerate(self.parent):
            if parent in components.keys():
                components[parent].append(i)

        # for (k, v) in components.items():
        #     print(f"Component {k} has elements {v}")

        return components

    def display_graph(self):
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

    def display_graph_d3(self):
        json_dict = {}
        nodes = []
        links = []
        for node_id in range(len(self.parent)):
            d = {"id": f'{self.node_labels[node_id]} ({node_id})', "group": self.parent[node_id]}
            nodes.append(d)
        json_dict["nodes"] = nodes

        for source, target in self.edges:
            d = {"source": f'{self.node_labels[source]} ({source})', "target": f'{self.node_labels[target]} ({target})', "value": 1}
            links.append(d)
        json_dict["links"] = links

        json_data = json.dumps(json_dict)
        with open("circuit.json", "w") as f:
            f.write(json_data)


if __name__ == "__main__":
    connection = get_connection()
    cursor = connection.cursor()

    create_linked_table(connection, clean=True)
    refresh_all_stored_procedures(connection)

    bit_size = 15
    start_time = time.time()

    bloq = Add(QUInt(bit_size))
    circuit = get_clifford_plus_t_cirq_circuit_for_bloq(bloq)
    # print(circuit)
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

    max_node_id = 0
    edges = get_edge_list(connection)
    for tup in edges:
        s, t = tup
        max_node_id = max(max_node_id, max(s, t))

    num_elem = max_node_id + 1

    gate_labels = get_gate_types(connection, num_elem)
    t_locations = [1 if t == "Z**0.25" or t == "Z**-0.25" else 0 for t in gate_labels]

    # print(edges)
    # print(t_locations)

    max_t_count = 20
    max_depth = 100

    start_time = time.time()

    uf = UnionFind(num_elem, max_t=max_t_count, max_d=max_depth, all_edges=edges,
                   node_labels=gate_labels, t_loc=t_locations)

    for node1, node2 in edges:
        uf.union(node1, node2)

    print(f"Time needed for widgetising {bit_size} bit adder {time.time() - start_time}")

    # print(uf.parent)
    # uf.display_graph()
    start_time = time.time()
    uf.display_graph_d3()
    print(f"Time needed for json for {bit_size} bit adder {time.time() - start_time}")

    print("Number of connected components", uf.count)


import random

from enum import Enum
import igraph as ig

from pandora.widgetization.widget import Widget
from pandora.connection_util import *

sys.setrecursionlimit(1000000)


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
        for vertex, dist, parent in self.g.bfsiter(root, advanced=True):

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


class UnionFindWidgetizer:
    def __init__(self, edges, pandora_gates, max_t, max_d):
        self.n_gates: int = len(pandora_gates)
        # initially, every node is its own widget, and the dictionary key = pandora_gate_root.id
        # this will change during the execution of UF
        # the widget count will be given by the number of unique pandora_gate_root values
        self.parent = dict([(pandora_gate.id, Widget(depth=1,
                                                     t_count=1 if
                                                     pandora_gate.type == PandoraGateTranslator.ZPowGate.value and
                                                     pandora_gate.param in [0.25, -0.25] else 0,
                                                     root=pandora_gate))
                            for pandora_gate in pandora_gates])

        self.widget_count = 0
        self.max_t_count = max_t
        self.max_depth = max_d
        self.edges = edges

    def find(self, current_id: int) -> int:
        """
        Find step of union-find. Returns the root id of the current node id.
        Args:
            current_id: the id of the initial node

        Returns:
            The id of the root.
        """

        root_of_current = self.parent[current_id].root.id
        if root_of_current != current_id:
            # path compression call
            self.parent[current_id] = self.parent[self.find(root_of_current)]
        return root_of_current

    def union(self, node_id_1, node_id_2):
        """
        Union step of union-find.
        Args:
            node_id_1: id of the first node
            node_id_2: id of the second node

        Returns:

        """
        root_id_1 = self.find(node_id_1)
        root_id_2 = self.find(node_id_2)

        t_count_1, depth_1 = self.parent[root_id_1].t_count, self.parent[root_id_1].depth
        t_count_2, depth_2 = self.parent[root_id_2].t_count, self.parent[root_id_2].depth

        # already in the same set
        if root_id_1 == root_id_2:
            return WidgetizationReturnCodes.EXIST

        if t_count_1 + t_count_2 > self.max_t_count:
            return WidgetizationReturnCodes.TCOUNT

        if depth_1 + depth_2 > self.max_depth:
            return WidgetizationReturnCodes.DEPTH

        if self.parent[root_id_1].depth >= self.parent[root_id_2].depth:
            # Root1 is large
            self.update_properties(root_id_1, root_id_2)
        else:
            # Root2 is large
            self.update_properties(root_id_2, root_id_1)

        return WidgetizationReturnCodes.OK

    def update_properties(self, root_large_id: int, root_small_id: int) -> None:
        """
        Updates the properties of the merging cluster. The "big" cluster will take the additional T count and depth of
        the small cluster.

        Args:
            root_large_id: id of the large cluster
            root_small_id: if of the merged cluster

        Returns:
            None.
        """
        self.parent[root_large_id].depth += self.parent[root_small_id].depth
        self.parent[root_large_id].t_count += self.parent[root_small_id].t_count

        self.parent[root_small_id] = self.parent[root_large_id]

    def compute_widgets_and_properties(self):
        # Compress all the possible paths -- not needed because the paths are already compressed in find?
        # for node_id in self.parent.keys():
        #     self.find(node_id)

        # Create a set of all the unique widgets
        widgets = set(self.parent.values())
        self.widget_count = len(widgets)

        depths = [w.depth for w in widgets]
        full_widget_count = sum([1 for w in widgets if w.depth == self.max_depth])

        avg_depth = sum(depths) / len(depths)

        t_counts = [w.t_count for w in widgets]
        avg_t = sum(t_counts) / len(t_counts)

        return self.widget_count, avg_depth, avg_t, full_widget_count

    def print_components(self, verbose=False):
        components = {}
        for node_id, widget in self.parent.items():
            if widget.root.id not in components.keys():
                components[widget.root.id] = []
            components[widget.root.id].append(node_id)

        if verbose:
            for (k, v) in components.items():
                print(f"Component {k} has elements {v}")

        return components

    def display_png_graph(self):
        """
        Deprecated and replaced with D3.
        """
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
    @staticmethod
    def generate_d3_json(widgetizer: BFSWidgetization, file_path=""):
        json_dict = {}
        nodes = []
        links = []
        for node_id in range(len(widgetizer.widget)):
            d = {"id": f'{widgetizer.node_labels[node_id]} ({node_id})', "group": widgetizer.widget[node_id]}
            nodes.append(d)
        json_dict["nodes"] = nodes

        for source, target in widgetizer.edges:
            d = {"source": f'{widgetizer.node_labels[source]} ({source})',
                 "target": f'{widgetizer.node_labels[target]} ({target})',
                 "value": 1}
            links.append(d)
        json_dict["links"] = links

        json_data = json.dumps(json_dict)
        with open(f"{file_path}/circuit.json", "w") as f:
            f.write(json_data)

    @staticmethod
    def generate_d3_json_for_uf(uf_widgetizer: UnionFindWidgetizer,
                                pandora_gate_dict: dict[int, PandoraGate],
                                file_path=""):
        json_dict = {}
        nodes = []
        links = []
        for node_id in uf_widgetizer.parent.keys():
            readable = PANDORA_TO_READABLE[pandora_gate_dict[node_id].type]
            d = {"id": f'{readable}*{pandora_gate_dict[node_id].param}({node_id})',
                 "group": uf_widgetizer.parent[node_id].root.id}
            nodes.append(d)

        json_dict["nodes"] = nodes
        for source, target in uf_widgetizer.edges:
            readable_source = PANDORA_TO_READABLE[pandora_gate_dict[source].type]
            readable_target = PANDORA_TO_READABLE[pandora_gate_dict[target].type]

            d = {
                "source": f'{readable_source}*{pandora_gate_dict[source].param}({source})',
                "target": f'{readable_target}*{pandora_gate_dict[target].param}({target})',
                "value": 1
            }
            links.append(d)
        json_dict["links"] = links

        json_data = json.dumps(json_dict)
        with open(f"{file_path}/circuit.json", "w") as f:
            f.write(json_data)

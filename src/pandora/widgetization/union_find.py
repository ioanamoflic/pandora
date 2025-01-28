from enum import Enum
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from pandora.widgetization.widget import Widget
from pandora.connection_util import *

sys.setrecursionlimit(1000000)


class WidgetizationReturnCodes(Enum):
    OK = 0
    EXIST = 1
    TCOUNT = 2
    DEPTH = 3


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
            # path compression
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
        for node_id in self.parent.keys():
            self.find(node_id)

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


class WidgetUtils:
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

    @staticmethod
    def plot3dsurface():
        fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
        df = pd.read_csv('widget_bench.csv', sep=',', usecols=['record_t', 'record_d', 'widget_count', 'times'])

        # Make data
        x = df['record_d']
        y = df['record_t']
        z = df['widget_count']

        x = np.log10(x)
        y = np.log10(y)
        z = np.log10(z)

        surf = ax.plot_trisurf(x, y, z, antialiased=False, edgecolor="black", linewidth=0.1, )

        ax.set_xlabel("Log(Depth)")
        ax.set_ylabel("Log(T-count)")
        ax.set_zlabel("Log(Widget-Count)")

        plt.show()

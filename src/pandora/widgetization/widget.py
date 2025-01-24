from pandora.gates import PandoraGate


class PandoraEdge:
    def __int__(self,
                source: PandoraGate | int,
                target: PandoraGate | int,
                weight: int = None):
        self.source = source
        self.target = target
        self.weight = weight


class Widget:
    def __init__(self, depth, t_count, root: PandoraGate):
        self.depth = depth
        self.t_count = t_count
        self.root = root
        # this could be used in the future to mark this as a starting point for widgetization
        self.is_starting_node = False

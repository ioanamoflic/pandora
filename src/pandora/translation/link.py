class LinkID:
    """
    Full format:
        gate_id * 1000 + port * 100 + type

    Stripped format:
        full // 100 == gate_id * 10 + port
    """

    @staticmethod
    def encode(gate_id: int, gate_port: int, gate_type: int) -> int:
        return gate_id * 1000 + gate_port * 100 + gate_type

    @staticmethod
    def gate_id(link_id: int) -> int:
        return link_id // 1000

    @staticmethod
    def port(link_id: int) -> int:
        return (link_id // 100) % 10

    @staticmethod
    def gate_type(link_id: int) -> int:
        return link_id % 100

    @staticmethod
    def remove_type(link_id: int) -> int:
        return link_id // 100

    @staticmethod
    def stripped_gate_id(link_id: int) -> int:
        return link_id // 10

    @staticmethod
    def stripped_port(link_id: int) -> int:
        return link_id % 10

    @staticmethod
    def is_non_input(link_id: int) -> bool:
        return link_id is not None and link_id > 100

    @staticmethod
    def strip_type(link: int | None) -> int | None:
        if LinkID.is_non_input(link):
            return LinkID.remove_type(link)
        return link

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcJob:
    kind: str

    # RSA-params
    n_bits: Optional[int] = None

    # Fermion-Hubbard params
    N: Optional[int] = None
    times: Optional[float] = None
    p_algo: Optional[float] = None

    # who am I
    n_nodes: int = None
    nprocs_per_node: int = None
    my_node_id: int = None
    my_proc_id: int = None



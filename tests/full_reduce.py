import pytest
import pytest_asyncio
import pyzx

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService

config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}

def get_adder(n_bits: int) -> pyzx.Circuit:
    # Adders from https://github.com/njross/optimizer/tree/master/QFT_and_Adders
    return pyzx.Circuit.load(f"benchmarking/adders/Adder{n_bits}.txt")

def create_chain_g() -> pyzx.Graph:
    # ------------------------------------------------------------------
    # 1. Simple linear chain
    # ------------------------------------------------------------------
    g = pyzx.Graph()

    v0 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    g.set_inputs((v0,))
    v1 = g.add_vertex(ty=pyzx.VertexType.Z, phase=0)
    v2 = g.add_vertex(ty=pyzx.VertexType.X, phase=1)
    v3 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    g.set_outputs((v3,))

    g.add_edges([(v0, v1), (v1, v2), (v2, v3)])
    return g
    
def create_bell_g() -> pyzx.Graph:
    g = pyzx.Graph()

    i0 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    i1 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    g.set_inputs((i0, i1))

    z = g.add_vertex(ty=pyzx.VertexType.Z)
    x = g.add_vertex(ty=pyzx.VertexType.X)

    o0 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    o1 = g.add_vertex(ty=pyzx.VertexType.BOUNDARY)
    g.set_outputs((o0, o1))

    g.add_edges([
        (i0, z),
        (i1, x),
        (z, x),
        (z, o0),
        (x, o1),
    ])
    return g


def create_star_g() -> pyzx.Graph:
    g = pyzx.Graph()

    center = g.add_vertex(ty=pyzx.VertexType.Z, phase=1)

    leaves = [
        g.add_vertex(ty=pyzx.VertexType.X)
        for _ in range(5)
    ]

    for leaf in leaves:
        g.add_edge((center, leaf))
    return g


def create_loop_g() -> pyzx.Graph:
    g = pyzx.Graph()

    v = [
        g.add_vertex(ty=pyzx.VertexType.Z if i % 2 == 0 else pyzx.VertexType.X)
        for i in range(4)
    ]

    g.add_edges([
        (v[0], v[1]),
        (v[1], v[2]),
        (v[2], v[3]),
        (v[3], v[0]),
    ])
    return g

@pytest_asyncio.fixture
async def service():
    db = PandoraDB(config_file)
    await db.connect()
    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)
        await service.build_pandora()
        yield service
    finally:
        await db.close()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "graph",
    [
        get_adder(1).to_graph(),
        create_chain_g(),
        create_bell_g(),
        create_star_g(),
        create_chain_g()
    ],
)
async def test_zx_load_simple(service, graph):
    await service.load_from_pyzx(graph)
    await service.simplify_zx_full();
    simpified_graph = await service.export_to_pyzx()
    
    assert pyzx.tensor.compare_tensors(graph, simpified_graph)

    pyzx_graph = graph.copy()
    pyzx.full_reduce(pyzx_graph)

    assert len(list(pyzx_graph.vertices())) == len(list(simpified_graph.vertices()))
    assert len(list(pyzx_graph.edges())) == len(list(simpified_graph.edges()))
    assert len(list(pyzx_graph.inputs())) == len(list(simpified_graph.inputs()))
    assert len(list(pyzx_graph.outputs())) == len(list(simpified_graph.outputs()))
    assert pyzx.tensor.compare_tensors(pyzx_graph, simpified_graph)

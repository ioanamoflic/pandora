import pytest
import pytest_asyncio
import pyzx

from fractions import Fraction
from pandora.db.core import PandoraDB
from pandora.translation.pyzx import read_to_pyzx_graph, write_from_pyzx_graph

config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234"
}

@pytest_asyncio.fixture
async def conn():
    db = PandoraDB(config_file)
    await db.connect()

    try:
        async with db.acquire() as conn:
            await conn.execute("TRUNCATE TABLE zx_edge RESTART IDENTITY CASCADE")
            await conn.execute("TRUNCATE TABLE zx_vertex RESTART IDENTITY CASCADE")

            yield conn
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_read_to_pyzx_graph(conn):
    await conn.execute(
        """
        INSERT INTO zx_vertex(id, type, qubit, row, param)
        VALUES
            (1, 0, 0, 0, 0.0),
            (2, 32, 0, 1, 0.5),
            (3, 33, 0, 2, 0.25),
            (4, 35, 0, 3, 1.0),
            (5, 1, 0, 4, 0.0)
        """
    )

    await conn.execute(
        """
        INSERT INTO zx_edge(id, type, source, target)
        VALUES
            (1, 0, 1000, 2032),
            (2, 1, 2032, 3033),
            (3, 0, 3033, 4035),
            (4, 1, 4035, 5001)
        """
    )

    g = await read_to_pyzx_graph(conn)

    assert len(list(g.vertices())) == 5
    assert len(list(g.edges())) == 4

    inputs = list(g.inputs())
    outputs = list(g.outputs())

    assert len(inputs) == 1
    assert len(outputs) == 1

    assert g.type(inputs[0]) == pyzx.VertexType.BOUNDARY
    assert g.type(outputs[0]) == pyzx.VertexType.BOUNDARY

    vertices_by_row = {g.row(v): v for v in g.vertices()}

    assert g.type(vertices_by_row[1]) == pyzx.VertexType.Z
    assert g.phase(vertices_by_row[1]) == Fraction(1, 2)

    assert g.type(vertices_by_row[2]) == pyzx.VertexType.X
    assert g.phase(vertices_by_row[2]) == Fraction(1, 4)

    assert g.type(vertices_by_row[3]) == pyzx.VertexType.H_BOX
    assert g.phase(vertices_by_row[3]) == Fraction(1, 1)

    assert g.edge_type((vertices_by_row[0], vertices_by_row[1])) == pyzx.EdgeType.SIMPLE
    assert g.edge_type((vertices_by_row[1], vertices_by_row[2])) == pyzx.EdgeType.HADAMARD
    assert g.edge_type((vertices_by_row[2], vertices_by_row[3])) == pyzx.EdgeType.SIMPLE
    assert g.edge_type((vertices_by_row[3], vertices_by_row[4])) == pyzx.EdgeType.HADAMARD



@pytest.mark.asyncio
async def test_write_from_pyzx_graph(conn):
    g = pyzx.Graph()

    vin = g.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=0)
    vz = g.add_vertex(pyzx.VertexType.Z, qubit=0, row=1, phase=Fraction(1, 2))
    vx = g.add_vertex(pyzx.VertexType.X, qubit=0, row=2, phase=Fraction(1, 4))
    vh = g.add_vertex(pyzx.VertexType.H_BOX, qubit=0, row=3, phase=Fraction(1, 1))
    vout = g.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=4)

    g.set_inputs((vin,))
    g.set_outputs((vout,))

    g.add_edge((vin, vz), pyzx.EdgeType.SIMPLE)
    g.add_edge((vz, vx), pyzx.EdgeType.HADAMARD)
    g.add_edge((vx, vh), pyzx.EdgeType.SIMPLE)
    g.add_edge((vh, vout), pyzx.EdgeType.HADAMARD)

    await write_from_pyzx_graph(conn, g)

    vertices = await conn.fetch("SELECT id, type, qubit, row, param FROM zx_vertex ORDER BY id")
    edges = await conn.fetch("SELECT id, type, source, target FROM zx_edge ORDER BY id")

    assert len(vertices) == 5
    assert len(edges) == 4

    vertex_rows = {int(v["row"]): v for v in vertices}

    assert int(vertex_rows[0]["type"]) == 0
    assert int(vertex_rows[1]["type"]) == 32
    assert int(vertex_rows[2]["type"]) == 33
    assert int(vertex_rows[3]["type"]) == 35
    assert int(vertex_rows[4]["type"]) == 1

    assert float(vertex_rows[0]["param"]) == pytest.approx(0.0)
    assert float(vertex_rows[1]["param"]) == pytest.approx(0.5)
    assert float(vertex_rows[2]["param"]) == pytest.approx(0.25)
    assert float(vertex_rows[3]["param"]) == pytest.approx(1.0)
    assert float(vertex_rows[4]["param"]) == pytest.approx(0.0)

    edge_types = [int(e["type"]) for e in edges]

    assert edge_types == [0, 1, 0, 1]

    for i in range(len(edges)):
        assert int(edges[i]["source"]) // 1000 == i + 1 # 1, 2, ...
        assert int(edges[i]["target"]) // 1000 == i + 2 # 2, 3, ...



@pytest.mark.asyncio
async def test_write_from_pyzx_graph_orders_edge_endpoints_by_sql_vertex_id(conn):
    g = pyzx.Graph()

    vout = g.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=1)
    vin = g.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=0)

    g.set_inputs((vin,))
    g.set_outputs((vout,))
    g.add_edge((vout, vin), pyzx.EdgeType.SIMPLE)

    await write_from_pyzx_graph(conn, g)

    edge = await conn.fetchrow("SELECT source, target FROM zx_edge")

    assert int(edge["source"]) == 1000
    assert int(edge["target"]) == 2001
    assert int(edge["source"]) // 1000 < int(edge["target"]) // 1000


@pytest.mark.asyncio
async def test_pyzx_graph_round_trip(conn):
    expected = pyzx.Graph()

    vin = expected.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=0)
    vz = expected.add_vertex(pyzx.VertexType.Z, qubit=0, row=1, phase=Fraction(1, 2))
    vx = expected.add_vertex(pyzx.VertexType.X, qubit=0, row=2, phase=Fraction(1, 4))
    vout = expected.add_vertex(pyzx.VertexType.BOUNDARY, qubit=0, row=3)

    expected.set_inputs((vin,))
    expected.set_outputs((vout,))

    expected.add_edge((vin, vz), pyzx.EdgeType.SIMPLE)
    expected.add_edge((vz, vx), pyzx.EdgeType.HADAMARD)
    expected.add_edge((vx, vout), pyzx.EdgeType.SIMPLE)

    await write_from_pyzx_graph(conn, expected)
    actual = await read_to_pyzx_graph(conn)

    assert len(list(actual.vertices())) == len(list(expected.vertices()))
    assert len(list(actual.edges())) == len(list(expected.edges()))
    assert len(list(actual.inputs())) == len(list(expected.inputs()))
    assert len(list(actual.outputs())) == len(list(expected.outputs()))

    assert pyzx.compare_tensors(actual, expected);
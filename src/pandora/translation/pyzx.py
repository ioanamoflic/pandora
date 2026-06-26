from __future__ import annotations
from fractions import Fraction
import pyzx

VERTEX_TYPES = {
    0: pyzx.VertexType.BOUNDARY,
    1: pyzx.VertexType.BOUNDARY,
    32: pyzx.VertexType.Z,
    33: pyzx.VertexType.X,
    35: pyzx.VertexType.H_BOX,
}

PYZX_VERTEX_TYPES = {
    pyzx.VertexType.BOUNDARY: None,  # resolved as input/output below
    pyzx.VertexType.Z: 32,
    pyzx.VertexType.X: 33,
    pyzx.VertexType.H_BOX: 35,
}

EDGE_TYPES = {
    0: pyzx.EdgeType.SIMPLE,
    1: pyzx.EdgeType.HADAMARD,
}

PYZX_EDGE_TYPES = {
    pyzx.EdgeType.SIMPLE: 0,
    pyzx.EdgeType.HADAMARD: 1,
}

async def read_to_pyzx_graph(conn) -> pyzx.Graph:
    vertices = await conn.fetch("SELECT id, type, qubit, row, param FROM zx_vertex ORDER BY id")
    edges = await conn.fetch("SELECT id, type, source, target FROM zx_edge ORDER BY id")

    g = pyzx.Graph()

    id_map: dict[int, int] = {}
    inputs: list[int] = []
    outputs: list[int] = []

    for v in vertices:
        sql_id = int(v["id"])
        sql_type = int(v["type"])

        pyzx_id = g.add_vertex(
            VERTEX_TYPES.get(sql_type, pyzx.VertexType.BOUNDARY),
            int(v["qubit"]),
            int(v["row"]),
            phase=Fraction(v["param"]).limit_denominator(),
        )

        id_map[sql_id] = pyzx_id

        if sql_type == 0:
            inputs.append(pyzx_id)
        elif sql_type == 1:
            outputs.append(pyzx_id)

    g.set_inputs(tuple(sorted(inputs, key=g.qubit)))
    g.set_outputs(tuple(sorted(outputs, key=g.qubit)))

    for e in edges:
        source = id_map.get(e["source"] // 1000)
        target = id_map.get(e["target"] // 1000)

        if source is None or target is None:
            continue

        g.add_edge((source, target), EDGE_TYPES.get(int(e["type"]), pyzx.EdgeType.SIMPLE))

    return g

async def write_from_pyzx_graph(conn, g: pyzx.Graph) -> None:
    await conn.execute("TRUNCATE TABLE zx_edge RESTART IDENTITY")
    await conn.execute("TRUNCATE TABLE zx_vertex RESTART IDENTITY")

    inputs = set(g.inputs())
    outputs = set(g.outputs())

    vertex_id_map: dict[int, int] = {}
    id_type_map: dict[int, int] = {}

    vertices = sorted(g.vertices(), key=lambda v: (g.row(v), g.qubit(v), v))

    for sql_id, v in enumerate(vertices, start=1):
        if v in inputs:
            sql_type = 0
        elif v in outputs:
            sql_type = 1
        else:
            sql_type = PYZX_VERTEX_TYPES.get(g.type(v), 0)

        sql_id = await conn.fetchval(
            "INSERT INTO zx_vertex(type, qubit, row, param) VALUES ($1, $2, $3, $4) RETURNING id",
            int(sql_type),
            int(g.qubit(v)),
            int(g.row(v)),
            float(g.phase(v)),
        )
        vertex_id_map[v] = sql_id
        id_type_map[sql_id] = sql_type

    edges = sorted(
        g.edges(),
        key=lambda e: (min(vertex_id_map[e[0]], vertex_id_map[e[1]]), max(vertex_id_map[e[0]], vertex_id_map[e[1]])),
    )

    for edge in edges:
        source, target = edge

        source_id = vertex_id_map[source]
        target_id = vertex_id_map[target]
        source_type = id_type_map[source_id]
        target_type = id_type_map[target_id]

        # The pandora rewrites assume source_id < target_id for minor optimizations
        if source_id > target_id:
            source_id, target_id = target_id, source_id
            source_type, target_type = target_type, source_type

        await conn.execute(
            "INSERT INTO zx_edge(type, source, target) VALUES ($1, $2, $3)",
            int(PYZX_EDGE_TYPES.get(g.edge_type(edge), 0)),
            source_id * 1000 + source_type,
            target_id * 1000 + target_type,
        )
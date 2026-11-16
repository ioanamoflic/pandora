import pytest
import pytest_asyncio
import pyzx

from pandora.db.core import PandoraDB
from pandora.db.repository import GateRepository
from pandora.db.service import PandoraService
from pandora.translation.pyzx import PYZX_EDGE_TYPES
from pandora.translation.translator import PandoraGateTranslator

config_file = {
    "database": "postgres",
    "user": "moflici1",
    "host": "localhost",
    "port": "5432",
    "password": "1234",
}

SIMPLE = PYZX_EDGE_TYPES[pyzx.EdgeType.SIMPLE]
HADAMARD = PYZX_EDGE_TYPES[pyzx.EdgeType.HADAMARD]
Z = PandoraGateTranslator.Z_SPIDER.value
X = PandoraGateTranslator.X_SPIDER.value
IN = PandoraGateTranslator.In.value
OUT = PandoraGateTranslator.Out.value

async def _add_vertex(
    conn,
    vtype: int,
    *,
    phase: float = 0.0,
    qubit: int = 0,
    row: int = 0,
) -> int:
    return await conn.fetchval(
        "INSERT INTO zx_vertex(type, qubit, row, param) VALUES($1, $2, $3, $4) RETURNING id",
        vtype,
        qubit,
        row,
        phase,
    )


async def _add_edge(conn, source_id: int, target_id: int, edge_type: int) -> int:
    assert source_id < target_id
    return await conn.fetchval(
        "INSERT INTO zx_edge(type, source, target) VALUES($1, zx_vertex_ref($2), zx_vertex_ref($3)) RETURNING id",
        edge_type,
        source_id,
        target_id,
    )


async def _call_rewrite(conn, name: str) -> None:
    # The function name is intentionally not user-controlled in these tests.
    await conn.execute(f"CALL {name}(false)")


async def _count(conn, table: str, where: str | None = None, *args) -> int:
    query = f"SELECT count(*) FROM {table}"
    if where:
        query += f" WHERE {where}"
    return await conn.fetchval(query, *args)


async def _phase(conn, vertex_id: int) -> float:
    value = await conn.fetchval("SELECT param FROM zx_vertex WHERE id = $1", vertex_id)
    return float(value or 0.0)


async def _vertex_type(conn, vertex_id: int) -> int:
    return await conn.fetchval("SELECT type FROM zx_vertex WHERE id = $1", vertex_id)


async def _degree(conn, vertex_id: int) -> int:
    return await conn.fetchval("SELECT zx_edge_degree($1)", vertex_id)


async def _edge_count_between(conn, a: int, b: int) -> int:
    return await conn.fetchval(
        """
        SELECT count(*)
            FROM zx_edge
            WHERE (get_id_from_link(source) = $1 AND get_id_from_link(target) = $2)
                OR (get_id_from_link(source) = $2 AND get_id_from_link(target) = $1)
        """,
        a,
        b,
    )


async def _edge_type_between(conn, a: int, b: int) -> int | None:
    return await conn.fetchval(
        """
        SELECT type
            FROM zx_edge
            WHERE (get_id_from_link(source) = $1 AND get_id_from_link(target) = $2)
                OR (get_id_from_link(source) = $2 AND get_id_from_link(target) = $1)
            ORDER BY id
            LIMIT 1
        """,
        a,
        b,
    )


async def _assert_edge(conn, a: int, b: int, edge_type: int) -> None:
    assert await _edge_count_between(conn, a, b) == 1, f"Expected exactly one edge between {a} and {b}"
    assert await _edge_type_between(conn, a, b) == edge_type, f"Unexpected edge type between {a} and {b}"


async def _assert_no_hadamard_edges(conn) -> None:
    assert await _count(conn, "zx_edge", "type = $1", HADAMARD) == 0


async def _assert_no_parallel_edges(conn) -> None:
    assert await conn.fetchval(
        """
        SELECT NOT EXISTS(
            SELECT 1
                FROM zx_edge
                GROUP BY
                    LEAST(get_id_from_link(source), get_id_from_link(target)),
                    GREATEST(get_id_from_link(source), get_id_from_link(target))
                HAVING count(*) > 1
        )
        """
    )


async def _assert_no_self_loops(conn) -> None:
    assert await conn.fetchval(
        """
        SELECT NOT EXISTS(
            SELECT 1
            FROM zx_edge
            WHERE get_id_from_link(source) = get_id_from_link(target)
        )
        """
    )


async def _assert_edge_links_match_vertex_types(conn) -> None:
    assert await conn.fetchval(
        """
        SELECT NOT EXISTS(
            SELECT 1
            FROM zx_edge e
            JOIN zx_vertex source_vertex
                ON source_vertex.id = get_id_from_link(e.source)
            JOIN zx_vertex target_vertex
                ON target_vertex.id = get_id_from_link(e.target)
            WHERE e.source % 1000 <> source_vertex.type
                OR e.target % 1000 <> target_vertex.type
        )
        """
    )


async def _new_vertices(conn, *old_vertex_ids: int) -> list[int]:
    rows = await conn.fetch(
        "SELECT id FROM zx_vertex WHERE NOT (id = ANY($1::bigint[])) ORDER BY id",
        list(old_vertex_ids),
    )
    return [row["id"] for row in rows]


@pytest_asyncio.fixture
async def zx_conn():
    db = PandoraDB(config=config_file, min_size=1, max_size=1)
    await db.connect()
    try:
        repo = GateRepository(db)
        service = PandoraService(db=db, repo=repo)
        await service.build_pandora()

        async with db.acquire() as conn:
            yield conn
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_zx_to_rg_simp_recolours_boundary_h_edge_without_adding_vertices(zx_conn):
    boundary = await _add_vertex(zx_conn, IN, qubit=0, row=0)
    z = await _add_vertex(zx_conn, Z, phase=0.25, qubit=0, row=1)
    await _add_edge(zx_conn, boundary, z, HADAMARD)

    await _call_rewrite(zx_conn, "zx_remove_h_edges")

    assert await _vertex_type(zx_conn, boundary) == IN
    assert await _vertex_type(zx_conn, z) == X
    assert await _phase(zx_conn, z) == pytest.approx(0.25)
    await _assert_edge(zx_conn, boundary, z, SIMPLE)
    assert await _count(zx_conn, "zx_vertex") == 2
    assert await _count(zx_conn, "zx_edge") == 1
    await _assert_no_hadamard_edges(zx_conn)
    await _assert_no_parallel_edges(zx_conn)
    await _assert_edge_links_match_vertex_types(zx_conn)


@pytest.mark.asyncio
async def test_zx_to_rg_simp_recolours_same_colour_h_edge_without_expansion(zx_conn):
    z0 = await _add_vertex(zx_conn, Z, phase=0.25, qubit=0, row=0)
    z1 = await _add_vertex(zx_conn, Z, phase=0.75, qubit=0, row=1)
    await _add_edge(zx_conn, z0, z1, HADAMARD)

    await _call_rewrite(zx_conn, "zx_remove_h_edges")

    assert await _vertex_type(zx_conn, z0) == Z
    assert await _vertex_type(zx_conn, z1) == X
    assert await _phase(zx_conn, z0) == pytest.approx(0.25)
    assert await _phase(zx_conn, z1) == pytest.approx(0.75)
    await _assert_edge(zx_conn, z0, z1, SIMPLE)
    assert await _count(zx_conn, "zx_vertex") == 2
    assert await _count(zx_conn, "zx_edge") == 1
    await _assert_no_hadamard_edges(zx_conn)
    await _assert_no_parallel_edges(zx_conn)
    await _assert_edge_links_match_vertex_types(zx_conn)


@pytest.mark.asyncio
async def test_zx_to_rg_simp_fuses_spiders_recoloured_over_regular_edges(zx_conn):
    z0 = await _add_vertex(zx_conn, Z, qubit=0, row=0)
    z1 = await _add_vertex(zx_conn, Z, qubit=0, row=1)
    z2 = await _add_vertex(zx_conn, Z, qubit=0, row=2)
    await _add_edge(zx_conn, z0, z1, HADAMARD)
    await _add_edge(zx_conn, z1, z2, SIMPLE)

    await _call_rewrite(zx_conn, "zx_remove_h_edges")

    assert await _vertex_type(zx_conn, z0) == Z
    assert await _vertex_type(zx_conn, z1) == X
    assert await _vertex_type(zx_conn, z2) is None
    await _assert_edge(zx_conn, z0, z1, SIMPLE)
    assert await _count(zx_conn, "zx_vertex") == 2
    assert await _count(zx_conn, "zx_edge") == 1
    await _assert_no_hadamard_edges(zx_conn)
    await _assert_no_parallel_edges(zx_conn)
    await _assert_edge_links_match_vertex_types(zx_conn)


@pytest.mark.asyncio
async def test_zx_to_rg_simp_uses_euler_expansion_for_conflicting_boundary_component(zx_conn):
    h_boundary = await _add_vertex(zx_conn, IN, qubit=0, row=0)
    simple_boundary = await _add_vertex(zx_conn, OUT, qubit=1, row=0)
    z = await _add_vertex(zx_conn, Z, qubit=0, row=1)
    await _add_edge(zx_conn, h_boundary, z, HADAMARD)
    await _add_edge(zx_conn, simple_boundary, z, SIMPLE)

    await _call_rewrite(zx_conn, "zx_remove_h_edges")

    new_vertices = await _new_vertices(zx_conn, h_boundary, simple_boundary, z)
    assert len(new_vertices) == 2
    w2, w3 = new_vertices

    assert await _vertex_type(zx_conn, z) == Z
    assert await _vertex_type(zx_conn, w2) == X
    assert await _vertex_type(zx_conn, w3) == Z
    # The first Euler Z spider is fused into the existing Z endpoint.
    assert await _phase(zx_conn, z) == pytest.approx(0.5)
    assert await _phase(zx_conn, w2) == pytest.approx(0.5)
    assert await _phase(zx_conn, w3) == pytest.approx(0.5)

    await _assert_edge(zx_conn, simple_boundary, z, SIMPLE)
    await _assert_edge(zx_conn, h_boundary, w3, SIMPLE)
    await _assert_edge(zx_conn, w3, w2, SIMPLE)
    await _assert_edge(zx_conn, w2, z, SIMPLE)
    assert await _count(zx_conn, "zx_vertex") == 5
    assert await _count(zx_conn, "zx_edge") == 4
    await _assert_no_hadamard_edges(zx_conn)
    await _assert_no_parallel_edges(zx_conn)
    await _assert_no_self_loops(zx_conn)
    await _assert_edge_links_match_vertex_types(zx_conn)


@pytest.mark.asyncio
async def test_zx_to_rg_simp_uses_same_colour_euler_expansion_for_odd_h_cycle(zx_conn):
    z0 = await _add_vertex(zx_conn, Z, qubit=0, row=0)
    z1 = await _add_vertex(zx_conn, Z, qubit=0, row=1)
    z2 = await _add_vertex(zx_conn, Z, qubit=0, row=2)
    await _add_edge(zx_conn, z0, z1, HADAMARD)
    await _add_edge(zx_conn, z0, z2, HADAMARD)
    await _add_edge(zx_conn, z1, z2, HADAMARD)

    await _call_rewrite(zx_conn, "zx_remove_h_edges")

    new_vertices = await _new_vertices(zx_conn, z0, z1, z2)
    assert len(new_vertices) == 3
    assert await _vertex_type(zx_conn, z0) == Z
    assert await _vertex_type(zx_conn, z1) == Z
    assert await _vertex_type(zx_conn, z2) == Z

    for vertex_id in new_vertices:
        assert await _vertex_type(zx_conn, vertex_id) == X
        assert await _degree(zx_conn, vertex_id) == 2

    assert await _count(zx_conn, "zx_vertex") == 6
    assert await _count(zx_conn, "zx_edge") == 6
    await _assert_no_hadamard_edges(zx_conn)
    await _assert_no_parallel_edges(zx_conn)
    await _assert_no_self_loops(zx_conn)
    await _assert_edge_links_match_vertex_types(zx_conn)

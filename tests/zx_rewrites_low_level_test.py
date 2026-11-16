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
    if source_id > target_id:
        source_id, target_id = target_id, source_id
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


async def _vertex_exists(conn, vertex_id: int) -> bool:
    return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM zx_vertex WHERE id = $1)", vertex_id)


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


async def _assert_vertices_exist(conn, *vertex_ids: int) -> None:
    for vertex_id in vertex_ids:
        assert await _vertex_exists(conn, vertex_id), f"Expected vertex {vertex_id} to exist"


async def _assert_vertices_removed(conn, *vertex_ids: int) -> None:
    for vertex_id in vertex_ids:
        assert not await _vertex_exists(conn, vertex_id), f"Expected vertex {vertex_id} to be removed"


async def _assert_edge(conn, a: int, b: int, edge_type: int) -> None:
    assert await _edge_count_between(conn, a, b) == 1, f"Expected exactly one edge between {a} and {b}"
    assert await _edge_type_between(conn, a, b) == edge_type, f"Unexpected edge type between {a} and {b}"


async def _assert_no_edge(conn, a: int, b: int) -> None:
    assert await _edge_count_between(conn, a, b) == 0, f"Expected no edge between {a} and {b}"


async def _edge_set(conn) -> set[tuple[int, int, int]]:
    rows = await conn.fetch(
        """
        SELECT
            LEAST(get_id_from_link(source), get_id_from_link(target)) AS a,
            GREATEST(get_id_from_link(source), get_id_from_link(target)) AS b,
            type
        FROM zx_edge
        ORDER BY a, b, type
        """
    )
    return {(row["a"], row["b"], row["type"]) for row in rows}


async def _assert_edge_set(conn, expected: set[tuple[int, int, int]]) -> None:
    actual = await _edge_set(conn)
    assert actual == expected


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


async def _assert_no_edges_incident_to(conn, vertex_id: int) -> None:
    assert await conn.fetchval(
        """
        SELECT NOT EXISTS(
            SELECT 1
            FROM zx_edge
            WHERE get_id_from_link(source) = $1 OR get_id_from_link(target) = $1
        )
        """,
        vertex_id,
    )


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
async def test_zx_x_to_z_converts_vertex_and_all_incident_edges(zx_conn):
    x = await _add_vertex(zx_conn, X, phase=0.25)
    z_neighbor = await _add_vertex(zx_conn, Z)
    out_neighbor = await _add_vertex(zx_conn, OUT)
    await _add_edge(zx_conn, x, z_neighbor, SIMPLE)
    await _add_edge(zx_conn, x, out_neighbor, HADAMARD)

    await _call_rewrite(zx_conn, "zx_x_to_z")

    await _assert_vertices_exist(zx_conn, x, z_neighbor, out_neighbor)
    assert await _vertex_type(zx_conn, x) == Z
    assert await _phase(zx_conn, x) == pytest.approx(0.25)
    await _assert_edge(zx_conn, x, z_neighbor, HADAMARD)
    await _assert_edge(zx_conn, x, out_neighbor, SIMPLE)
    assert await _count(zx_conn, "zx_vertex", "type = $1", X) == 0
    assert await _count(zx_conn, "zx_vertex") == 3
    assert await _count(zx_conn, "zx_edge") == 2
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_id_simp_removes_zero_phase_degree_two_spider(zx_conn):
    left = await _add_vertex(zx_conn, IN, qubit=0, row=0)
    mid = await _add_vertex(zx_conn, Z, qubit=0, row=1)
    right = await _add_vertex(zx_conn, OUT, qubit=0, row=2)
    await _add_edge(zx_conn, left, mid, SIMPLE)
    await _add_edge(zx_conn, mid, right, SIMPLE)

    await _call_rewrite(zx_conn, "zx_id_simp")

    await _assert_vertices_removed(zx_conn, mid)
    await _assert_vertices_exist(zx_conn, left, right)
    await _assert_edge_set(zx_conn, {(left, right, SIMPLE)})
    assert await _count(zx_conn, "zx_vertex") == 2
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_id_simp_does_not_remove_nonzero_phase_or_wrong_degree(zx_conn):
    left = await _add_vertex(zx_conn, IN)
    phased = await _add_vertex(zx_conn, Z, phase=0.25)
    right = await _add_vertex(zx_conn, OUT)
    leaf = await _add_vertex(zx_conn, Z)
    await _add_edge(zx_conn, left, phased, SIMPLE)
    await _add_edge(zx_conn, phased, right, SIMPLE)
    await _add_edge(zx_conn, left, leaf, SIMPLE)

    await _call_rewrite(zx_conn, "zx_id_simp")

    await _assert_vertices_exist(zx_conn, left, phased, right, leaf)
    await _assert_edge(conn=zx_conn, a=left, b=phased, edge_type=SIMPLE)
    await _assert_edge(conn=zx_conn, a=phased, b=right, edge_type=SIMPLE)
    await _assert_edge(conn=zx_conn, a=left, b=leaf, edge_type=SIMPLE)
    assert await _count(zx_conn, "zx_vertex") == 4
    assert await _count(zx_conn, "zx_edge") == 3


@pytest.mark.asyncio
async def test_zx_remove_self_loops_removes_hadamard_loop_and_adds_pi_phase(zx_conn):
    z = await _add_vertex(zx_conn, Z, phase=0.25)
    neighbor = await _add_vertex(zx_conn, OUT)
    await _add_edge(zx_conn, z, z, HADAMARD)
    await _add_edge(zx_conn, z, neighbor, SIMPLE)

    await _call_rewrite(zx_conn, "zx_remove_self_loops")

    await _assert_vertices_exist(zx_conn, z, neighbor)
    assert await _phase(zx_conn, z) == pytest.approx(1.25)
    await _assert_edge_set(zx_conn, {(z, neighbor, SIMPLE)})


@pytest.mark.asyncio
async def test_zx_spider_simp_fuses_same_colour_simple_edge(zx_conn):
    z1 = await _add_vertex(zx_conn, Z, phase=0.25)
    z2 = await _add_vertex(zx_conn, Z, phase=0.5)
    out = await _add_vertex(zx_conn, OUT)
    other = await _add_vertex(zx_conn, IN)
    await _add_edge(zx_conn, z1, z2, SIMPLE)
    await _add_edge(zx_conn, z2, out, SIMPLE)
    await _add_edge(zx_conn, z1, other, HADAMARD)

    await _call_rewrite(zx_conn, "zx_spider_simp")

    await _assert_vertices_removed(zx_conn, z2)
    await _assert_vertices_exist(zx_conn, z1, out, other)
    assert await _phase(zx_conn, z1) == pytest.approx(0.75)
    await _assert_edge_set(zx_conn, {(z1, out, SIMPLE), (z1, other, HADAMARD)})
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_spider_simp_does_not_fuse_different_colours_or_hadamard_edge(zx_conn):
    z = await _add_vertex(zx_conn, Z, phase=0.25)
    x = await _add_vertex(zx_conn, X, phase=0.5)
    z_h = await _add_vertex(zx_conn, Z, phase=0.75)
    await _add_edge(zx_conn, z, x, SIMPLE)
    await _add_edge(zx_conn, z, z_h, HADAMARD)

    await _call_rewrite(zx_conn, "zx_spider_simp")

    await _assert_vertices_exist(zx_conn, z, x, z_h)
    assert await _phase(zx_conn, z) == pytest.approx(0.25)
    assert await _phase(zx_conn, x) == pytest.approx(0.5)
    assert await _phase(zx_conn, z_h) == pytest.approx(0.75)
    await _assert_edge(conn=zx_conn, a=z, b=x, edge_type=SIMPLE)
    await _assert_edge(conn=zx_conn, a=z, b=z_h, edge_type=HADAMARD)


@pytest.mark.asyncio
async def test_zx_lcomp_simp_removes_pi_over_two_spider_and_complements_neighborhood(zx_conn):
    center = await _add_vertex(zx_conn, Z, phase=0.5)
    n1 = await _add_vertex(zx_conn, Z)
    n2 = await _add_vertex(zx_conn, Z)
    n3 = await _add_vertex(zx_conn, Z)
    g1 = await _add_vertex(zx_conn, X)
    g2 = await _add_vertex(zx_conn, X)
    g3 = await _add_vertex(zx_conn, X)

    for neighbor, guard in ((n1, g1), (n2, g2), (n3, g3)):
        await _add_edge(zx_conn, center, neighbor, HADAMARD)
        await _add_edge(zx_conn, neighbor, guard, HADAMARD)

    await _call_rewrite(zx_conn, "zx_lcomp_simp")

    await _assert_vertices_removed(zx_conn, center)
    await _assert_vertices_exist(zx_conn, n1, n2, n3, g1, g2, g3)
    await _assert_no_edges_incident_to(zx_conn, center)
    for neighbor in (n1, n2, n3):
        assert await _phase(zx_conn, neighbor) == pytest.approx(1.5)

    expected = {
        (min(n1, g1), max(n1, g1), HADAMARD),
        (min(n2, g2), max(n2, g2), HADAMARD),
        (min(n3, g3), max(n3, g3), HADAMARD),
        (min(n1, n2), max(n1, n2), HADAMARD),
        (min(n1, n3), max(n1, n3), HADAMARD),
        (min(n2, n3), max(n2, n3), HADAMARD),
    }
    await _assert_edge_set(zx_conn, expected)
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_lcomp_simp_toggles_existing_neighbor_edges_off(zx_conn):
    center = await _add_vertex(zx_conn, Z, phase=0.5)
    n1 = await _add_vertex(zx_conn, Z)
    n2 = await _add_vertex(zx_conn, Z)
    await _add_edge(zx_conn, center, n1, HADAMARD)
    await _add_edge(zx_conn, center, n2, HADAMARD)
    await _add_edge(zx_conn, n1, n2, HADAMARD)

    await _call_rewrite(zx_conn, "zx_lcomp_simp")

    await _assert_vertices_removed(zx_conn, center)
    await _assert_vertices_exist(zx_conn, n1, n2)
    await _assert_no_edge(zx_conn, n1, n2)
    assert await _count(zx_conn, "zx_edge") == 0


@pytest.mark.asyncio
async def test_zx_pivot_simp_removes_pivot_pair_and_toggles_neighbor_edge(zx_conn):
    v0 = await _add_vertex(zx_conn, Z)
    v1 = await _add_vertex(zx_conn, Z)
    n0 = await _add_vertex(zx_conn, Z)
    n1 = await _add_vertex(zx_conn, Z)
    g0 = await _add_vertex(zx_conn, OUT, qubit=0, row=10)
    g1 = await _add_vertex(zx_conn, OUT, qubit=1, row=10)

    await _add_edge(zx_conn, v0, v1, HADAMARD)
    await _add_edge(zx_conn, v0, n0, HADAMARD)
    await _add_edge(zx_conn, v1, n1, HADAMARD)
    await _add_edge(zx_conn, n0, g0, SIMPLE)
    await _add_edge(zx_conn, n1, g1, SIMPLE)

    await _call_rewrite(zx_conn, "zx_pivot_simp")

    await _assert_vertices_removed(zx_conn, v0, v1)
    await _assert_vertices_exist(zx_conn, n0, n1, g0, g1)
    await _assert_no_edges_incident_to(zx_conn, v0)
    await _assert_no_edges_incident_to(zx_conn, v1)
    expected = {
        (min(n0, n1), max(n0, n1), HADAMARD),
        (min(n0, g0), max(n0, g0), SIMPLE),
        (min(n1, g1), max(n1, g1), SIMPLE),
    }
    await _assert_edge_set(zx_conn, expected)
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_pivot_simp_toggles_existing_cross_edge_off(zx_conn):
    v0 = await _add_vertex(zx_conn, Z)
    v1 = await _add_vertex(zx_conn, Z)
    n0 = await _add_vertex(zx_conn, Z)
    n1 = await _add_vertex(zx_conn, Z)
    await _add_edge(zx_conn, v0, v1, HADAMARD)
    await _add_edge(zx_conn, v0, n0, HADAMARD)
    await _add_edge(zx_conn, v1, n1, HADAMARD)
    await _add_edge(zx_conn, n0, n1, HADAMARD)

    await _call_rewrite(zx_conn, "zx_pivot_simp")

    await _assert_vertices_removed(zx_conn, v0, v1)
    await _assert_vertices_exist(zx_conn, n0, n1)
    await _assert_no_edge(zx_conn, n0, n1)
    assert await _count(zx_conn, "zx_edge") == 0


@pytest.mark.asyncio
async def test_zx_pivot_boundary_simp_has_exact_boundary_topology_and_gadget_phases(zx_conn):
    v = await _add_vertex(zx_conn, Z)
    w = await _add_vertex(zx_conn, Z, phase=0.25, row=1)
    b = await _add_vertex(zx_conn, OUT, qubit=0, row=2)
    await _add_edge(zx_conn, v, w, HADAMARD)
    await _add_edge(zx_conn, w, b, HADAMARD)

    await _call_rewrite(zx_conn, "zx_pivot_boundary_simp")

    await _assert_vertices_removed(zx_conn, w)
    await _assert_vertices_exist(zx_conn, v, b)
    assert await _phase(zx_conn, v) == pytest.approx(0.0)
    await _assert_edge(zx_conn, v, b, SIMPLE)

    gadget_phase = await conn_fetch_single_vertex_id_by(zx_conn, "qubit = -2")
    gadget_axel = await conn_fetch_single_vertex_id_by(zx_conn, "qubit = -1")
    assert await _vertex_type(zx_conn, gadget_phase) == Z
    assert await _vertex_type(zx_conn, gadget_axel) == Z
    assert await _phase(zx_conn, gadget_phase) == pytest.approx(0.25)
    assert await _phase(zx_conn, gadget_axel) == pytest.approx(0.0)

    await _assert_vertices_exist(zx_conn, gadget_phase, gadget_axel)
    assert await _count(zx_conn, "zx_vertex") == 4
    assert await _count(zx_conn, "zx_edge") == 2
    await _assert_edge(zx_conn, v, b, SIMPLE)
    # The second edge is implementation-specific but must be the generated gadget connection.
    assert await _edge_count_between(zx_conn, gadget_phase, gadget_axel) == 1
    await _assert_no_parallel_edges(zx_conn)


async def conn_fetch_single_vertex_id_by(conn, where: str, *args) -> int:
    rows = await conn.fetch(f"SELECT id FROM zx_vertex WHERE {where}", *args)
    assert len(rows) == 1, f"Expected exactly one vertex matching: {where}; got {len(rows)}"
    return rows[0]["id"]


@pytest.mark.asyncio
async def test_zx_pivot_gadget_simp_creates_single_non_clifford_gadget(zx_conn):
    v0 = await _add_vertex(zx_conn, Z)
    v1 = await _add_vertex(zx_conn, Z, phase=0.25)
    n = await _add_vertex(zx_conn, Z)
    await _add_edge(zx_conn, v0, v1, HADAMARD)
    await _add_edge(zx_conn, v1, n, HADAMARD)

    await _call_rewrite(zx_conn, "zx_pivot_gadget_simp")

    await _assert_vertices_removed(zx_conn, v1)
    await _assert_vertices_exist(zx_conn, v0, n)
    assert await _count(zx_conn, "zx_vertex", "type = $1 AND NOT zx_phase_is_clifford(param)", Z) == 1
    non_clifford = await conn_fetch_single_vertex_id_by(zx_conn, "type = $1 AND NOT zx_phase_is_clifford(param)", Z)
    assert await _phase(zx_conn, non_clifford) == pytest.approx(0.25)
    assert await _degree(zx_conn, non_clifford) == 1
    assert await _count(zx_conn, "zx_vertex", "qubit = -2") == 1
    assert await _count(zx_conn, "zx_vertex") == 3
    assert await _count(zx_conn, "zx_edge") == 1

    # The implementation represents the extracted non-Clifford phase as a
    # single degree-1 gadget. The remaining edge must be incident to that
    # gadget, but the concrete neighbor is an implementation detail.
    assert await _count(
        zx_conn,
        "zx_edge",
        "get_id_from_link(source) = $1 OR get_id_from_link(target) = $1",
        non_clifford,
    ) == 1
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_gadget_simp_merges_equal_phase_gadgets_exactly(zx_conn):
    target = await _add_vertex(zx_conn, Z)
    axel_a = await _add_vertex(zx_conn, Z)
    axel_b = await _add_vertex(zx_conn, Z)
    leaf_a = await _add_vertex(zx_conn, Z, phase=0.25)
    leaf_b = await _add_vertex(zx_conn, Z, phase=0.25)

    await _add_edge(zx_conn, axel_a, target, HADAMARD)
    await _add_edge(zx_conn, axel_b, target, HADAMARD)
    await _add_edge(zx_conn, leaf_a, axel_a, SIMPLE)
    await _add_edge(zx_conn, leaf_b, axel_b, SIMPLE)

    await _call_rewrite(zx_conn, "zx_gadget_simp")

    await _assert_vertices_exist(zx_conn, target)
    assert await _count(zx_conn, "zx_vertex") == 3
    merged_leaf = await conn_fetch_single_vertex_id_by(
        zx_conn,
        "type = $1 AND ABS(COALESCE(param, 0::real) - 0.5) < 1e-6 AND zx_edge_degree(id) = 1",
        Z,
    )
    merged_axel = await conn_fetch_single_vertex_id_by(
        zx_conn,
        "type = $1 AND ABS(COALESCE(param, 0::real)) < 1e-6 AND zx_edge_degree(id) = 2 AND id <> $2",
        Z,
        target,
    )
    await _assert_edge(zx_conn, merged_leaf, merged_axel, SIMPLE)
    await _assert_edge(zx_conn, merged_axel, target, HADAMARD)
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_gadget_simp_does_not_merge_different_targets_or_phases(zx_conn):
    target_a = await _add_vertex(zx_conn, Z)
    target_b = await _add_vertex(zx_conn, Z)
    axel_a = await _add_vertex(zx_conn, Z)
    axel_b = await _add_vertex(zx_conn, Z)
    leaf_a = await _add_vertex(zx_conn, Z, phase=0.25)
    leaf_b = await _add_vertex(zx_conn, Z, phase=0.5)

    await _add_edge(zx_conn, axel_a, target_a, HADAMARD)
    await _add_edge(zx_conn, axel_b, target_b, HADAMARD)
    await _add_edge(zx_conn, leaf_a, axel_a, SIMPLE)
    await _add_edge(zx_conn, leaf_b, axel_b, SIMPLE)

    await _call_rewrite(zx_conn, "zx_gadget_simp")

    await _assert_vertices_exist(zx_conn, target_a, target_b, axel_a, axel_b, leaf_a, leaf_b)
    assert await _count(zx_conn, "zx_vertex") == 6
    assert await _count(zx_conn, "zx_edge") == 4


@pytest.mark.asyncio
async def test_zx_copy_simp_copies_pi_phase_spider_to_each_neighbor_exactly(zx_conn):
    v = await _add_vertex(zx_conn, Z, phase=1.0)
    w = await _add_vertex(zx_conn, X)
    n1 = await _add_vertex(zx_conn, X)
    n2 = await _add_vertex(zx_conn, Z)

    await _add_edge(zx_conn, v, w, SIMPLE)
    await _add_edge(zx_conn, w, n1, HADAMARD)
    await _add_edge(zx_conn, w, n2, SIMPLE)

    await _call_rewrite(zx_conn, "zx_copy_simp")

    await _assert_vertices_removed(zx_conn, v, w)
    await _assert_vertices_exist(zx_conn, n1, n2)
    await _assert_no_edges_incident_to(zx_conn, v)
    await _assert_no_edges_incident_to(zx_conn, w)
    assert await _count(zx_conn, "zx_vertex") == 4
    copied = await conn_fetch_vertices_by(
        zx_conn,
        "id NOT IN ($1, $2, $3, $4) AND type = $5 AND ABS(COALESCE(param, 0::real) - 1.0) < 1e-6",
        v,
        w,
        n1,
        n2,
        Z,
    )
    assert len(copied) == 2
    for copied_vertex in copied:
        assert await _degree(zx_conn, copied_vertex) == 1
    assert await _edge_count_between(zx_conn, n1, copied[0]) + await _edge_count_between(zx_conn, n1, copied[1]) == 1
    assert await _edge_count_between(zx_conn, n2, copied[0]) + await _edge_count_between(zx_conn, n2, copied[1]) == 1
    await _assert_no_edge(zx_conn, n1, n2)
    await _assert_no_parallel_edges(zx_conn)


async def conn_fetch_vertices_by(conn, where: str, *args) -> list[int]:
    rows = await conn.fetch(f"SELECT id FROM zx_vertex WHERE {where} ORDER BY id", *args)
    return [row["id"] for row in rows]


@pytest.mark.asyncio
async def test_zx_copy_simp_does_not_fire_without_opposite_color_center(zx_conn):
    v = await _add_vertex(zx_conn, Z, phase=0.5)
    same_color_center = await _add_vertex(zx_conn, Z)
    n = await _add_vertex(zx_conn, X)
    await _add_edge(zx_conn, v, same_color_center, HADAMARD)
    await _add_edge(zx_conn, same_color_center, n, HADAMARD)

    await _call_rewrite(zx_conn, "zx_copy_simp")

    await _assert_vertices_exist(zx_conn, v, same_color_center, n)
    assert await _phase(zx_conn, v) == pytest.approx(0.5)
    assert await _count(zx_conn, "zx_vertex") == 3
    await _assert_edge_set(
        zx_conn,
        {
            (v, same_color_center, HADAMARD),
            (same_color_center, n, HADAMARD),
        },
    )
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_supplementarity_simp_removes_supplementary_pair_and_updates_common_neighbors(zx_conn):
    anchor_in = await _add_vertex(zx_conn, IN, qubit=0, row=0)
    anchor_out = await _add_vertex(zx_conn, OUT, qubit=1, row=0)
    a = await _add_vertex(zx_conn, Z)
    b = await _add_vertex(zx_conn, Z)
    v = await _add_vertex(zx_conn, Z, phase=0.25)
    w = await _add_vertex(zx_conn, Z, phase=0.75)

    await _add_edge(zx_conn, anchor_in, a, SIMPLE)
    await _add_edge(zx_conn, anchor_out, b, SIMPLE)
    await _add_edge(zx_conn, v, a, HADAMARD)
    await _add_edge(zx_conn, v, b, HADAMARD)
    await _add_edge(zx_conn, w, a, HADAMARD)
    await _add_edge(zx_conn, w, b, HADAMARD)

    await _call_rewrite(zx_conn, "zx_supplementarity_simp")

    await _assert_vertices_removed(zx_conn, v, w)
    await _assert_vertices_exist(zx_conn, anchor_in, anchor_out, a, b)
    await _assert_no_edges_incident_to(zx_conn, v)
    await _assert_no_edges_incident_to(zx_conn, w)
    assert await _phase(zx_conn, a) == pytest.approx(1.0)
    assert await _phase(zx_conn, b) == pytest.approx(1.0)
    await _assert_edge_set(
        zx_conn,
        {
            (min(anchor_in, a), max(anchor_in, a), SIMPLE),
            (min(anchor_out, b), max(anchor_out, b), SIMPLE),
        },
    )
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_supplementarity_simp_does_not_fire_without_matching_neighbors_or_supplementary_phases(zx_conn):
    a = await _add_vertex(zx_conn, Z)
    b = await _add_vertex(zx_conn, Z)
    c = await _add_vertex(zx_conn, Z)
    v = await _add_vertex(zx_conn, Z, phase=0.25)
    w = await _add_vertex(zx_conn, Z, phase=0.5)

    await _add_edge(zx_conn, v, a, HADAMARD)
    await _add_edge(zx_conn, v, b, HADAMARD)
    await _add_edge(zx_conn, w, a, HADAMARD)
    await _add_edge(zx_conn, w, c, HADAMARD)

    await _call_rewrite(zx_conn, "zx_supplementarity_simp")

    await _assert_vertices_exist(zx_conn, a, b, c, v, w)
    assert await _phase(zx_conn, v) == pytest.approx(0.25)
    assert await _phase(zx_conn, w) == pytest.approx(0.5)
    assert await _count(zx_conn, "zx_vertex") == 5
    assert await _count(zx_conn, "zx_edge") == 4
    await _assert_no_parallel_edges(zx_conn)


# ---------------------------------------------------------------------------
# Fault-equivalent rewrites
# ---------------------------------------------------------------------------


async def _neighbors(conn, vertex_id: int) -> set[int]:
    rows = await conn.fetch(
        """
        SELECT get_id_from_link(target) AS other FROM zx_edge WHERE get_id_from_link(source) = $1
        UNION ALL
        SELECT get_id_from_link(source) AS other FROM zx_edge WHERE get_id_from_link(target) = $1
        """,
        vertex_id,
    )
    return {row["other"] for row in rows}


async def _spider_ids(conn) -> list[int]:
    rows = await conn.fetch(
        "SELECT id FROM zx_vertex WHERE type IN ($1, $2) ORDER BY id", Z, X
    )
    return [row["id"] for row in rows]


# --- Fuse-4_fe -------------------------------------------------------------

async def _degree4_spider_with_boundaries(conn, colour: int) -> tuple[int, list[int]]:
    v = await _add_vertex(conn, colour)
    legs = [await _add_vertex(conn, IN if i // 2 == 0 else OUT, row=0 if i // 2 == 0 else 2) for i in range(4)]
    for leg in legs:
        await _add_edge(conn, v, leg, SIMPLE)
    return v, legs

@pytest.mark.asyncio
async def test_zx_fuse4_fe_expand_builds_ring(zx_conn):
    v, legs = await _degree4_spider_with_boundaries(zx_conn, Z)

    await _call_rewrite(zx_conn, "zx_fuse4_fe_expand")

    # Original spider gone; four degree-3 ring spiders, four boundaries.
    assert not await _vertex_exists(zx_conn, v)
    assert await _count(zx_conn, "zx_vertex") == 8
    # 4 ring edges + 4 external legs.
    assert await _count(zx_conn, "zx_edge") == 8
    ring = await _spider_ids(zx_conn)
    assert len(ring) == 4
    for r in ring:
        assert await _degree(zx_conn, r) == 3
    for leg in legs:
        assert await _degree(zx_conn, leg) == 1
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_fuse4_fe_roundtrip_expand_then_simp(zx_conn):
    v, legs = await _degree4_spider_with_boundaries(zx_conn, Z)

    await _call_rewrite(zx_conn, "zx_fuse4_fe_expand")
    await _call_rewrite(zx_conn, "zx_fuse4_fe_simp")

    assert await _count(zx_conn, "zx_vertex") == 5
    spiders = await _spider_ids(zx_conn)
    assert len(spiders) == 1
    assert await _degree(zx_conn, spiders[0]) == 4
    assert await _neighbors(zx_conn, spiders[0]) == set(legs)
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_fuse4_fe_roundtrip_x_spider(zx_conn):
    v, legs = await _degree4_spider_with_boundaries(zx_conn, X)

    await _call_rewrite(zx_conn, "zx_fuse4_fe_expand")
    ring = await _spider_ids(zx_conn)
    for r in ring:
        assert (await _vertex_type(zx_conn, r)) == X

    await _call_rewrite(zx_conn, "zx_fuse4_fe_simp")
    spiders = await _spider_ids(zx_conn)
    assert len(spiders) == 1
    assert await _vertex_type(zx_conn, spiders[0]) == X
    assert await _neighbors(zx_conn, spiders[0]) == set(legs)


# --- Fuse-n_fe -------------------------------------------------------------


@pytest.mark.asyncio
async def test_zx_fusen_fe_expand_builds_hub_gadget(zx_conn):
    # 2n = 6 (n = 3).
    v = await _add_vertex(zx_conn, Z)
    legs = [await _add_vertex(zx_conn, IN if i % 2 == 0 else OUT, row=0 if i % 2 == 0 else 2) for i in range(6)]
    for leg in legs:
        await _add_edge(zx_conn, v, leg, SIMPLE)

    await _call_rewrite(zx_conn, "zx_fusen_fe_expand")

    assert not await _vertex_exists(zx_conn, v)
    # 2 hubs + 2n column spiders = 8 spiders, + 6 boundaries = 14 vertices.
    assert await _count(zx_conn, "zx_vertex") == 14
    # 3n internal + 2n external = 9 + 6 = 15 edges.
    assert await _count(zx_conn, "zx_edge") == 15
    spiders = await _spider_ids(zx_conn)
    assert len(spiders) == 8
    hubs = [s for s in spiders if await _degree(zx_conn, s) == 3 and not (await _neighbors(zx_conn, s) & set(legs))]
    # Two hubs are the only spiders with no boundary neighbour.
    assert len(hubs) == 2
    await _assert_no_parallel_edges(zx_conn)


@pytest.mark.asyncio
async def test_zx_fusen_fe_roundtrip_expand_then_simp(zx_conn):
    v = await _add_vertex(zx_conn, Z)
    legs = [await _add_vertex(zx_conn, IN if i % 2 == 0 else OUT, row=0 if i % 2 == 0 else 2) for i in range(6)]
    for leg in legs:
        await _add_edge(zx_conn, v, leg, SIMPLE)

    await _call_rewrite(zx_conn, "zx_fusen_fe_expand")
    await _call_rewrite(zx_conn, "zx_fusen_fe_simp")

    assert await _count(zx_conn, "zx_vertex") == 7
    spiders = await _spider_ids(zx_conn)
    assert len(spiders) == 1
    assert await _degree(zx_conn, spiders[0]) == 6
    assert await _neighbors(zx_conn, spiders[0]) == set(legs)
    await _assert_no_parallel_edges(zx_conn)

# --- Pi-Copy_fe -------------------------------------------------------------


@pytest.mark.asyncio
async def test_zx_pi_copy_simp_degree2_regular_edge_preserves_edge_types(zx_conn):
    center = await _add_vertex(zx_conn, Z, phase=0.5)
    pi = await _add_vertex(zx_conn, X, phase=1.0)
    outside = await _add_vertex(zx_conn, IN, row=0)
    simple_leg = await _add_vertex(zx_conn, OUT, row=2)
    hadamard_leg = await _add_vertex(zx_conn, OUT, row=2)

    await _add_edge(zx_conn, outside, pi, SIMPLE)
    await _add_edge(zx_conn, pi, center, SIMPLE)
    await _add_edge(zx_conn, center, simple_leg, SIMPLE)
    await _add_edge(zx_conn, center, hadamard_leg, HADAMARD)

    await _call_rewrite(zx_conn, "zx_pi_copy_simp")

    await _assert_vertices_removed(zx_conn, pi)
    await _assert_vertices_exist(zx_conn, center, outside, simple_leg, hadamard_leg)
    assert await _phase(zx_conn, center) == pytest.approx(-0.5)

    assert await _count(zx_conn, "zx_vertex") == 6
    assert await _count(zx_conn, "zx_edge") == 5

    await _assert_edge(zx_conn, center, outside, SIMPLE)

    copied = [s for s in await _spider_ids(zx_conn) if s != center]
    assert len(copied) == 2

    outward_edges = {}
    for copied_pi in copied:
        assert await _vertex_type(zx_conn, copied_pi) == X
        assert await _phase(zx_conn, copied_pi) == pytest.approx(1.0)
        assert await _degree(zx_conn, copied_pi) == 2

        await _assert_edge(zx_conn, center, copied_pi, SIMPLE)

        old_leg = ((await _neighbors(zx_conn, copied_pi)) - {center}).pop()
        outward_edges[old_leg] = await _edge_type_between(zx_conn, copied_pi, old_leg)

    assert outward_edges == {
        simple_leg: SIMPLE,
        hadamard_leg: HADAMARD,
    }

    await _assert_no_parallel_edges(zx_conn)

@pytest.mark.asyncio
async def test_zx_pi_copy_simp_two_matches_second_invalidated_by_first_rewrite(zx_conn):
    center = await _add_vertex(zx_conn, Z, phase=0.5)

    pi_a = await _add_vertex(zx_conn, X, phase=1.0)
    pi_b = await _add_vertex(zx_conn, X, phase=1.0)

    outside_a = await _add_vertex(zx_conn, IN, row=0)
    outside_b = await _add_vertex(zx_conn, OUT, row=2)

    # Shape:
    #
    #   outside_a --S-- pi_a(pi) --S-- center(alpha) --S-- pi_b(pi) --S-- outside_b
    #
    # Both pi_a and pi_b are initially suitable degree-2 pi-copy sites.
    # Rewriting either one splits the center edge to the other, so the second
    # initially queued match must not be applied from a stale binding.
    await _add_edge(zx_conn, outside_a, pi_a, SIMPLE)
    await _add_edge(zx_conn, pi_a, center, SIMPLE)
    await _add_edge(zx_conn, center, pi_b, SIMPLE)
    await _add_edge(zx_conn, pi_b, outside_b, SIMPLE)

    await _call_rewrite(zx_conn, "zx_pi_copy_simp")

    current_spiders = set(await _spider_ids(zx_conn))

    original_pis = {pi_a, pi_b}
    surviving_original_pis = original_pis & current_spiders
    removed_original_pis = original_pis - current_spiders

    assert len(surviving_original_pis) == 1
    assert len(removed_original_pis) == 1

    surviving_pi = surviving_original_pis.pop()
    removed_pi = removed_original_pis.pop()

    removed_outside = outside_a if removed_pi == pi_a else outside_b
    surviving_outside = outside_b if surviving_pi == pi_b else outside_a

    await _assert_vertices_removed(zx_conn, removed_pi)
    await _assert_vertices_exist(zx_conn, center, surviving_pi, outside_a, outside_b)

    # Only one rewrite should have been applied. If the stale second match is
    # also applied, this phase will usually be changed twice.
    assert await _phase(zx_conn, center) == pytest.approx(-0.5)

    # One original pi is removed and one copied pi is inserted, so the total
    # counts stay the same.
    assert await _count(zx_conn, "zx_vertex") == 5
    assert await _count(zx_conn, "zx_edge") == 4

    # The rewritten side is now connected directly to the center.
    await _assert_edge(zx_conn, center, removed_outside, SIMPLE)

    # The other original pi was not rewritten from a stale match. Instead, the
    # first rewrite split its old center edge by inserting a copied pi spider.
    copied = current_spiders - {center, surviving_pi}
    assert len(copied) == 1

    copied_pi = copied.pop()
    assert copied_pi not in original_pis

    assert await _vertex_type(zx_conn, copied_pi) == X
    assert await _phase(zx_conn, copied_pi) == pytest.approx(1.0)
    assert await _degree(zx_conn, copied_pi) == 2

    assert await _vertex_type(zx_conn, surviving_pi) == X
    assert await _phase(zx_conn, surviving_pi) == pytest.approx(1.0)
    assert await _degree(zx_conn, surviving_pi) == 2

    await _assert_edge(zx_conn, center, copied_pi, SIMPLE)
    await _assert_edge(zx_conn, copied_pi, surviving_pi, SIMPLE)
    await _assert_edge(zx_conn, surviving_pi, surviving_outside, SIMPLE)

    # The old center-surviving_pi edge must have been split. This is the side
    # effect that invalidates the second initially discovered match.
    assert center not in await _neighbors(zx_conn, surviving_pi)

    await _assert_no_parallel_edges(zx_conn)
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
Z = PandoraGateTranslator.Z_SPIDER.value
X = PandoraGateTranslator.X_SPIDER.value

# Priors and check-node scaling are derived from each spider's phase inside
# zx_bp_min_sum (see the SQL). Phase 0 is Pauli, phase 0.5 is not.
PAULI_PRIOR = 10e-3
NON_PAULI_PRIOR = 10e-2
PAULI_SCALING = 0.6
NON_PAULI_SCALING = 1.0

PAULI_PHASE = 0.0
NON_PAULI_PHASE = 0.5


def _expected_check_value(prior: float, scaling: float, max_iter: int) -> float:
    """Closed form for the symmetric K(2,2) diagram.

    By symmetry every variable -> check message stays equal; call it ``a``. It
    starts at the prior, and each iteration the check update scales the single
    peer message by ``scaling`` while the variable update adds the prior back:

        a_0 = prior
        a_k = prior + scaling * a_{k-1}

    Each check ends by summing its two incoming messages, so the check value is
    ``2 * a_maxiter``.
    """
    a = prior
    for _ in range(max_iter):
        a = prior + scaling * a
    return 2 * a


async def _add_vertex(conn, vtype: int, *, phase: float = 0.0, qubit: int = 0, row: int = 0) -> int:
    return await conn.fetchval(
        "INSERT INTO zx_vertex(type, qubit, row, param) VALUES($1, $2, $3, $4) RETURNING id",
        vtype, qubit, row, phase,
    )


async def _edge(conn, a: int, b: int, edge_type: int = SIMPLE) -> int:
    lo, hi = (a, b) if a < b else (b, a)
    return await conn.fetchval(
        "INSERT INTO zx_edge(type, source, target) VALUES($1, zx_vertex_ref($2), zx_vertex_ref($3)) RETURNING id",
        edge_type, lo, hi,
    )


async def _run_bp(
    conn,
    *,
    max_iter: int = 10,
    variable_type: int = X,
) -> dict:
    """Run the fixed-iteration min-sum and read the check values.

    Priors are derived from the vertex phases inside the procedure, so there is
    nothing to seed here.
    """
    await conn.execute(
        "CALL zx_bp_min_sum($1::int, $2::smallint)",
        max_iter, variable_type,
    )
    check_values = await conn.fetch(
        "SELECT vertex_id, value FROM zx_bp_check_value ORDER BY vertex_id"
    )
    return {
        "check_values": {c["vertex_id"]: c["value"] for c in check_values},
    }


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


async def _k22(conn, *, var_phase: float = PAULI_PHASE, check_phase: float = PAULI_PHASE):
    """Complete bipartite K(2,2): X variables v0,v1 ; Z checks c0,c1 (all four edges).

    With the default X-variable / Z-check mapping the variable phases fix the
    prior and the check phases fix the check-node scaling. Symmetry keeps every
    variable -> check message equal, so each check value follows
    ``_expected_check_value``.
    """
    v0 = await _add_vertex(conn, X, phase=var_phase, qubit=0)
    v1 = await _add_vertex(conn, X, phase=var_phase, qubit=1)
    c0 = await _add_vertex(conn, Z, phase=check_phase, qubit=2)
    c1 = await _add_vertex(conn, Z, phase=check_phase, qubit=3)
    for v in (v0, v1):
        for c in (c0, c1):
            await _edge(conn, v, c)
    return v0, v1, c0, c1


@pytest.mark.asyncio
async def test_runs_a_fixed_number_of_iterations(zx_conn):
    _, _, c0, c1 = await _k22(zx_conn)
    max_iter = 7

    result = await _run_bp(zx_conn, max_iter=max_iter)

    expected = _expected_check_value(PAULI_PRIOR, PAULI_SCALING, max_iter)
    assert result["check_values"][c0] == pytest.approx(expected)
    assert result["check_values"][c1] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_check_values_only_cover_check_nodes(zx_conn):
    v0, v1, c0, c1 = await _k22(zx_conn)

    result = await _run_bp(zx_conn)

    # Only the Z (check) spiders get a value; the X (variable) spiders do not.
    assert set(result["check_values"].keys()) == {c0, c1}


@pytest.mark.asyncio
async def test_pauli_phase_uses_small_prior_and_0_6_scaling(zx_conn):
    # All spiders have phase 0 (Pauli): variable prior 10e-3, check scaling 0.6.
    v0, v1, c0, c1 = await _k22(zx_conn)
    max_iter = 10

    result = await _run_bp(zx_conn, max_iter=max_iter)

    expected = _expected_check_value(PAULI_PRIOR, PAULI_SCALING, max_iter)
    assert result["check_values"][c0] == pytest.approx(expected)
    assert result["check_values"][c1] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_non_pauli_phase_uses_large_prior_and_no_scaling(zx_conn):
    # Non-Pauli spiders (phase 0.5): variable prior 10e-2, check scaling 1.
    v0, v1, c0, c1 = await _k22(
        zx_conn, var_phase=NON_PAULI_PHASE, check_phase=NON_PAULI_PHASE
    )
    max_iter = 10

    result = await _run_bp(zx_conn, max_iter=max_iter)

    expected = _expected_check_value(NON_PAULI_PRIOR, NON_PAULI_SCALING, max_iter)
    assert result["check_values"][c0] == pytest.approx(expected)
    assert result["check_values"][c1] == pytest.approx(expected)
    # Unscaled accumulation from the larger prior aggregates past 0.5.
    assert max(result["check_values"].values()) > 0.5


@pytest.mark.asyncio
async def test_check_values_accumulate_with_iterations(zx_conn):
    v0, v1, c0, c1 = await _k22(zx_conn)

    few = await _run_bp(zx_conn, max_iter=1)
    many = await _run_bp(zx_conn, max_iter=10)

    # More iterations aggregate more belief at each check.
    assert many["check_values"][c0] > few["check_values"][c0]
    assert many["check_values"][c1] > few["check_values"][c1]


@pytest.mark.asyncio
async def test_variable_type_selects_the_other_colour_as_checks(zx_conn):
    v0, v1, c0, c1 = await _k22(zx_conn)

    # Flip the mapping: treat Z as variables, so the X spiders become the checks.
    result = await _run_bp(zx_conn, variable_type=Z)

    assert set(result["check_values"].keys()) == {v0, v1}

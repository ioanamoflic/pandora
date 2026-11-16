-- Apply a pivot on v0/v1: complement the edges between the three neighbour sets, fold the pivot phases into the neighbours, and remove the pivoted vertices.
CREATE OR REPLACE PROCEDURE _zx_apply_pivot(
    p_v0_id bigint,
    p_v1_id bigint,
    p_b1_id bigint,
    p_v0_phase double precision,
    p_v1_phase double precision
)
LANGUAGE plpgsql
AS $$
DECLARE
    v0_phase double precision := p_v0_phase;
    v1_phase double precision := p_v1_phase;

    vertices_to_remove bigint[] := ARRAY[p_v1_id]::bigint[];
    retained_edge_id bigint;
    retained_edge_type smallint;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS zx_pivot_neighbors (
        id bigint PRIMARY KEY,
        type smallint NOT NULL,
        set smallint NOT NULL -- 0 = neighbours of v0, 1 = neighbours of v1, 2 = common
    ) ON COMMIT DROP;

    CREATE TEMP TABLE IF NOT EXISTS zx_pending_edges (
        a_id bigint,
        a_type smallint,
        b_id bigint,
        b_type smallint,
        n_regular smallint NOT NULL CHECK (n_regular IN (0, 1)),
        n_had smallint NOT NULL CHECK (n_had IN (0, 1)),
        PRIMARY KEY (a_id, b_id)
    ) ON COMMIT DROP;

    TRUNCATE zx_pivot_neighbors;
    TRUNCATE zx_pending_edges;

    INSERT INTO zx_pivot_neighbors(id, type, set)
    WITH incidents AS (
        SELECT ie.other_id, ie.other_type, 0 AS side
            FROM zx_incident_edges(p_v0_id) AS ie
            WHERE ie.other_id <> p_v1_id
        UNION ALL
        SELECT ie.other_id, ie.other_type, 1 AS side
            FROM zx_incident_edges(p_v1_id) AS ie
            WHERE ie.other_id <> p_v0_id
                AND (p_b1_id IS NULL OR ie.other_id <> p_b1_id)
    ),
    neighbors AS (
        SELECT other_id, max(other_type) AS other_type, bool_or(side = 0) AS on_v0, bool_or(side = 1) AS on_v1
        FROM incidents
        GROUP BY other_id
    )
    SELECT
        other_id,
        other_type,
        CASE
            WHEN on_v0 AND on_v1 THEN 2::smallint
            WHEN on_v0 THEN 0::smallint
            ELSE 1::smallint
        END
    FROM neighbors;

    WITH phase_delta AS (
        SELECT id, sum(delta)::double precision AS delta
        FROM (
            SELECT id, 1::double precision AS delta
                FROM zx_pivot_neighbors
                WHERE set = 2
            UNION ALL
            SELECT id, v0_phase AS delta
                FROM zx_pivot_neighbors
                WHERE set IN (1, 2)
                    AND zx_normalize_phase(v0_phase) <> 0::double precision
            UNION ALL
            SELECT id, v1_phase AS delta
                FROM zx_pivot_neighbors
                WHERE set IN (0, 2)
                    AND zx_normalize_phase(v1_phase) <> 0::double precision
        ) AS delta_terms
        GROUP BY id
    )
    UPDATE zx_vertex AS v
    SET param = zx_normalize_phase(v.param + phase_delta.delta)
        FROM phase_delta
        WHERE v.id = phase_delta.id
            AND zx_normalize_phase(phase_delta.delta) <> 0::double precision;

    -- The a.id < b.id join condition already orders each pair, matching the (a_id, b_id) primary key.
    INSERT INTO zx_pending_edges(a_id, a_type, b_id, b_type, n_regular, n_had)
    SELECT
            a.id AS a_id,
            a.type AS a_type,
            b.id AS b_id,
            b.type AS b_type,
            0::smallint AS n_regular,
            1::smallint AS n_had
        FROM zx_pivot_neighbors AS a
        JOIN zx_pivot_neighbors AS b
            ON a.id < b.id
            AND a.set <> b.set;

    IF p_b1_id IS NULL THEN
        vertices_to_remove := vertices_to_remove || p_v0_id;
    ELSE
        SELECT ie.edge_id, ie.edge_type
        INTO retained_edge_id, retained_edge_type
            FROM zx_incident_edges(p_v1_id) AS ie
            WHERE ie.other_id = p_b1_id
            ORDER BY ie.edge_id
            LIMIT 1;

        INSERT INTO zx_pending_edges(a_id, a_type, b_id, b_type, n_regular, n_had)
        SELECT
                LEAST(v0.id, retained.id) AS a_id,
                CASE WHEN v0.id <= retained.id THEN v0.type ELSE retained.type END AS a_type,
                GREATEST(v0.id, retained.id) AS b_id,
                CASE WHEN v0.id <= retained.id THEN retained.type ELSE v0.type END AS b_type,
                CASE WHEN retained_edge_type = zx_const_hadamard_edge() THEN 1::smallint ELSE 0::smallint END AS n_regular,
                CASE WHEN retained_edge_type = zx_const_regular_edge() THEN 1::smallint ELSE 0::smallint END AS n_had
            FROM zx_vertex AS v0
            JOIN zx_vertex AS retained ON retained.id = p_b1_id
            WHERE v0.id = p_v0_id
            ON CONFLICT (a_id, b_id)
                DO UPDATE SET
                    n_regular = ((zx_pending_edges.n_regular + EXCLUDED.n_regular) % 2)::smallint,
                    n_had = ((zx_pending_edges.n_had + EXCLUDED.n_had) % 2)::smallint;

        DELETE FROM zx_edge
            WHERE id = retained_edge_id;
    END IF;

    PERFORM zx_merge_edge(
        replacement.a_id,
        replacement.a_type,
        replacement.b_id,
        replacement.b_type,
        replacement.edge_type
    )
    FROM (
        SELECT
                a_id,
                a_type,
                b_id,
                b_type,
                zx_const_regular_edge() AS edge_type
            FROM zx_pending_edges
            WHERE n_regular = 1
        UNION ALL
        SELECT
                a_id,
                a_type,
                b_id,
                b_type,
                zx_const_hadamard_edge() AS edge_type
            FROM zx_pending_edges
            WHERE n_had = 1
    ) AS replacement;

    DELETE FROM zx_edge
    WHERE get_id_from_link(source) = ANY(vertices_to_remove)
       OR get_id_from_link(target) = ANY(vertices_to_remove);

    DELETE FROM zx_vertex
    WHERE id = ANY(vertices_to_remove);
END;
$$;

-- Pivot simplification: pivot on Hadamard edges between two interior Pauli Z-spiders, removing both.
CREATE OR REPLACE PROCEDURE zx_pivot_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    candidate record;
    vertex_pair record;
BEGIN
    rewrite_started_at := clock_timestamp();
    FOR candidate IN
        WITH edge_endpoints AS (
            SELECT
                e.id AS edge_id,
                e.type AS edge_type,
                get_id_from_link(e.source) AS source_id,
                get_type_from_link(e.source) AS source_type,
                get_id_from_link(e.target) AS target_id,
                get_type_from_link(e.target) AS target_type
            FROM zx_edge AS e
        ),
        incident AS (
            SELECT edge_id, edge_type, source_id AS self_id, target_type AS other_type
                FROM edge_endpoints
            UNION ALL
            SELECT edge_id, edge_type, target_id AS self_id, source_type AS other_type
                FROM edge_endpoints
        ),
        vertex_ok AS (
            SELECT
                v.id,
                v.param,
                COUNT(i.edge_id) AS degree,
                COUNT(*) FILTER (WHERE zx_type_is_boundary(i.other_type)) AS boundary_count,
                bool_or(
                    NOT zx_type_is_boundary(i.other_type)
                    AND (i.edge_type <> zx_const_hadamard_edge()
                        OR i.other_type <> zx_const_z_spider())
                ) AS has_bad_incident
            FROM zx_vertex AS v
            LEFT JOIN incident AS i ON i.self_id = v.id
            WHERE v.type = zx_const_z_spider()
                AND zx_phase_is_pauli(v.param)
            GROUP BY v.id, v.param
        )
        SELECT
                ee.edge_id,
                ee.source_id AS v0_id,
                ee.target_id AS v1_id
            FROM edge_endpoints AS ee
            JOIN vertex_ok AS v0 ON v0.id = ee.source_id
            JOIN vertex_ok AS v1 ON v1.id = ee.target_id
            WHERE ee.edge_type = zx_const_hadamard_edge()
                AND NOT COALESCE(v0.has_bad_incident, false)
                AND NOT COALESCE(v1.has_bad_incident, false)
                AND COALESCE(v0.boundary_count, 0) + COALESCE(v1.boundary_count, 0) <= 1
            ORDER BY
                GREATEST((v0.degree - 1), 0) * GREATEST((v1.degree - 1), 0),
                ee.edge_id
    LOOP
        SELECT
            v0.id AS v0_id,
            v0.param AS v0_param,
            v0_inc.boundary_id AS v0_boundary_id,
            v1.id AS v1_id,
            v1.param AS v1_param,
            v1_inc.boundary_id AS v1_boundary_id
        INTO vertex_pair
            FROM zx_edge AS e
            JOIN zx_vertex AS v0 ON v0.id = candidate.v0_id
            JOIN zx_vertex AS v1 ON v1.id = candidate.v1_id
            CROSS JOIN LATERAL (
                SELECT
                    MIN(ie.other_id) FILTER (WHERE zx_type_is_boundary(ie.other_type)) AS boundary_id,
                    COUNT(*) FILTER (WHERE zx_type_is_boundary(ie.other_type)) AS boundary_count,
                    bool_or(
                        ie.other_id <> v0.id
                        AND NOT zx_type_is_boundary(ie.other_type)
                        AND (ie.edge_type <> zx_const_hadamard_edge()
                            OR ie.other_type <> zx_const_z_spider())
                    ) AS has_invalid_neighbor
                FROM zx_incident_edges(v0.id) AS ie
            ) AS v0_inc
            CROSS JOIN LATERAL (
                SELECT
                    MIN(ie.other_id) FILTER (WHERE zx_type_is_boundary(ie.other_type)) AS boundary_id,
                    COUNT(*) FILTER (WHERE zx_type_is_boundary(ie.other_type)) AS boundary_count,
                    bool_or(
                        ie.other_id <> v1.id
                        AND NOT zx_type_is_boundary(ie.other_type)
                        AND (ie.edge_type <> zx_const_hadamard_edge()
                            OR ie.other_type <> zx_const_z_spider())
                    ) AS has_invalid_neighbor
                FROM zx_incident_edges(v1.id) AS ie
            ) AS v1_inc
            WHERE e.id = candidate.edge_id
                -- zx_merge_edge creates only edges where source id < target id
                AND get_id_from_link(e.source) = LEAST(v0.id, v1.id)
                AND get_id_from_link(e.target) = GREATEST(v0.id, v1.id)

                -- Need to revalidate as previous loops may have changed the endpoints
                AND e.type = zx_const_hadamard_edge()
                AND v0.type = zx_const_z_spider()
                AND v1.type = zx_const_z_spider()
                AND zx_phase_is_pauli(v0.param)
                AND zx_phase_is_pauli(v1.param)

                AND NOT COALESCE(v0_inc.has_invalid_neighbor, false)
                AND NOT COALESCE(v1_inc.has_invalid_neighbor, false)
                AND v0_inc.boundary_count + v1_inc.boundary_count <= 1;

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        IF vertex_pair.v0_boundary_id IS NOT NULL THEN
            -- _zx_apply_pivot expects the optional retained boundary on p_v1.
            CALL _zx_apply_pivot(
                vertex_pair.v1_id,
                vertex_pair.v0_id,
                vertex_pair.v0_boundary_id,
                vertex_pair.v1_param,
                vertex_pair.v0_param
            );
        ELSE
            CALL _zx_apply_pivot(
                vertex_pair.v0_id,
                vertex_pair.v1_id,
                vertex_pair.v1_boundary_id,
                vertex_pair.v0_param,
                vertex_pair.v1_param
            );
        END IF;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_pivot_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

-- Boundary pivot: pivot a Pauli Z-spider against its neighbour that touches a boundary, adding a phase gadget.
CREATE OR REPLACE PROCEDURE zx_pivot_boundary_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    candidate record;
    pauli_vertex record;
    boundary_partner record;
    new_phase_vertex_id bigint;
    new_connector_vertex_id bigint;
BEGIN
    rewrite_started_at := clock_timestamp();
    -- Find ids for a vertex connected to another vertex connected to a boundary
    FOR candidate IN
        WITH incident AS (
            SELECT
                    type AS edge_type,
                    get_id_from_link(source) AS self_id,
                    get_id_from_link(target) AS other_id,
                    get_type_from_link(target) AS other_type
                FROM zx_edge
            UNION ALL
            SELECT
                    type AS edge_type,
                    get_id_from_link(target) AS self_id,
                    get_id_from_link(source) AS other_id,
                    get_type_from_link(source) AS other_type
                FROM zx_edge
        ),
        degree AS (
            SELECT self_id AS id, count(*) AS degree
                FROM incident
                GROUP BY self_id
        ),
        boundary_partner_ok AS (
            SELECT
                    w.id AS w_id,
                    w.param AS w_param,
                    COALESCE(d.degree, 0) AS w_degree,
                    min(i.other_id) FILTER (WHERE zx_type_is_boundary(i.other_type)) AS boundary_id
                FROM zx_vertex AS w
                JOIN incident AS i ON i.self_id = w.id
                LEFT JOIN degree AS d ON d.id = w.id
                WHERE w.type = zx_const_z_spider()
                    AND NOT zx_phase_is_pauli(w.param)
                GROUP BY w.id, w.param, d.degree
                HAVING count(*) > 1
                    AND count(*) FILTER (WHERE zx_type_is_boundary(i.other_type)) = 1
                    AND NOT bool_or(
                        NOT zx_type_is_boundary(i.other_type)
                        AND (i.other_type <> zx_const_z_spider()
                            OR i.edge_type <> zx_const_hadamard_edge()))
        ),
        pauli_ok AS (
            SELECT
                    v.id AS v_id,
                    COALESCE(self_degree.degree, 0) AS v_degree
                FROM zx_vertex AS v
                JOIN incident AS i ON i.self_id = v.id
                LEFT JOIN degree AS self_degree ON self_degree.id = v.id
                LEFT JOIN degree AS other_degree ON other_degree.id = i.other_id
                WHERE v.type = zx_const_z_spider()
                    AND zx_phase_is_pauli(v.param)
                GROUP BY v.id, self_degree.degree
                HAVING NOT bool_or(
                    i.other_type <> zx_const_z_spider()
                    OR i.edge_type <> zx_const_hadamard_edge()
                    OR COALESCE(other_degree.degree, 0) <= 1)
        )
        SELECT DISTINCT ON (i.other_id)
                i.other_id AS v_id,
                wb.w_id,
                wb.boundary_id
            FROM boundary_partner_ok AS wb
            JOIN incident AS i ON i.self_id = wb.w_id
            JOIN pauli_ok AS p ON p.v_id = i.other_id
            WHERE i.other_id <> wb.boundary_id
                AND i.other_type = zx_const_z_spider()
                AND i.edge_type = zx_const_hadamard_edge()
            ORDER BY
                i.other_id,
                zx_phase_is_proper_clifford(wb.w_param) DESC,
                GREATEST(p.v_degree - 1, 0) * GREATEST(wb.w_degree - 1, 0),
                wb.w_id
    LOOP

        -- Re-check the vertices as the rewrite may change them
        SELECT * INTO pauli_vertex FROM zx_vertex WHERE id = candidate.v_id;
        IF NOT FOUND
            OR pauli_vertex.type <> zx_const_z_spider()
            OR NOT zx_phase_is_pauli(pauli_vertex.param)
        THEN
            CONTINUE;
        END IF;

        SELECT * INTO boundary_partner FROM zx_vertex WHERE id = candidate.w_id;
        IF NOT FOUND
            OR boundary_partner.type <> zx_const_z_spider()
            OR zx_phase_is_pauli(boundary_partner.param)
        THEN
            CONTINUE;
        END IF;

        -- No need to re-check the boundary vertex as it does not change from the rewrites

        -- Check the edges still exist
        -- zx_merge_edge creates only edges where source id < target id
        IF NOT EXISTS (
            SELECT 1 FROM zx_edge AS e
                WHERE get_id_from_link(e.source) = LEAST(pauli_vertex.id, boundary_partner.id)
                    AND get_id_from_link(e.target) = GREATEST(pauli_vertex.id, boundary_partner.id)
                    AND e.type = zx_const_hadamard_edge()
        ) THEN
            CONTINUE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM zx_edge AS e
                WHERE get_id_from_link(e.source) = LEAST(boundary_partner.id, candidate.boundary_id)
                    AND get_id_from_link(e.target) = GREATEST(boundary_partner.id, candidate.boundary_id)
        ) THEN
            CONTINUE;
        END IF;

        -- Revalidate the boundary partner's neighborhood
        IF NOT EXISTS (
                SELECT 1
                    FROM zx_incident_edges(boundary_partner.id)
                    HAVING count(*) > 1
                        AND count(*) FILTER (WHERE zx_type_is_boundary(other_type)) = 1
                        AND NOT bool_or(
                            NOT zx_type_is_boundary(other_type)
                            AND (other_type <> zx_const_z_spider()
                                OR edge_type <> zx_const_hadamard_edge())
                        )
        ) THEN
            CONTINUE;
        END IF;

        -- Check that all neighbors of the Pauli vertex are ok
        IF EXISTS (
            SELECT 1
                FROM zx_incident_edges(pauli_vertex.id) AS ie
                WHERE ie.other_type <> zx_const_z_spider()
                    OR ie.edge_type <> zx_const_hadamard_edge()
                    OR zx_edge_degree(ie.other_id) <= 1
        ) THEN
            CONTINUE;
        END IF;

        -- Add a phase gadget
        INSERT INTO zx_vertex(type, qubit, row, param)
        VALUES (zx_const_z_spider(), -2, boundary_partner.row, boundary_partner.param)
        RETURNING id INTO new_phase_vertex_id;

        INSERT INTO zx_vertex(type, qubit, row, param)
        VALUES (zx_const_z_spider(), -1, boundary_partner.row, 0::double precision)
        RETURNING id INTO new_connector_vertex_id;

        UPDATE zx_vertex
        SET param = 0::double precision
            WHERE id = boundary_partner.id;

        PERFORM zx_merge_edge(
            new_phase_vertex_id,
            zx_const_z_spider(),
            new_connector_vertex_id,
            zx_const_z_spider(),
            zx_const_hadamard_edge()
        );

        PERFORM zx_merge_edge(
            new_connector_vertex_id,
            zx_const_z_spider(),
            boundary_partner.id,
            boundary_partner.type,
            zx_const_hadamard_edge()
        );

        CALL _zx_apply_pivot(
            pauli_vertex.id,
            boundary_partner.id,
            candidate.boundary_id,
            pauli_vertex.param,
            0::double precision
        );

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_pivot_boundary_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

-- Gadget pivot: pivot a Pauli Z-spider against a non-Pauli neighbour, turning the neighbour into a phase gadget.
CREATE OR REPLACE PROCEDURE zx_pivot_gadget_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    candidate record;
    gadget_pair record;
    new_gadget_vertex_id bigint;
    neighbor_ids bigint[];
    neighbor_types smallint[];
    neighbor_sets smallint[];
    neighbor_pauli_edge_ids bigint[];
BEGIN
    rewrite_started_at := clock_timestamp();
    FOR candidate IN
        WITH raw_edges AS (
            SELECT
                    e.id AS edge_id,
                    get_id_from_link(e.source) AS source_id,
                    get_id_from_link(e.target) AS target_id,
                    zx_phase_is_pauli(source_vertex.param) AS source_is_pauli,
                    zx_phase_is_pauli(target_vertex.param) AS target_is_pauli
                FROM zx_edge AS e
                JOIN zx_vertex AS source_vertex
                    ON source_vertex.id = get_id_from_link(e.source)
                JOIN zx_vertex AS target_vertex
                    ON target_vertex.id = get_id_from_link(e.target)
                WHERE e.type = zx_const_hadamard_edge()
                    AND source_vertex.type = zx_const_z_spider()
                    AND target_vertex.type = zx_const_z_spider()
        )
        SELECT
                edge_id,
                CASE WHEN source_is_pauli THEN source_id ELSE target_id END AS pauli_id,
                CASE WHEN source_is_pauli THEN target_id ELSE source_id END AS non_pauli_id
            FROM raw_edges
            WHERE (source_is_pauli AND NOT target_is_pauli)
                OR (target_is_pauli AND NOT source_is_pauli)
            ORDER BY edge_id
    LOOP
        SELECT
            pauli_vertex.id AS pauli_id,
            pauli_vertex.row AS pauli_row,
            pauli_vertex.param AS pauli_param,
            non_pauli_vertex.id AS non_pauli_id,
            non_pauli_vertex.param AS non_pauli_param
        INTO gadget_pair
            FROM zx_edge AS edge_to_pivot
            JOIN zx_vertex AS pauli_vertex
                ON pauli_vertex.id = candidate.pauli_id
            JOIN zx_vertex AS non_pauli_vertex
                ON non_pauli_vertex.id = candidate.non_pauli_id
            WHERE edge_to_pivot.id = candidate.edge_id
                -- zx_merge_edge creates only edges where source id < target id
                AND get_id_from_link(edge_to_pivot.source) = LEAST(candidate.pauli_id, candidate.non_pauli_id)
                AND get_id_from_link(edge_to_pivot.target) = GREATEST(candidate.pauli_id, candidate.non_pauli_id)
                AND edge_to_pivot.type = zx_const_hadamard_edge()
                AND pauli_vertex.type = zx_const_z_spider()
                AND non_pauli_vertex.type = zx_const_z_spider()
                AND zx_phase_is_pauli(pauli_vertex.param)
                AND NOT zx_phase_is_pauli(non_pauli_vertex.param);

        IF NOT FOUND THEN
            CONTINUE;
        END IF;

        -- Fail fast if the candidate is stale
        IF NOT EXISTS (
            SELECT 1
                FROM zx_incident_edges(gadget_pair.non_pauli_id) AS ie
                WHERE ie.other_id <> gadget_pair.pauli_id
        ) THEN
            CONTINUE;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM (
                SELECT other_id, other_type, edge_type
                    FROM zx_incident_edges(gadget_pair.pauli_id)
                    WHERE other_id <> gadget_pair.non_pauli_id
                UNION ALL
                SELECT other_id, other_type, edge_type
                    FROM zx_incident_edges(gadget_pair.non_pauli_id)
                    WHERE other_id <> gadget_pair.pauli_id
            ) AS ie
            WHERE ie.other_type <> zx_const_z_spider()
                OR ie.edge_type <> zx_const_hadamard_edge()
        ) THEN
            CONTINUE;
        END IF;

        -- Specialised pivot for the gadget case
        WITH incident AS (
            SELECT edge_id, other_id, other_type, 0 AS side
                FROM zx_incident_edges(gadget_pair.pauli_id)
                    WHERE other_id <> gadget_pair.non_pauli_id
            UNION ALL
            SELECT edge_id, other_id, other_type, 1 AS side
                FROM zx_incident_edges(gadget_pair.non_pauli_id)
                    WHERE other_id <> gadget_pair.pauli_id
        ),
        neighbors AS (
            SELECT
                other_id AS id,
                max(other_type)::smallint AS vertex_type,
                CASE
                    WHEN bool_or(side = 0) AND bool_or(side = 1) THEN 2::smallint
                    WHEN bool_or(side = 0) THEN 0::smallint
                    ELSE 1::smallint
                END AS neighbor_set,
                min(edge_id) FILTER (WHERE side = 0) AS pauli_edge_id
            FROM incident
            GROUP BY other_id
        )
        SELECT
            COALESCE(array_agg(id ORDER BY id), ARRAY[]::bigint[]),
            COALESCE(array_agg(vertex_type ORDER BY id), ARRAY[]::smallint[]),
            COALESCE(array_agg(neighbor_set ORDER BY id), ARRAY[]::smallint[]),
            COALESCE(array_agg(pauli_edge_id ORDER BY id), ARRAY[]::bigint[])
        INTO
            neighbor_ids,
            neighbor_types,
            neighbor_sets,
            neighbor_pauli_edge_ids
        FROM neighbors;

        IF EXISTS (
            WITH neighbors AS (
                SELECT *
                FROM unnest(
                    neighbor_ids,
                    neighbor_types,
                    neighbor_sets,
                    neighbor_pauli_edge_ids
                ) AS n(id, vertex_type, neighbor_set, pauli_edge_id)
            )
            SELECT 1
            FROM neighbors AS n
            WHERE n.neighbor_set = 0
                AND NOT EXISTS (
                    SELECT 1
                    FROM zx_edge AS second_edge
                    WHERE second_edge.id <> n.pauli_edge_id
                        AND get_id_from_link(second_edge.source) = n.id
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM zx_edge AS second_edge
                    WHERE second_edge.id <> n.pauli_edge_id
                        AND get_id_from_link(second_edge.target) = n.id
                )
        )
        THEN
            CONTINUE;
        END IF;

        INSERT INTO zx_vertex(type, qubit, row, param)
        VALUES (
            zx_const_z_spider(),
            -2,
            gadget_pair.pauli_row,
            gadget_pair.non_pauli_param
        )
        RETURNING id INTO new_gadget_vertex_id;

        UPDATE zx_vertex
        SET qubit = -1
            WHERE id = gadget_pair.pauli_id;

        WITH n AS (
            SELECT id, neighbor_set
            FROM unnest(neighbor_ids, neighbor_sets) AS n(id, neighbor_set)
        ),
        phase_delta AS (
            SELECT
                id,
                CASE
                    WHEN neighbor_set = 2 THEN gadget_pair.pauli_param + 1::double precision
                    WHEN neighbor_set = 1 THEN gadget_pair.pauli_param
                    ELSE 0::double precision
                END AS delta
            FROM n
        )
        UPDATE zx_vertex AS v
        SET param = zx_normalize_phase(v.param + phase_delta.delta)
            FROM phase_delta
            WHERE v.id = phase_delta.id
                AND phase_delta.delta <> 0::double precision;

        PERFORM zx_merge_edge(
            edges_to_merge.a_id,
            edges_to_merge.a_type,
            edges_to_merge.b_id,
            edges_to_merge.b_type,
            zx_const_hadamard_edge()
        )
        FROM (
            SELECT
                gadget_pair.pauli_id AS a_id,
                zx_const_z_spider() AS a_type,
                new_gadget_vertex_id AS b_id,
                zx_const_z_spider() AS b_type
            UNION ALL
            SELECT
                a.id AS a_id,
                a.vertex_type AS a_type,
                b.id AS b_id,
                b.vertex_type AS b_type
            FROM unnest(neighbor_ids, neighbor_types, neighbor_sets) AS a(id, vertex_type, neighbor_set)
            JOIN unnest(neighbor_ids, neighbor_types, neighbor_sets) AS b(id, vertex_type, neighbor_set)
                ON a.id < b.id
                AND a.neighbor_set <> b.neighbor_set
        ) AS edges_to_merge;

        -- Split deletes let PostgreSQL use the expression indexes independently.
        DELETE FROM zx_edge
        WHERE get_id_from_link(source) = gadget_pair.non_pauli_id;

        DELETE FROM zx_edge
        WHERE get_id_from_link(target) = gadget_pair.non_pauli_id;

        DELETE FROM zx_vertex
        WHERE id = gadget_pair.non_pauli_id;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_pivot_gadget_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

-- Fault-equivalent n-legged spider fusion (Fuse-n_fe):
CREATE OR REPLACE PROCEDURE zx_fusen_fe_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    overlapping_gadget_id bigint;
    rewired_edge record;
BEGIN
    rewrite_started_at := clock_timestamp();
    CREATE TEMP TABLE IF NOT EXISTS fusen_fe_gadget (
        gadget_id bigint,
        comp_root bigint,
        vertex_id bigint,
        vertex_type smallint,
        PRIMARY KEY (gadget_id, vertex_id)
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS fusen_fe_gadget_comp_root_idx
        ON fusen_fe_gadget (comp_root);

    LOOP
        TRUNCATE fusen_fe_gadget;

        WITH candidate_vertices AS (
            SELECT DISTINCT
                v.id AS vertex_id,
                v.type AS vertex_type
            FROM zx_vertex v
            WHERE v.type IN (zx_const_z_spider(), zx_const_x_spider())
                AND zx_phase_is_zero(v.param)
        ),
        hub_candidates AS (
            SELECT
                c.vertex_id,
                c.vertex_type,
                d.degree
            FROM candidate_vertices c
            CROSS JOIN LATERAL (SELECT zx_edge_degree(c.vertex_id)::bigint AS degree) d
            WHERE d.degree >= 2
            AND NOT EXISTS (
                SELECT 1
                FROM zx_incident_edges(c.vertex_id) i
                LEFT JOIN candidate_vertices o
                    ON o.vertex_id = i.other_id
                    AND o.vertex_type = c.vertex_type
                WHERE i.edge_type <> zx_const_regular_edge()
                    OR o.vertex_id IS NULL
            )
        ),
        hub_pairs AS (
            SELECT
                h1.vertex_id AS hub_a,
                h2.vertex_id AS hub_b,
                h1.vertex_type,
                h1.degree AS n
            FROM hub_candidates h1
            JOIN hub_candidates h2
                ON h1.vertex_id < h2.vertex_id
                AND h1.vertex_type = h2.vertex_type
                AND h1.degree = h2.degree
            WHERE NOT EXISTS (
                SELECT 1
                FROM zx_edge e
                WHERE get_id_from_link(e.source) = h1.vertex_id
                    AND get_id_from_link(e.target) = h2.vertex_id
            )
        ),
        hub_neighbours AS (
            SELECT
                    p.hub_a,
                    p.hub_b,
                    p.vertex_type,
                    p.n,
                    0 AS side,
                    i.other_id AS outer_id
                FROM hub_pairs p
                CROSS JOIN LATERAL zx_incident_edges(p.hub_a) i
            UNION ALL
            SELECT
                    p.hub_a,
                    p.hub_b,
                    p.vertex_type,
                    p.n,
                    1 AS side,
                    i.other_id AS outer_id
                FROM hub_pairs p
                CROSS JOIN LATERAL zx_incident_edges(p.hub_b) i
        ),
        valid_pairs AS (
            SELECT
                hub_a,
                hub_b,
                vertex_type,
                n
            FROM hub_neighbours
            GROUP BY hub_a, hub_b, vertex_type, n
            HAVING count(DISTINCT outer_id) = 2 * n
                AND bool_and(zx_edge_degree(outer_id) = 3)
        ),
        valid_outer AS (
            SELECT hn.*
            FROM hub_neighbours hn
            JOIN valid_pairs vp
                USING (hub_a, hub_b, vertex_type, n)
        ),
        outer_pair_edges AS (
            SELECT
                oa.hub_a,
                oa.hub_b,
                oa.vertex_type,
                oa.n,
                oa.outer_id AS outer_a,
                ob.outer_id AS outer_b
            FROM valid_outer oa
            JOIN valid_outer ob
                ON ob.hub_a = oa.hub_a
                AND ob.hub_b = oa.hub_b
                AND ob.vertex_type = oa.vertex_type
                AND ob.n = oa.n
                AND ob.side = 1
            JOIN zx_incident_edges(oa.outer_id) i
                ON i.other_id = ob.outer_id
                AND i.edge_type = zx_const_regular_edge()
            WHERE oa.side = 0
        ),
        outer_pair_stats AS (
            SELECT
                hub_a,
                hub_b,
                vertex_type,
                n
            FROM outer_pair_edges
            GROUP BY hub_a, hub_b, vertex_type, n
            HAVING count(*) = n
                AND count(DISTINCT outer_a) = n
                AND count(DISTINCT outer_b) = n
        ),
        selected_vertices AS (
            SELECT
                    hub_a,
                    hub_b,
                    vertex_type,
                    n,
                    hub_a AS vertex_id
                FROM valid_pairs
            UNION ALL
            SELECT
                    hub_a,
                    hub_b,
                    vertex_type,
                    n,
                    hub_b AS vertex_id
                FROM valid_pairs
            UNION ALL
            SELECT
                    hub_a,
                    hub_b,
                    vertex_type,
                    n,
                    outer_id AS vertex_id
                FROM valid_outer
        ),
        internal_edge_stats AS (
            SELECT
                sv1.hub_a,
                sv1.hub_b,
                sv1.vertex_type,
                sv1.n
            FROM selected_vertices sv1
            JOIN zx_incident_edges(sv1.vertex_id) i
                ON true
            JOIN selected_vertices sv2
                ON sv2.hub_a = sv1.hub_a
                AND sv2.hub_b = sv1.hub_b
                AND sv2.vertex_type = sv1.vertex_type
                AND sv2.n = sv1.n
                AND sv2.vertex_id = i.other_id
            GROUP BY sv1.hub_a, sv1.hub_b, sv1.vertex_type, sv1.n
            HAVING count(DISTINCT i.edge_id) = 3 * sv1.n
                AND count(DISTINCT i.edge_id) FILTER (
                    WHERE i.edge_type = zx_const_regular_edge()
                ) = 3 * sv1.n
        ),
        good_pairs AS (
            SELECT
                row_number() OVER (ORDER BY vp.hub_a, vp.hub_b) AS gadget_id,
                vp.hub_a,
                vp.hub_b,
                vp.vertex_type,
                vp.n,
                vp.hub_a AS survivor
            FROM valid_pairs vp
            JOIN outer_pair_stats ops
                USING (hub_a, hub_b, vertex_type, n)
            JOIN internal_edge_stats ies
                USING (hub_a, hub_b, vertex_type, n)
        ),
        chosen_vertices AS (
            SELECT
                    gp.gadget_id,
                    gp.survivor AS comp_root,
                    gp.hub_a AS vertex_id,
                    gp.vertex_type
                FROM good_pairs gp
            UNION ALL
            SELECT
                    gp.gadget_id,
                    gp.survivor AS comp_root,
                    gp.hub_b AS vertex_id,
                    gp.vertex_type
                FROM good_pairs gp
            UNION ALL
            SELECT
                    gp.gadget_id,
                    gp.survivor AS comp_root,
                    vo.outer_id AS vertex_id,
                    gp.vertex_type
                FROM good_pairs gp
                JOIN valid_outer vo
                    ON vo.hub_a = gp.hub_a
                    AND vo.hub_b = gp.hub_b
                    AND vo.vertex_type = gp.vertex_type
                    AND vo.n = gp.n
        )
        INSERT INTO fusen_fe_gadget (
            gadget_id,
            comp_root,
            vertex_id,
            vertex_type
        )
        SELECT
            gadget_id,
            comp_root,
            vertex_id,
            vertex_type
        FROM chosen_vertices;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        -- Delete gadgets while they overlap
        LOOP
            SELECT b.gadget_id
            INTO overlapping_gadget_id
                FROM fusen_fe_gadget a
                JOIN fusen_fe_gadget b
                    ON b.vertex_id = a.vertex_id
                    AND a.gadget_id < b.gadget_id
                ORDER BY a.gadget_id, b.gadget_id
                LIMIT 1;

            IF NOT FOUND THEN
                EXIT;
            END IF;

            DELETE FROM fusen_fe_gadget WHERE gadget_id = overlapping_gadget_id;
        END LOOP;

        FOR rewired_edge IN
            SELECT
                    e.type AS edge_type,
                    COALESCE(s.comp_root, get_id_from_link(e.source)) AS source_id,
                    COALESCE(s.vertex_type, get_type_from_link(e.source)) AS source_type,
                    COALESCE(t.comp_root, get_id_from_link(e.target)) AS target_id,
                    COALESCE(t.vertex_type, get_type_from_link(e.target)) AS target_type
                FROM zx_edge e
                LEFT JOIN fusen_fe_gadget s
                    ON s.vertex_id = get_id_from_link(e.source)
                LEFT JOIN fusen_fe_gadget t
                    ON t.vertex_id = get_id_from_link(e.target)
                WHERE (s.vertex_id IS NOT NULL OR t.vertex_id IS NOT NULL)
                -- Exclude gadget-internal edges
                AND NOT (s.vertex_id IS NOT NULL AND t.vertex_id IS NOT NULL AND s.gadget_id = t.gadget_id)
                -- Keep edges to root
                AND ((s.vertex_id IS NOT NULL AND s.vertex_id <> s.comp_root)
                    OR (t.vertex_id IS NOT NULL AND t.vertex_id <> t.comp_root))
        LOOP
            PERFORM zx_merge_edge(
                rewired_edge.source_id,
                rewired_edge.source_type,
                rewired_edge.target_id,
                rewired_edge.target_type,
                rewired_edge.edge_type
            );
        END LOOP;

        -- Delete all edge touching the non-root gadget spiders
        DELETE FROM zx_edge e
        USING fusen_fe_gadget s
        WHERE s.vertex_id <> s.comp_root
            AND (get_id_from_link(e.source) = s.vertex_id OR get_id_from_link(e.target) = s.vertex_id);

        -- Delete the non-root gadget spiders
        DELETE FROM zx_vertex v
        USING fusen_fe_gadget s
        WHERE s.vertex_id <> s.comp_root
            AND v.id = s.vertex_id;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_fusen_fe_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

-- Expand each even-degree (2n >= 4), phase-0 spider into the hub+column gadget.
CREATE OR REPLACE PROCEDURE zx_fusen_fe_expand(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    v          record;
    deg        integer;
    n          integer;
    w_ids      bigint[];
    w_types    smallint[];
    e_types    smallint[];
    t_ids      bigint[];
    b_ids      bigint[];
    hub_t      bigint;
    hub_b      bigint;
    new_id     bigint;
    i          integer;
BEGIN
    rewrite_started_at := clock_timestamp();
    FOR v IN
        SELECT id, type, qubit, "row"
            FROM zx_vertex
            WHERE type IN (zx_const_z_spider(), zx_const_x_spider())
                AND zx_phase_is_zero(param)
                AND zx_edge_degree(id) >= 4
                AND zx_edge_degree(id) % 2 = 0
    LOOP
        deg := zx_edge_degree(v.id);
        n := deg / 2;

        SELECT
                array_agg(other_id ORDER BY edge_id),
                array_agg(other_type ORDER BY edge_id),
                array_agg(edge_type ORDER BY edge_id)
            INTO w_ids, w_types, e_types
            FROM zx_incident_edges(v.id);

        -- Create the two hubs.
        INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (v.type, v.qubit, v.row, 0) RETURNING id INTO hub_t;
        INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (v.type, v.qubit, v.row, 0) RETURNING id INTO hub_b;

        -- Create the 2n column spiders.
        t_ids := ARRAY[]::bigint[];
        b_ids := ARRAY[]::bigint[];
        FOR i IN 1..n LOOP
            INSERT INTO zx_vertex(type, qubit, "row", param)
                VALUES (v.type, v.qubit, v.row, 0) RETURNING id INTO new_id;
            t_ids := t_ids || new_id;
            INSERT INTO zx_vertex(type, qubit, "row", param)
                VALUES (v.type, v.qubit, v.row, 0) RETURNING id INTO new_id;
            b_ids := b_ids || new_id;
        END LOOP;

        -- Internal edges (hub->column, vertical) and external legs.
        FOR i IN 1..n LOOP
            PERFORM zx_merge_edge(hub_t, v.type, t_ids[i], v.type, zx_const_regular_edge());
            PERFORM zx_merge_edge(hub_b, v.type, b_ids[i], v.type, zx_const_regular_edge());
            PERFORM zx_merge_edge(t_ids[i], v.type, b_ids[i], v.type, zx_const_regular_edge());

            PERFORM zx_merge_edge(t_ids[i], v.type, w_ids[i], w_types[i], e_types[i]);
            PERFORM zx_merge_edge(b_ids[i], v.type, w_ids[n + i], w_types[n + i], e_types[n + i]);
        END LOOP;

        -- Remove the original spider and its edges.
        DELETE FROM zx_edge e
            WHERE get_id_from_link(e.source) = v.id OR get_id_from_link(e.target) = v.id;
        DELETE FROM zx_vertex WHERE id = v.id;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_fusen_fe_expand', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

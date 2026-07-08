-- Fault-equivalent four-legged spider fusion (Fuse-4_fe):
CREATE OR REPLACE PROCEDURE zx_fuse4_fe_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    overlapping_square_id bigint;
    rewired_edge record;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS fuse4_fe_gadget (
        square_id bigint,
        comp_root bigint,
        vertex_id bigint,
        vertex_type smallint,
        PRIMARY KEY (square_id, vertex_id)
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS fuse4_fe_gadget_comp_root_idx
        ON fuse4_fe_gadget (comp_root);

    LOOP
        TRUNCATE fuse4_fe_gadget;

        WITH candidate_vertices AS (
            SELECT
                v.id AS vertex_id,
                v.type AS vertex_type
            FROM zx_vertex v
            WHERE v.type IN (zx_const_z_spider(), zx_const_x_spider())
                AND zx_phase_is_zero(v.param)
        ),
        regular_pairs AS (
            SELECT DISTINCT
                LEAST(cs.vertex_id, ct.vertex_id) AS a,
                GREATEST(cs.vertex_id, ct.vertex_id) AS b,
                cs.vertex_type
            FROM zx_edge e
            INNER JOIN candidate_vertices cs
                ON cs.vertex_id = get_id_from_link(e.source)
            INNER JOIN candidate_vertices ct
                ON ct.vertex_id = get_id_from_link(e.target)
            WHERE e.type = zx_const_regular_edge()
                AND cs.vertex_id <> ct.vertex_id
                AND cs.vertex_type = ct.vertex_type
        ),
        adj AS (
            SELECT
                a AS from_id,
                b AS to_id,
                vertex_type
            FROM regular_pairs
            UNION ALL
            SELECT
                b AS from_id,
                a AS to_id,
                vertex_type
            FROM regular_pairs
        ),
        raw_cycles AS (
            SELECT
                a.from_id AS v1,
                a.to_id AS v2,
                b.to_id AS v3,
                c.to_id AS v4,
                a.vertex_type
            FROM adj a
            JOIN adj b
                ON b.from_id = a.to_id
                AND a.vertex_type = b.vertex_type
            JOIN adj c
                ON c.from_id = b.to_id
                AND b.vertex_type = c.vertex_type
            JOIN regular_pairs closing_edge
                ON closing_edge.a = LEAST(c.to_id, a.from_id)
                AND closing_edge.b = GREATEST(c.to_id, a.from_id)
                AND closing_edge.vertex_type = a.vertex_type
            WHERE a.from_id <> b.to_id
                AND a.from_id <> c.to_id
                AND a.to_id <> b.to_id
                AND a.to_id <> c.to_id
                AND b.to_id <> c.to_id
        ),
        cycle_quads AS (
            SELECT DISTINCT
                sorted.verts,
                rc.vertex_type
            FROM raw_cycles rc
            CROSS JOIN LATERAL (
                SELECT array_agg(x ORDER BY x) AS verts
                FROM unnest(ARRAY[rc.v1, rc.v2, rc.v3, rc.v4]) AS u(x)
            ) sorted
        ),
        exact_internal_square AS (
            SELECT
                q.verts,
                q.vertex_type
            FROM cycle_quads q
            JOIN zx_edge e
                ON get_id_from_link(e.source) = ANY(q.verts)
                AND get_id_from_link(e.target) = ANY(q.verts)
            GROUP BY q.verts, q.vertex_type
            HAVING count(*) = 4
        ),
        exact_boundary_legs AS (
            SELECT sq.*
            FROM exact_internal_square sq
            WHERE NOT EXISTS (
                SELECT 1
                FROM unnest(sq.verts) AS v(vertex_id)
                WHERE zx_edge_degree(vertex_id) <> 3
            )
        ),
        selected_square AS (
            SELECT
                row_number() OVER (
                    ORDER BY sq.verts, sq.vertex_type
                ) AS square_id,
                (sq.verts)[1] AS comp_root,
                sq.verts,
                sq.vertex_type
            FROM exact_boundary_legs sq
        ),
        chosen_vertices AS (
            SELECT
                ss.square_id,
                ss.comp_root,
                v.vertex_id,
                ss.vertex_type
            FROM selected_square ss
            CROSS JOIN LATERAL unnest(ss.verts) AS v(vertex_id)
        )
        INSERT INTO fuse4_fe_gadget (square_id, comp_root, vertex_id, vertex_type)
        SELECT
            square_id,
            comp_root,
            vertex_id,
            vertex_type
        FROM chosen_vertices;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        -- Delete squares while they overlap
        LOOP
            SELECT b.square_id
            INTO overlapping_square_id
                FROM fuse4_fe_gadget a
                JOIN fuse4_fe_gadget b
                    ON b.vertex_id = a.vertex_id
                    AND a.square_id < b.square_id
                ORDER BY a.square_id, b.square_id
                LIMIT 1;

            IF NOT FOUND THEN
                EXIT;
            END IF;

            DELETE FROM fuse4_fe_gadget WHERE square_id = overlapping_square_id;
        END LOOP;

        FOR rewired_edge IN
            SELECT
                    e.type AS edge_type,
                    COALESCE(s.comp_root, get_id_from_link(e.source)) AS source_id,
                    COALESCE(s.vertex_type, get_type_from_link(e.source)) AS source_type,
                    COALESCE(t.comp_root, get_id_from_link(e.target)) AS target_id,
                    COALESCE(t.vertex_type, get_type_from_link(e.target)) AS target_type
                FROM zx_edge e
                LEFT JOIN fuse4_fe_gadget s
                    ON s.vertex_id = get_id_from_link(e.source)
                LEFT JOIN fuse4_fe_gadget t
                    ON t.vertex_id = get_id_from_link(e.target)
                WHERE (s.vertex_id IS NOT NULL OR t.vertex_id IS NOT NULL)
                -- Exclude the square's internal edges
                AND NOT (s.vertex_id IS NOT NULL AND t.vertex_id IS NOT NULL AND s.square_id = t.square_id)
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

        -- Delete all edge touching the non-root square spiders
        DELETE FROM zx_edge e
        USING fuse4_fe_gadget s
        WHERE s.vertex_id <> s.comp_root
            AND (get_id_from_link(e.source) = s.vertex_id OR get_id_from_link(e.target) = s.vertex_id);

        -- Delete the three non-root square spiders
        DELETE FROM zx_vertex v
        USING fuse4_fe_gadget s
        WHERE s.vertex_id <> s.comp_root
            AND v.id = s.vertex_id;

        changed := true;
    END LOOP;
END;
$$;

--Expand each degree-4, phase-0 spider into the 4-cycle gadget
CREATE OR REPLACE PROCEDURE zx_fuse4_fe_expand(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    v record;
    w_ids bigint[];
    w_types smallint[];
    e_types smallint[];
    r_ids bigint[];
    new_id bigint;
    i integer;
BEGIN
    FOR v IN
        SELECT id, type, qubit, "row"
            FROM zx_vertex
            WHERE type IN (zx_const_z_spider(), zx_const_x_spider())
                AND zx_phase_is_zero(param)
                AND zx_edge_degree(id) = 4
    LOOP
        SELECT
                array_agg(other_id ORDER BY edge_id),
                array_agg(other_type ORDER BY edge_id),
                array_agg(edge_type ORDER BY edge_id)
            INTO w_ids, w_types, e_types
            FROM zx_incident_edges(v.id);

        -- Create the four ring spiders.
        r_ids := ARRAY[]::bigint[];
        FOR i IN 1..4 LOOP
            INSERT INTO zx_vertex(type, qubit, "row", param)
                VALUES (v.type, v.qubit, v.row, 0)
                RETURNING id INTO new_id;
            r_ids := r_ids || new_id;
        END LOOP;

        -- Ring edges
        FOR i IN 1..4 LOOP
            PERFORM zx_merge_edge(r_ids[i], v.type, r_ids[(i % 4) + 1], v.type, zx_const_regular_edge());
        END LOOP;

        -- External legs
        FOR i IN 1..4 LOOP
            PERFORM zx_merge_edge(r_ids[i], v.type, w_ids[i], w_types[i], e_types[i]);
        END LOOP;

        -- Remove the original spider and its edges.
        DELETE FROM zx_edge e
            WHERE get_id_from_link(e.source) = v.id OR get_id_from_link(e.target) = v.id;
        DELETE FROM zx_vertex WHERE id = v.id;

        changed := true;
    END LOOP;
END;
$$;

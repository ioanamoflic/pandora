CREATE OR REPLACE PROCEDURE zx_pi_copy_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    overlapping_candidate_id bigint;
    copied_leg record;
    new_vertex_id bigint;
BEGIN
    rewrite_started_at := clock_timestamp();
    CREATE TEMP TABLE IF NOT EXISTS pi_copy_gadget (
        cand_id bigint,
        pi_id bigint,
        copy_edge_id bigint,
        source_edge_id bigint,
        center_id bigint,
        center_edge_id bigint
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS pi_copy_gadget_cand_idx
        ON pi_copy_gadget (cand_id);

    TRUNCATE pi_copy_gadget;

    WITH pi_center_edges AS (
        SELECT
            pi.id AS pi_id,
            pi.type AS pi_type,
            copy_edge.id AS copy_edge_id,
            CASE
                WHEN get_id_from_link(copy_edge.source) = pi.id
                    THEN get_id_from_link(copy_edge.target)
                ELSE get_id_from_link(copy_edge.source)
            END AS center_id
        FROM zx_vertex pi
        JOIN zx_edge copy_edge
            ON get_id_from_link(copy_edge.source) = pi.id
            OR get_id_from_link(copy_edge.target) = pi.id
        WHERE zx_type_is_zx_spider(pi.type)
            AND pi.param = 1::double precision
            AND zx_edge_degree(pi.id) = 2
            AND copy_edge.type = zx_const_regular_edge()
    ),
    source_leg AS (
        SELECT
            p.pi_id,
            p.pi_type,
            p.copy_edge_id,
            p.center_id,
            source_edge.id AS source_edge_id
        FROM pi_center_edges p
        JOIN zx_edge source_edge
            ON source_edge.id <> p.copy_edge_id
            AND (get_id_from_link(source_edge.source) = p.pi_id
                OR get_id_from_link(source_edge.target) = p.pi_id)
    ),
    raw_candidates AS (
        SELECT
            row_number() OVER (
                ORDER BY s.pi_id, s.copy_edge_id, s.center_id, s.source_edge_id
            )::bigint AS cand_id,
            s.pi_id,
            s.copy_edge_id,
            s.source_edge_id,
            s.center_id
        FROM source_leg s
        JOIN zx_vertex center
            ON center.id = s.center_id
        WHERE zx_type_is_zx_spider(center.type)
            AND zx_phase_is_clifford(center.param)
            AND center.type <> s.pi_type
    )
    INSERT INTO pi_copy_gadget (
        cand_id,
        pi_id,
        copy_edge_id,
        source_edge_id,
        center_id,
        center_edge_id
    )
    SELECT
        c.cand_id,
        c.pi_id,
        c.copy_edge_id,
        c.source_edge_id,
        c.center_id,
        center_edge.id AS center_edge_id
    FROM raw_candidates c
    JOIN zx_edge center_edge
        ON (get_id_from_link(center_edge.source) = c.center_id
            OR get_id_from_link(center_edge.target) = c.center_id)
        AND center_edge.id <> c.copy_edge_id
        AND center_edge.id <> c.source_edge_id;

    IF NOT EXISTS (SELECT 1 FROM pi_copy_gadget) THEN
        INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
        VALUES ('zx_pi_copy_simp', rewrite_started_at, rewrite_execution_count,
                EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
        RETURN;
    END IF;

    changed := true;

    rewrite_execution_count := rewrite_execution_count + 1;

    -- Remove candidates that overlap.
    LOOP
        SELECT b.cand_id
        INTO overlapping_candidate_id
            FROM pi_copy_gadget a
            JOIN pi_copy_gadget b
                ON a.cand_id < b.cand_id
            WHERE
                a.center_id = b.center_id
                OR a.copy_edge_id IN (b.copy_edge_id, b.source_edge_id, b.center_edge_id)
                OR a.source_edge_id IN (b.copy_edge_id, b.source_edge_id, b.center_edge_id)
                OR a.center_edge_id IN (b.copy_edge_id, b.source_edge_id, b.center_edge_id)
            ORDER BY a.cand_id, b.cand_id
            LIMIT 1;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        DELETE FROM pi_copy_gadget
        WHERE cand_id = overlapping_candidate_id;
    END LOOP;

    FOR copied_leg IN
        SELECT
                g.cand_id,
                g.center_edge_id,
                pi.type AS pi_type,
                center.id AS center_id,
                center.type AS center_type,
                center.qubit AS center_qubit,
                center.row AS center_row,
                CASE
                    WHEN get_id_from_link(center_edge.source) = g.center_id
                        THEN get_id_from_link(center_edge.target)
                    ELSE get_id_from_link(center_edge.source)
                END AS other_id,
                CASE
                    WHEN get_id_from_link(center_edge.source) = g.center_id
                        THEN get_type_from_link(center_edge.target)
                    ELSE get_type_from_link(center_edge.source)
                END AS other_type,
                center_edge.type AS outward_edge_type
            FROM pi_copy_gadget g
            JOIN zx_vertex pi
                ON pi.id = g.pi_id
            JOIN zx_vertex center
                ON center.id = g.center_id
            JOIN zx_edge center_edge
                ON center_edge.id = g.center_edge_id
            ORDER BY g.cand_id, g.center_edge_id
    LOOP
        INSERT INTO zx_vertex (type, qubit, row, param)
        VALUES (
            copied_leg.pi_type,
            copied_leg.center_qubit,
            copied_leg.center_row,
            1::double precision
        )
        RETURNING id INTO new_vertex_id;

        PERFORM zx_merge_edge(
            copied_leg.center_id,
            copied_leg.center_type,
            new_vertex_id,
            copied_leg.pi_type,
            zx_const_regular_edge()
        );

        PERFORM zx_merge_edge(
            new_vertex_id,
            copied_leg.pi_type,
            copied_leg.other_id,
            copied_leg.other_type,
            copied_leg.outward_edge_type
        );
    END LOOP;

    PERFORM zx_merge_edge(
        c.center_id,
        c.center_type,
        c.source_other_id,
        c.source_other_type,
        c.source_edge_type
    )
    FROM (
        SELECT DISTINCT ON (g.cand_id)
            g.cand_id,
            g.pi_id,
            g.center_id,
            center.type AS center_type,
            CASE
                WHEN get_id_from_link(source_edge.source) = g.pi_id
                    THEN get_id_from_link(source_edge.target)
                ELSE get_id_from_link(source_edge.source)
            END AS source_other_id,
            CASE
                WHEN get_id_from_link(source_edge.source) = g.pi_id
                    THEN get_type_from_link(source_edge.target)
                ELSE get_type_from_link(source_edge.source)
            END AS source_other_type,
            source_edge.type AS source_edge_type
        FROM pi_copy_gadget g
        JOIN zx_vertex center
            ON center.id = g.center_id
        JOIN zx_edge source_edge
            ON source_edge.id = g.source_edge_id
        ORDER BY g.cand_id
    ) c;

    -- Flip all centers
    UPDATE zx_vertex v
    SET param = -v.param
        FROM (SELECT DISTINCT center_id FROM pi_copy_gadget) c
        WHERE v.id = c.center_id;

    -- Delete all old edges
    DELETE FROM zx_edge e
    USING (
        SELECT copy_edge_id AS edge_id FROM pi_copy_gadget
        UNION
        SELECT source_edge_id AS edge_id FROM pi_copy_gadget
        UNION
        SELECT center_edge_id AS edge_id FROM pi_copy_gadget
    ) old_edges
    WHERE e.id = old_edges.edge_id;

    -- Delete consumed pi spiders
    DELETE FROM zx_vertex v
    USING (SELECT DISTINCT pi_id FROM pi_copy_gadget) old_pi
    WHERE v.id = old_pi.pi_id;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_pi_copy_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;
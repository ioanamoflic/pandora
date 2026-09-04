-- Fuse phase gadgets that share the same target set
CREATE OR REPLACE PROCEDURE zx_gadget_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    affected_count integer := 0;
BEGIN
    WITH candidates AS (
        SELECT
                targets.target_ids AS gadget_target_ids,
                phase_v.id AS gadget_phase_v_id,
                anchor.id AS gadget_anchor_v_id,
                phase_v.param AS gadget_phase_v_phase,
                anchor.param AS gadget_anchor_v_phase
            FROM zx_vertex phase_v
            JOIN LATERAL (
                SELECT
                    MIN(x.other_id) AS gadget_anchor_v_id,
                    COUNT(*) AS degree
                FROM (
                    SELECT ie.other_id
                    FROM zx_incident_edges(phase_v.id) ie
                    LIMIT 2
                ) x
            ) phase_v_neighbor
                ON phase_v_neighbor.degree = 1
            JOIN zx_vertex anchor
                ON anchor.id = phase_v_neighbor.gadget_anchor_v_id
            JOIN LATERAL (
                SELECT array_agg(DISTINCT ie2.other_id ORDER BY ie2.other_id) AS target_ids
                FROM zx_incident_edges(anchor.id) ie2
                WHERE NOT (
                    zx_edge_degree(ie2.other_id) = 1
                    AND NOT zx_phase_is_clifford((
                        SELECT param
                            FROM zx_vertex
                            WHERE id = ie2.other_id
                    ))
                )
            ) targets ON true
            WHERE phase_v.type = zx_const_z_spider()
                AND anchor.type = zx_const_z_spider()
                AND NOT zx_phase_is_clifford(phase_v.param)
                AND zx_phase_is_pauli(anchor.param)
                AND targets.target_ids IS NOT NULL
                AND array_length(targets.target_ids, 1) > 0
    ),
    groups AS (
        SELECT
            gadget_target_ids,
            COUNT(*)::integer AS group_size,
            MIN(gadget_phase_v_id) AS keep_phase_v_id,
            (array_agg(gadget_anchor_v_id ORDER BY gadget_phase_v_id))[1] AS keep_anchor_v_id,
            zx_normalize_phase(
                mod(
                    SUM(
                        CASE
                            WHEN zx_normalize_phase(gadget_anchor_v_phase) = 0::double precision
                                THEN gadget_phase_v_phase
                            ELSE -gadget_phase_v_phase
                        END
                    )::numeric,
                    2::numeric
                )::double precision
            ) AS total_phase,
            bool_or(zx_normalize_phase(gadget_anchor_v_phase) = 1::double precision) AS single_anchor_is_pi
        FROM candidates
        GROUP BY gadget_target_ids
    ),
    canonicalized_single_phase AS (
        UPDATE zx_vertex phase_v
        SET param = zx_normalize_phase(-phase_v.param)
            FROM candidates c
            JOIN groups g
                ON g.gadget_target_ids = c.gadget_target_ids
            WHERE g.group_size = 1
                AND g.single_anchor_is_pi
                AND phase_v.id = c.gadget_phase_v_id
        RETURNING 1
    ),
    canonicalized_single_anchor AS (
        UPDATE zx_vertex anchor
        SET param = 0::double precision
            FROM candidates c
            JOIN groups g
                ON g.gadget_target_ids = c.gadget_target_ids
            WHERE g.group_size = 1
                AND g.single_anchor_is_pi
                AND anchor.id = c.gadget_anchor_v_id
        RETURNING 1
    ),
    fused_phase AS (
        UPDATE zx_vertex phase_v
        SET param = g.total_phase
            FROM groups g
            WHERE g.group_size > 1
                AND phase_v.id = g.keep_phase_v_id
        RETURNING 1
    ),
    fused_anchor AS (
        UPDATE zx_vertex anchor
        SET param = 0::double precision
            FROM groups g
            WHERE g.group_size > 1
                AND anchor.id = g.keep_anchor_v_id
        RETURNING 1
    ),
    vertices_to_delete AS (
        SELECT c.gadget_phase_v_id AS id
            FROM candidates c
            JOIN groups g
                ON g.gadget_target_ids = c.gadget_target_ids
            WHERE g.group_size > 1
                AND c.gadget_phase_v_id <> g.keep_phase_v_id
        UNION
        SELECT c.gadget_anchor_v_id AS id
            FROM candidates c
            JOIN groups g
                ON g.gadget_target_ids = c.gadget_target_ids
            WHERE g.group_size > 1
                AND c.gadget_anchor_v_id <> g.keep_anchor_v_id
    ),
    deleted_edges AS (
        DELETE FROM zx_edge e
        USING vertices_to_delete v
        WHERE v.id = get_id_from_link(e.source)
            OR v.id = get_id_from_link(e.target)
        RETURNING 1
    ),
    deleted_vertices AS (
        DELETE FROM zx_vertex z
        USING vertices_to_delete v
        WHERE z.id = v.id
        RETURNING 1
    ),
    final_change_check AS (
        SELECT 1
        FROM groups
        WHERE group_size > 1 OR single_anchor_is_pi
        LIMIT 1
    )
    SELECT COUNT(*) INTO affected_count FROM final_change_check;

    IF affected_count > 0 THEN
        changed := true;
    END IF;
END;
$$;

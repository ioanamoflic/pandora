-- Recolour every X-spider to a Z-spider
CREATE OR REPLACE PROCEDURE zx_x_to_z(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    vertex_candidate record;
    locked_vertex record;
    incident_edge_ids bigint[];
    locked_edge_count integer;
    total_edge_count integer;
    round_changed boolean;
    converted_count integer;
BEGIN
    WITH x_vertices AS (
        SELECT v.id
            FROM zx_vertex v
            WHERE v.type = zx_const_x_spider()
    ),
    edge_matches AS (
        SELECT
            e.id AS edge_id,
            get_id_from_link(e.source) AS source_id,
            get_id_from_link(e.target) AS target_id,
            xs.id IS NOT NULL AS source_is_converted,
            xt.id IS NOT NULL AS target_is_converted
        FROM zx_edge e
        LEFT JOIN x_vertices xs
            ON xs.id = get_id_from_link(e.source)
        LEFT JOIN x_vertices xt
            ON xt.id = get_id_from_link(e.target)
        WHERE xs.id IS NOT NULL
            OR xt.id IS NOT NULL
    ),
    updated_vertices AS (
        UPDATE zx_vertex v
            SET type = zx_const_z_spider()
            FROM x_vertices x
            WHERE v.id = x.id
        RETURNING v.id
    ),
    updated_edges AS (
        UPDATE zx_edge e
        SET
            type = CASE
                -- Don't change edge type if both endpoints are converted, since both would cause a flip
                WHEN (em.source_is_converted <> em.target_is_converted)
                THEN CASE
                    WHEN e.type = zx_const_regular_edge()
                        THEN zx_const_hadamard_edge()
                    ELSE zx_const_regular_edge()
                END
                ELSE e.type
            END,
            source = CASE
                WHEN em.source_is_converted
                    THEN zx_vertex_ref(get_id_from_link(e.source), zx_const_z_spider())
                ELSE e.source
            END,
            target = CASE
                WHEN em.target_is_converted
                    THEN zx_vertex_ref(get_id_from_link(e.target), zx_const_z_spider())
                ELSE e.target
            END
        FROM edge_matches em
            WHERE e.id = em.edge_id
        RETURNING e.id
    )
    SELECT count(*)
    INTO converted_count
        FROM updated_vertices;

    IF converted_count > 0 THEN
        changed := true;
    END IF;
END;
$$;
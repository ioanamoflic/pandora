-- Drop self-loops on spiders
CREATE OR REPLACE PROCEDURE zx_remove_self_loops(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    deleted_count integer;
BEGIN
    rewrite_started_at := clock_timestamp();
    WITH self_loops AS (
        SELECT
            v.id AS vertex_id,
            e.id AS edge_id,
            e.type AS edge_type
        FROM zx_vertex v
        JOIN zx_edge e
            ON get_id_from_link(e.source) = v.id
           AND get_id_from_link(e.target) = v.id
        WHERE v.type IN (zx_const_z_spider(), zx_const_x_spider())
    ),
    phase_updates AS (
        SELECT
            vertex_id,
            COUNT(*) FILTER (WHERE edge_type = zx_const_hadamard_edge()) AS had_count
        FROM self_loops
        GROUP BY vertex_id
    ),
    updated_vertices AS (
        UPDATE zx_vertex v
        SET param = zx_normalize_phase(v.param + 1::double precision)
            FROM phase_updates p
            WHERE v.id = p.vertex_id
                AND mod(p.had_count, 2) = 1
        RETURNING v.id
    ),
    deleted_edges AS (
        DELETE FROM zx_edge e
        USING self_loops s
            WHERE e.id = s.edge_id
        RETURNING e.id
    )
    SELECT COUNT(*)::integer
    INTO deleted_count
        FROM deleted_edges;

    IF deleted_count > 0 THEN
        changed := true;
        rewrite_execution_count := rewrite_execution_count + 1;
    END IF;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_remove_self_loops', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;
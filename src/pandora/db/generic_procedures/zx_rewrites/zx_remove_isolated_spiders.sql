CREATE OR REPLACE PROCEDURE zx_remove_isolated_spiders(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    deleted_count integer := 0;
BEGIN
    rewrite_started_at := clock_timestamp();
    DELETE FROM zx_vertex v
        WHERE v.type IN (zx_const_z_spider(), zx_const_x_spider())
            AND NOT EXISTS (
                SELECT 1
                    FROM zx_edge e
                    WHERE get_id_from_link(e.source) = v.id
                        OR get_id_from_link(e.target) = v.id
            );

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    IF deleted_count > 0 THEN
        changed := true;
        rewrite_execution_count := rewrite_execution_count + 1;
    END IF;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_remove_isolated_spiders', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

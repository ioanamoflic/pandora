CREATE OR REPLACE PROCEDURE zx_remove_isolated_spiders(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count integer := 0;
BEGIN
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
    END IF;
END;
$$;

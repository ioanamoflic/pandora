-- Check whether the current X/Z spider colouring is bipartite, e.g. there are no edges connecting two spiders of the same colour
CREATE OR REPLACE FUNCTION zx_is_bipartite()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT NOT EXISTS (
        SELECT 1
            FROM zx_edge e
            WHERE get_type_from_link(e.source) IN (zx_const_z_spider(), zx_const_x_spider())
                AND get_type_from_link(e.target) IN (zx_const_z_spider(), zx_const_x_spider())
                AND get_type_from_link(e.source) = get_type_from_link(e.target)
    );
$$;
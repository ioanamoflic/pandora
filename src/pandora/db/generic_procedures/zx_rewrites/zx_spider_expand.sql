-- Spider unfusion
CREATE OR REPLACE PROCEDURE zx_spider_expand(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    v          record;
    leg        record;
    s_id       bigint;
BEGIN
    FOR v IN
        SELECT id, type, qubit, "row"
            FROM zx_vertex
            WHERE type IN (zx_const_z_spider(), zx_const_x_spider())
                AND zx_edge_degree(id) >= 3
    LOOP
        SELECT edge_id, edge_type, other_id, other_type
            INTO leg
            FROM zx_incident_edges(v.id)
            ORDER BY random()
            LIMIT 1;

        INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (v.type, v.qubit, v.row, 0)
            RETURNING id INTO s_id;

        PERFORM zx_merge_edge(s_id, v.type, leg.other_id, leg.other_type, leg.edge_type);
        PERFORM zx_merge_edge(v.id, v.type, s_id, v.type, zx_const_regular_edge());

        DELETE FROM zx_edge WHERE id = leg.edge_id;

        changed := true;
    END LOOP;
END;
$$;

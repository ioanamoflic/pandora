-- Identity insertion
CREATE OR REPLACE PROCEDURE zx_id_expand(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    edge record;
    s_id bigint;
    s_type smallint;
BEGIN
    FOR edge IN
        SELECT
                e.id AS edge_id,
                e.type AS edge_type,
                get_id_from_link(e.source) AS a_id,
                get_type_from_link(e.source) AS a_type,
                get_id_from_link(e.target) AS b_id,
                get_type_from_link(e.target) AS b_type,
                (sv.qubit + tv.qubit) / 2 AS qubit,
                (sv.row + tv.row) / 2 AS row
            FROM zx_edge e
            JOIN zx_vertex sv ON sv.id = get_id_from_link(e.source)
            JOIN zx_vertex tv ON tv.id = get_id_from_link(e.target)
    LOOP
        s_type := CASE WHEN random() < 0.5
                        THEN zx_const_z_spider()
                    ELSE zx_const_x_spider() END;
        INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (s_type, edge.qubit, edge.row, 0)
            RETURNING id INTO s_id;

        PERFORM zx_merge_edge(edge.a_id, edge.a_type, s_id, s_type, edge.edge_type);
        PERFORM zx_merge_edge(s_id, s_type, edge.b_id, edge.b_type, zx_const_regular_edge());

        -- Remove the original edge.
        DELETE FROM zx_edge WHERE id = edge.edge_id;

        changed := true;
    END LOOP;
END;
$$;

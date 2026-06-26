CREATE OR REPLACE FUNCTION zx_is_identity()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
SELECT NOT EXISTS (
    -- Every vertex is either an input or an output.
    SELECT true FROM zx_vertex v WHERE v.type NOT IN (zx_const_input_type(), zx_const_output_type())
    UNION ALL
    -- Each qubit has exactly one input and one output.
    SELECT true FROM zx_vertex v WHERE v.type IN (zx_const_input_type(), zx_const_output_type())
            GROUP BY v.type, v.qubit HAVING count(*) <> 1
    UNION ALL
    -- Every edge is a regular edge between an input and output on the same qubit
    SELECT true
        FROM zx_edge e
            LEFT JOIN zx_vertex s ON s.id = get_id_from_link(e.source)
            LEFT JOIN zx_vertex t ON t.id = get_id_from_link(e.target)
            WHERE e.type <> zx_const_regular_edge()
                OR s.id IS NULL OR t.id IS NULL
                OR s.qubit <> t.qubit
                OR s.type = t.type
    UNION ALL
    -- Every input/output vertex has exactly one edge
    SELECT true FROM zx_vertex v WHERE zx_edge_degree(v.id) <> 1
)
$$;
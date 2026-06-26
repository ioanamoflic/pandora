-- If the vertex type is known, we can create a link directly
CREATE OR REPLACE FUNCTION zx_vertex_ref(p_vertex_id bigint, p_vertex_type smallint)
RETURNS bigint
LANGUAGE plpgsql
IMMUTABLE PARALLEL SAFE
AS $$
BEGIN
    RETURN create_link(p_vertex_id, 0, p_vertex_type);
END;
$$;

-- If the vertex type is not known, we need to look it up.
CREATE OR REPLACE FUNCTION zx_vertex_ref(p_vertex_id bigint)
RETURNS bigint
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    vertex_type smallint;
BEGIN
    SELECT type INTO vertex_type
        FROM zx_vertex
        WHERE id = p_vertex_id;

    IF vertex_type IS NULL THEN
        RAISE EXCEPTION 'zx_vertex_ref cannot reference missing zx_vertex id %', p_vertex_id;
    END IF;

    RETURN zx_vertex_ref(p_vertex_id, vertex_type);
END;
$$;

-- Normalise a phase to [0, 2].
CREATE OR REPLACE FUNCTION zx_normalize_phase(p_phase real)
RETURNS real
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT COALESCE(
        mod(mod(p_phase::numeric, 2::numeric) + 2::numeric, 2::numeric)::real,
        0::real
    );
$$;

CREATE OR REPLACE FUNCTION zx_type_is_boundary(t smallint)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT t IN (zx_const_input_type(), zx_const_output_type());
$$;

CREATE OR REPLACE FUNCTION zx_type_is_zx_spider(t smallint)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT t IN (zx_const_z_spider(), zx_const_x_spider());
$$;

CREATE OR REPLACE FUNCTION zx_check_edge_order(
    source_id bigint,
    source_type smallint,
    target_id bigint,
    target_type smallint
)
RETURNS TABLE (
    source_id bigint,
    source_type smallint,
    target_id bigint,
    target_type smallint
)
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT source_id, source_type, target_id, target_type
        WHERE source_id <= target_id
    UNION ALL
    SELECT target_id, target_type, source_id, source_type
        WHERE source_id > target_id;
$$;

-- Count the number of edges on a vertex. A self-loop contributes 2.
CREATE OR REPLACE FUNCTION zx_edge_degree(p_vertex_id bigint)
RETURNS integer
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(SUM(cnt), 0)::integer
    FROM (
        SELECT COUNT(*) AS cnt
            FROM zx_edge
            WHERE get_id_from_link(source) = p_vertex_id
        UNION ALL
        SELECT COUNT(*) AS cnt
            FROM zx_edge
            WHERE get_id_from_link(target) = p_vertex_id
    ) AS counts;
$$;

CREATE OR REPLACE FUNCTION zx_incident_edges(p_vertex_id bigint)
RETURNS TABLE (
    edge_id bigint,
    edge_type smallint,
    other_id bigint,
    other_type smallint
)
LANGUAGE sql
STABLE
AS $$
    SELECT
            e.id,
            e.type,
            get_id_from_link(e.target) AS other_id,
            get_type_from_link(e.target) AS other_type
        FROM zx_edge e
        WHERE get_id_from_link(e.source) = p_vertex_id
    UNION ALL
    SELECT
            e.id,
            e.type,
            get_id_from_link(e.source) AS other_id,
            get_type_from_link(e.source) AS other_type
        FROM zx_edge e
        WHERE get_id_from_link(e.target) = p_vertex_id;
$$;

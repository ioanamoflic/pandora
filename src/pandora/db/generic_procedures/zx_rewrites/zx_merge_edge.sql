-- Add an edge between the given vertices, merging it with any existing edge and updating the phase of the source spider as needed.
CREATE OR REPLACE FUNCTION zx_merge_edge(
    p_source_id bigint,
    p_source_type smallint,
    p_target_id bigint,
    p_target_type smallint,
    p_edge_type smallint
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    source_id bigint;
    target_id bigint;
    source_type smallint;
    target_type smallint;
    existing_edge_id bigint;
    existing_edge_type smallint;
BEGIN
    IF p_source_id IS NULL OR p_target_id IS NULL OR p_source_type IS NULL OR p_target_type IS NULL OR p_edge_type IS NULL THEN
        RETURN false;
    END IF;

    -- If this would be a self-loop, ignore it or update the phase for a Hadamard edge
    IF p_source_id = p_target_id THEN
        IF p_edge_type = zx_const_hadamard_edge() AND p_source_type IN (zx_const_z_spider(), zx_const_x_spider()) THEN
            UPDATE zx_vertex
                SET param = zx_normalize_phase(param + 1::double precision)
                WHERE id = p_source_id;
        END IF;
        RETURN true;
    END IF;

    -- Keep the smaller id as source, so the existing_edge query doesn't need a "or source = target" check
    SELECT * INTO source_id, source_type, target_id, target_type
        FROM zx_check_edge_order(p_source_id, p_source_type, p_target_id, p_target_type);

    SELECT e.id, e.type
    INTO existing_edge_id, existing_edge_type
        FROM zx_edge e
        WHERE get_id_from_link(e.source) = source_id
            AND get_id_from_link(e.target) = target_id
        ORDER BY e.id
        LIMIT 1
        FOR UPDATE;

    -- There is no edge, insert a new one
    IF existing_edge_id IS NULL THEN
        INSERT INTO zx_edge(type, source, target)
        VALUES (
            p_edge_type,
            zx_vertex_ref(source_id, source_type),
            zx_vertex_ref(target_id, target_type)
        );
        RETURN true;
    END IF;

    -- If either vertex is not a spider and there is already an edge, just leave it
    IF source_type NOT IN (zx_const_z_spider(), zx_const_x_spider())
        OR target_type NOT IN (zx_const_z_spider(), zx_const_x_spider()) THEN
        RAISE EXCEPTION 'Cannot merge non-spider edges!';
    END IF;

    IF source_type = target_type THEN
        IF p_edge_type = zx_const_regular_edge() AND existing_edge_type = zx_const_regular_edge() THEN
            -- There already is the edge we want, do nothing
            RETURN true;
        ELSIF p_edge_type <> existing_edge_type THEN
            -- There is an edge but it's the wrong type, flip it and update the phase of the source spider
            UPDATE zx_edge
                SET type = zx_const_regular_edge()
                WHERE id = existing_edge_id;

            UPDATE zx_vertex
                SET param = zx_normalize_phase(param + 1::double precision)
                WHERE id = source_id;
                RETURN true;
        ELSIF p_edge_type = zx_const_hadamard_edge() AND existing_edge_type = zx_const_hadamard_edge() THEN
            /*
            There would be 2 H edges, which cancel out:
                Suppose there is
                    ...-- X --H-- X --...
                    ...-- X --H-- X --...
                We can push one H through the spider fusion rule to get
                    ...-- X ----- Z --H-...
                    ...-- X --HH- Z --H-...
                Then the HH edge is an identity and can be removed, leaving 2 normal edges between different colored spiders:
                    ...-- X ----- Z --H-...
                    ...-- X ----- Z --H-...
                These parallel edges can then be removed with the Hopf rule
                    ...-- X       Z --H-...
                    ...-- X       Z --H-...
                And finally, Z can absorb the H edges to become an X spider again:
                    ...-- X       X --...
                    ...-- X       X --...
            */
            DELETE FROM zx_edge WHERE id = existing_edge_id;
            RETURN true;
        END IF;
    ELSE
        IF p_edge_type = zx_const_hadamard_edge() AND existing_edge_type = zx_const_hadamard_edge() THEN
            RETURN true;
        ELSIF p_edge_type <> existing_edge_type THEN
            UPDATE zx_edge
            SET type = zx_const_hadamard_edge()
            WHERE id = existing_edge_id;

            UPDATE zx_vertex
            SET param = zx_normalize_phase(param + 1::double precision)
            WHERE id = source_id;
            RETURN true;
        ELSIF p_edge_type = zx_const_regular_edge() AND existing_edge_type = zx_const_regular_edge() THEN
            DELETE FROM zx_edge WHERE id = existing_edge_id;
            RETURN true;
        END IF;
    END IF;

    RETURN true;
END;
$$;
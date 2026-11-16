-- Fuse same-colour spiders connected by regular edges
CREATE OR REPLACE PROCEDURE zx_spider_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    rewired_edge record;
    component_count integer;
BEGIN
    rewrite_started_at := clock_timestamp();
    CREATE TEMP TABLE IF NOT EXISTS fuseable_spiders (
        comp_root   bigint,
        vertex_id   bigint PRIMARY KEY,
        vertex_type smallint
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS fuseable_spiders_comp_root_idx
        ON fuseable_spiders (comp_root);

    LOOP
        TRUNCATE fuseable_spiders;

        -- Connected fuseable_vertices of same-colour spiders joined by regular edges.
        WITH RECURSIVE candidates AS (
            SELECT
                    get_id_from_link(e.source) AS source_id,
                    get_id_from_link(e.target) AS target_id,
                    get_type_from_link(e.source) AS vertex_type
                FROM zx_edge e
                WHERE e.type = zx_const_regular_edge()
                    AND get_type_from_link(e.source) IN (zx_const_z_spider(), zx_const_x_spider())
                    AND get_type_from_link(e.target) = get_type_from_link(e.source)
        ),
        all_edges AS (
            SELECT source_id AS from_id, target_id AS to_id, vertex_type
                FROM candidates
            UNION ALL
            SELECT target_id AS from_id, source_id AS to_id, vertex_type
                FROM candidates
        ),
        vertices AS (
            SELECT source_id AS vertex_id, vertex_type FROM candidates
            UNION
            SELECT target_id AS vertex_id, vertex_type FROM candidates
        ),
        connected_vertices AS (
            SELECT vertex_id AS root_id, vertex_id, vertex_type
                FROM vertices
            UNION
            SELECT v.root_id, ue.to_id, v.vertex_type
                FROM connected_vertices v
                JOIN all_edges ue
                    ON ue.from_id = v.vertex_id
                    AND ue.vertex_type = v.vertex_type
        ),
        fuseable_vertices AS (
            -- Collapse each set of connected spiders to the lowest vertex ID
            SELECT
                    min(root_id) AS comp_root,
                    vertex_id,
                    vertex_type
                FROM connected_vertices
                GROUP BY vertex_id, vertex_type
        ),
        multiple_to_fuse AS (
            -- Only select where there are at least 2 spiders to fuse
            SELECT comp_root
                FROM fuseable_vertices
                GROUP BY comp_root
                HAVING count(*) > 1
        )
        INSERT INTO fuseable_spiders (comp_root, vertex_id, vertex_type)
        SELECT v.comp_root, v.vertex_id, v.vertex_type
            FROM fuseable_vertices v
            JOIN multiple_to_fuse f
                ON f.comp_root = v.comp_root;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        ANALYZE fuseable_spiders;

        -- Sum phases into each root spider
        UPDATE zx_vertex v
            SET param = x.new_param
            FROM (
                SELECT
                        s.comp_root,
                        zx_normalize_phase(sum(v.param)::double precision) AS new_param
                    FROM fuseable_spiders s
                    JOIN zx_vertex v
                        ON v.id = s.vertex_id
                    GROUP BY s.comp_root
            ) x
            WHERE v.id = x.comp_root;

        FOR rewired_edge IN
            WITH fuseable_without_root AS (
                SELECT *
                    FROM fuseable_spiders
                    WHERE vertex_id <> comp_root
            )
            SELECT
                    e.type as edge_type,
                    -- Source is the connected spider if it exists, otherwise this end is connected to a to-be fused spider and will be rewired to the root
                    COALESCE(source_component.comp_root, get_id_from_link(e.source)) AS source_id,
                    COALESCE(source_component.vertex_type, get_type_from_link(e.source)) AS source_type,
                    COALESCE(target_component.comp_root, get_id_from_link(e.target)) AS target_id,
                    COALESCE(target_component.vertex_type, get_type_from_link(e.target)) AS target_type
                FROM zx_edge e
                LEFT JOIN fuseable_without_root source_component
                    ON source_component.vertex_id = get_id_from_link(e.source)
                LEFT JOIN fuseable_without_root target_component
                    ON target_component.vertex_id = get_id_from_link(e.target)
                WHERE (source_component.vertex_id IS NOT NULL OR target_component.vertex_id IS NOT NULL)
                AND (
                    COALESCE(source_component.comp_root, get_id_from_link(e.source))
                        <> COALESCE(target_component.comp_root, get_id_from_link(e.target))
                    OR e.type = zx_const_hadamard_edge()
                )
        LOOP
            PERFORM zx_merge_edge(
                rewired_edge.source_id,
                rewired_edge.source_type,
                rewired_edge.target_id,
                rewired_edge.target_type,
                rewired_edge.edge_type
            );
        END LOOP;

        DELETE FROM zx_edge e
            USING fuseable_spiders s
            WHERE s.vertex_id <> s.comp_root
                AND (get_id_from_link(e.source) = s.vertex_id
                    OR get_id_from_link(e.target) = s.vertex_id);

        DELETE FROM zx_vertex v
            USING fuseable_spiders s
            WHERE s.vertex_id <> s.comp_root
                AND v.id = s.vertex_id;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_spider_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;

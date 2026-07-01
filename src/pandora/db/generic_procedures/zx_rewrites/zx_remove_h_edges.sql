-- Eliminate H-edges by turning Z-spiders to X-spiders. If color toggling cannot remove all H-edges, then the rest are expanded using Euler/Hadamard decomposition.
CREATE OR REPLACE PROCEDURE zx_remove_h_edges(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    toggled_count integer := 0;
    recoloured_edges integer := 0;

    h_edge record;
    new_type smallint;
    phase_add real;
    w1_id bigint;
    w2_id bigint;
    w3_id bigint;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM zx_edge WHERE type = zx_const_hadamard_edge()) THEN
        RETURN;
    END IF;

    WITH RECURSIVE
    edges AS (
        SELECT
            e.id,
            e.type AS edge_type,
            get_id_from_link(e.source) AS source_id,
            get_id_from_link(e.target) AS target_id,
            CASE WHEN e.type = zx_const_hadamard_edge() THEN 1 ELSE 0 END AS edge_h
        FROM zx_edge e
    ),
    undirected_edges AS (
        SELECT source_id AS from_id, target_id AS to_id, edge_h FROM edges
        UNION ALL
        SELECT target_id AS from_id, source_id AS to_id, edge_h FROM edges
    ),
    affected_vertices AS (
        SELECT vertex_id
        FROM (
            SELECT source_id AS vertex_id FROM edges WHERE edge_h = 1
            UNION
            SELECT target_id AS vertex_id FROM edges WHERE edge_h = 1
        ) h
        UNION
        SELECT ue.to_id
            FROM affected_vertices av
            JOIN undirected_edges ue
                ON ue.from_id = av.vertex_id
    ),
    component_walk AS (
        SELECT vertex_id AS root_id, vertex_id
            FROM affected_vertices
        UNION
        SELECT cw.root_id, ue.to_id
            FROM component_walk cw
            JOIN undirected_edges ue
                ON ue.from_id = cw.vertex_id
    ),
    components AS (
        SELECT min(root_id) AS comp_root, vertex_id
            FROM component_walk
            GROUP BY vertex_id
    ),
    vertices AS (
        SELECT
            v.id AS vertex_id,
            v.type AS vertex_type,
            v.type NOT IN (zx_const_z_spider(), zx_const_x_spider()) AS is_fixed
        FROM zx_vertex v
        JOIN affected_vertices av
            ON av.vertex_id = v.id
    ),
    component_seeds AS (
        SELECT vertex_id, 0 AS toggle
            FROM vertices
            WHERE is_fixed
        UNION
        SELECT min(c.vertex_id), 0
            FROM components c
            WHERE NOT EXISTS (
                SELECT 1
                FROM vertices v
                JOIN components cv
                    ON cv.vertex_id = v.vertex_id
                WHERE v.is_fixed
                    AND cv.comp_root = c.comp_root
            )
            GROUP BY c.comp_root
    ),
    assignments AS (
        SELECT vertex_id, toggle
            FROM component_seeds
        UNION
        SELECT ue.to_id, (a.toggle + ue.edge_h) % 2
            FROM assignments a
            JOIN undirected_edges ue
                ON ue.from_id = a.vertex_id
    ),
    conflict_vertices AS (
        SELECT vertex_id
            FROM assignments
            GROUP BY vertex_id
            HAVING count(DISTINCT toggle) > 1
    ),
    final_assignments AS (
        SELECT a.vertex_id, min(a.toggle) AS toggle
        FROM assignments a
        JOIN components c
            ON c.vertex_id = a.vertex_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM conflict_vertices cv
            JOIN components cc
                ON cc.vertex_id = cv.vertex_id
            WHERE cc.comp_root = c.comp_root
        )
        GROUP BY a.vertex_id
    ),
    toggled_spiders AS (
        SELECT
            v.vertex_id,
            CASE
                WHEN v.vertex_type = zx_const_z_spider() THEN zx_const_x_spider()
                ELSE zx_const_z_spider()
            END AS new_vertex_type
        FROM vertices v
        JOIN final_assignments a
            ON a.vertex_id = v.vertex_id
        WHERE a.toggle = 1 AND v.vertex_type IN (zx_const_z_spider(), zx_const_x_spider())
    ),
    edge_toggles AS (
        SELECT
            e.id AS edge_id,
            e.source_id,
            e.target_id,
            CASE
                WHEN s.vertex_id IS NOT NULL THEN zx_vertex_ref(e.source_id, s.new_vertex_type)
            END AS new_source,
            CASE
                WHEN t.vertex_id IS NOT NULL THEN zx_vertex_ref(e.target_id, t.new_vertex_type)
            END AS new_target,
            CASE
                WHEN (s.vertex_id IS NOT NULL) <> (t.vertex_id IS NOT NULL) THEN
                    CASE
                        WHEN e.edge_type = zx_const_regular_edge() THEN zx_const_hadamard_edge()
                        ELSE zx_const_regular_edge()
                    END
                ELSE e.edge_type
            END AS new_edge_type
        FROM edges e
        LEFT JOIN toggled_spiders s
            ON s.vertex_id = e.source_id
        LEFT JOIN toggled_spiders t
            ON t.vertex_id = e.target_id
        WHERE s.vertex_id IS NOT NULL
            OR t.vertex_id IS NOT NULL
    ),
    updated_vertices AS (
        UPDATE zx_vertex v
        SET type = t.new_vertex_type
            FROM toggled_spiders t
            WHERE v.id = t.vertex_id
        RETURNING v.id
    ),
    updated_edges AS (
        UPDATE zx_edge e
        SET
            type = et.new_edge_type,
            source = COALESCE(et.new_source, e.source),
            target = COALESCE(et.new_target, e.target)
        FROM edge_toggles et
        WHERE e.id = et.edge_id
        RETURNING e.id
    )
    SELECT
        (SELECT count(*) FROM updated_vertices),
        (SELECT count(*) FROM updated_edges)
    INTO toggled_count, recoloured_edges;

    IF toggled_count > 0 THEN
        changed := true;
    END IF;

    -- Expand remaining Hadamard edges using Euler decomposition
    FOR h_edge IN
        SELECT
                e.id AS edge_id,
                s.id AS source_id,
                s.type AS source_type,
                s.param AS source_param,
                t.id AS target_id,
                t.type AS target_type,
                t.param AS target_param,
                s.qubit AS qubit,
                s."row" AS "row"
            FROM zx_edge e
            JOIN zx_vertex s
                ON s.id = get_id_from_link(e.source)
            JOIN zx_vertex t
                ON t.id = get_id_from_link(e.target)
            WHERE e.type = zx_const_hadamard_edge()
    LOOP
        DELETE FROM zx_edge WHERE id = h_edge.edge_id;

        IF h_edge.source_type IN (zx_const_z_spider(), zx_const_x_spider())
            AND h_edge.target_type IN (zx_const_z_spider(), zx_const_x_spider())
            AND h_edge.source_type = h_edge.target_type
        THEN
            -- Same-colour ZX endpoints
            -- If either endpoint phase is pi/2, add 3/2 to make it 2 % 2 = 0
            new_type := CASE
                WHEN h_edge.source_type = zx_const_z_spider() THEN zx_const_x_spider()
                ELSE zx_const_z_spider()
            END;

            IF h_edge.source_param = 0.5 OR h_edge.target_param = 0.5
            THEN
                phase_add := 1.5;
            ELSE
                phase_add := 0.5;
            END IF;

            UPDATE zx_vertex v
            SET param = zx_normalize_phase((v.param + phase_add)::real)
                WHERE v.id IN (h_edge.source_id, h_edge.target_id);

            INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (new_type, h_edge.qubit, h_edge.row, phase_add)
            RETURNING id INTO w1_id;

            PERFORM zx_merge_edge(
                h_edge.source_id,
                h_edge.source_type,
                w1_id,
                new_type,
                zx_const_regular_edge()
            );

            PERFORM zx_merge_edge(
                w1_id,
                new_type,
                h_edge.target_id,
                h_edge.target_type,
                zx_const_regular_edge()
            );
        ELSE
            -- Mixed-colour or non-ZX endpoint
            INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (zx_const_z_spider(), h_edge.qubit, h_edge.row, 0.5)
            RETURNING id INTO w1_id;

            INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (zx_const_x_spider(), h_edge.qubit, h_edge.row, 0.5)
            RETURNING id INTO w2_id;

            INSERT INTO zx_vertex(type, qubit, "row", param)
            VALUES (zx_const_z_spider(), h_edge.qubit, h_edge.row, 0.5)
            RETURNING id INTO w3_id;

            PERFORM zx_merge_edge(
                h_edge.source_id,
                h_edge.source_type,
                w3_id,
                zx_const_z_spider(),
                zx_const_regular_edge()
            );

            PERFORM zx_merge_edge(
                w3_id,
                zx_const_z_spider(),
                w2_id,
                zx_const_x_spider(),
                zx_const_regular_edge()
            );

            PERFORM zx_merge_edge(
                w2_id,
                zx_const_x_spider(),
                w1_id,
                zx_const_z_spider(),
                zx_const_regular_edge()
            );

            PERFORM zx_merge_edge(
                w1_id,
                zx_const_z_spider(),
                h_edge.target_id,
                h_edge.target_type,
                zx_const_regular_edge()
            );
        END IF;

        changed := true;
    END LOOP;

    -- We might have created parallel same-color spriders, so merge those
    IF changed THEN
        CALL zx_spider_simp(changed);
    END IF;
END;
$$;

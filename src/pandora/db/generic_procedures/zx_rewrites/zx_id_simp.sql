-- Remove identity spiders (zero-phase degree-2 spiders), contracting each chain into a single edge
CREATE OR REPLACE PROCEDURE zx_id_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    path_count      integer;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS identity_edges (
        vertex_id     bigint,
        edge_id       bigint,
        edge_type     smallint,
        neighbor_link bigint,
        PRIMARY KEY (vertex_id, edge_id)
    ) ON COMMIT DROP;

    CREATE TEMP TABLE IF NOT EXISTS identity_chains (
        start_link    bigint,
        end_link      bigint,
        new_edge_type smallint,
        edge_ids      bigint[],
        vertex_ids    bigint[]
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS tmp_identity_incident_neighbor_idx
        ON identity_edges (get_id_from_link(neighbor_link));

    LOOP
        TRUNCATE identity_edges;
        TRUNCATE identity_chains;

        INSERT INTO identity_edges (vertex_id, edge_id, edge_type, neighbor_link)
        SELECT
                ie.vertex_id,
                ie.edge_id,
                ie.edge_type,
                ie.neighbor_link
            FROM (
                SELECT
                        v.id AS vertex_id,
                        e.id AS edge_id,
                        e.type AS edge_type,
                        CASE WHEN get_id_from_link(e.source) = v.id THEN e.target ELSE e.source END AS neighbor_link,
                        count(*) OVER (PARTITION BY v.id) AS degree
                    FROM zx_vertex v
                    JOIN zx_edge e
                        ON get_id_from_link(e.source) = v.id
                            OR get_id_from_link(e.target) = v.id
                    WHERE zx_phase_is_zero(v.param)
                        AND v.type IN (zx_const_z_spider(), zx_const_x_spider())
            ) ie
            WHERE ie.degree = 2;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        -- Find the longest possible chains of identity edges
        WITH RECURSIVE identity_spiders AS (
            SELECT DISTINCT vertex_id
                FROM identity_edges
        ), chain AS (
            -- Start case: An edge with a non-identity neighbor
            SELECT
                    i.edge_id AS start_edge_id,
                    i.neighbor_link AS start_link,

                    i.edge_id AS previous_edge_id,
                    ARRAY[i.edge_id]::bigint[] AS edge_ids,
                    CASE WHEN i.edge_type = zx_const_hadamard_edge() THEN 1 ELSE 0 END AS hadamard_count,

                    i.vertex_id AS current_vertex,
                    ARRAY[i.vertex_id]::bigint[] AS vertex_ids,
                    NULL::bigint  AS end_edge_id,
                    NULL::bigint  AS end_link
                FROM identity_edges i
                LEFT JOIN identity_spiders neighbor
                    ON neighbor.vertex_id = get_id_from_link(i.neighbor_link)
                WHERE neighbor.vertex_id IS NULL
            UNION ALL
            SELECT
                    -- Constants
                    c.start_edge_id,
                    c.start_link,

                    -- Edges
                    next_edge.edge_id AS previous_edge_id,
                    c.edge_ids || next_edge.edge_id,
                    c.hadamard_count + CASE WHEN next_edge.edge_type = zx_const_hadamard_edge() THEN 1 ELSE 0 END AS hadamard_count,

                    -- Vertices
                    CASE WHEN next_neighbor.vertex_id IS NULL THEN NULL ELSE get_id_from_link(next_edge.neighbor_link) END AS current_vertex,
                    CASE WHEN next_neighbor.vertex_id IS NULL THEN c.vertex_ids ELSE c.vertex_ids || (get_id_from_link(next_edge.neighbor_link)) END AS vertex_ids,
                    CASE WHEN next_neighbor.vertex_id IS NULL THEN next_edge.edge_id ELSE NULL END AS end_edge_id,
                    CASE WHEN next_neighbor.vertex_id IS NULL THEN next_edge.neighbor_link ELSE NULL END AS end_link
                FROM chain c
                -- Join the edge starting from the current vertex and not the previous edge.
                JOIN identity_edges next_edge
                    ON next_edge.vertex_id = c.current_vertex
                    AND next_edge.edge_id <> c.previous_edge_id
                LEFT JOIN identity_spiders next_neighbor
                    ON next_neighbor.vertex_id = get_id_from_link(next_edge.neighbor_link)
                -- Iterate until we reach a non-identity neighbor
                WHERE c.end_edge_id IS NULL
        )
        INSERT INTO identity_chains (start_link, end_link, new_edge_type, edge_ids, vertex_ids)
        SELECT
            start_link,
            end_link,
            -- The new edge type is hadamard only if there are an odd number of hadamard edges in the chain as H^2 = I.
            CASE
                WHEN hadamard_count % 2 = 0
                    THEN zx_const_regular_edge()
                ELSE zx_const_hadamard_edge()
            END AS new_edge_type,
            edge_ids,
            vertex_ids
        FROM chain
            WHERE end_edge_id IS NOT NULL
                AND get_id_from_link(start_link) < get_id_from_link(end_link);

        IF NOT FOUND THEN
            EXIT;
        END IF;

        DELETE FROM zx_edge e
        USING (SELECT DISTINCT unnest(edge_ids) AS edge_id FROM identity_chains) ids
            WHERE e.id = ids.edge_id;

        DELETE FROM zx_vertex v
        USING (SELECT DISTINCT unnest(vertex_ids) AS vertex_id FROM identity_chains) ids
            WHERE v.id = ids.vertex_id;

        PERFORM zx_merge_edge(
            get_id_from_link(removed_chain.start_link),
            get_type_from_link(removed_chain.start_link),
            get_id_from_link(removed_chain.end_link),
            get_type_from_link(removed_chain.end_link),
            removed_chain.new_edge_type
        )
        FROM identity_chains AS removed_chain;

        changed := true;
    END LOOP;
END;
$$;
-- Copy a Pauli leaf spider through its single edge
CREATE OR REPLACE PROCEDURE zx_copy_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    rewrite_started_at timestamptz;
    rewrite_execution_count bigint := 0;
    candidate record;
    replacement record;
    new_vertex_id bigint;
    round_changed boolean;
BEGIN
    rewrite_started_at := clock_timestamp();
    LOOP
        round_changed := false;
        FOR candidate IN
            WITH leaf_edges AS (
                SELECT
                    v.id AS leaf_id,
                    v.type AS leaf_type,
                    v.param AS source_phase,

                    e.id AS copy_edge_id,
                    e.type AS copy_edge_type,

                    CASE
                        WHEN get_id_from_link(e.source) = v.id THEN e.target
                        ELSE e.source
                    END AS neighbor_link
                FROM zx_vertex v
                JOIN zx_edge e
                    ON v.id IN (get_id_from_link(e.source), get_id_from_link(e.target))
                WHERE zx_type_is_zx_spider(v.type)
                    AND zx_phase_is_pauli(v.param)
                    AND zx_edge_degree(v.id) = 1
            ),
            copy_candidates AS (
                SELECT
                    e.leaf_id,
                    neighbor.id AS neighbor_id,
                    e.copy_edge_id,

                    CASE
                        WHEN e.copy_edge_type = zx_const_hadamard_edge()
                        THEN CASE
                            WHEN e.leaf_type = zx_const_z_spider()
                            THEN zx_const_x_spider()
                            ELSE zx_const_z_spider()
                        END
                        ELSE e.leaf_type
                    END AS copy_type,

                    e.source_phase,
                    neighbor.qubit AS neighbor_qubit,
                    neighbor.row AS neighbor_row
                FROM leaf_edges e
                JOIN zx_vertex neighbor
                    ON neighbor.id = get_id_from_link(e.neighbor_link)
                WHERE zx_type_is_zx_spider(neighbor.type)
                  AND ((e.copy_edge_type = zx_const_hadamard_edge()
                            AND neighbor.type = e.leaf_type)
                        OR (e.copy_edge_type <> zx_const_hadamard_edge()
                            AND neighbor.type <> e.leaf_type))
            ),
            -- Group by the neighbor, e.g. if 2 leaves connect to same neighbor
            candidate_ranks AS (
                SELECT
                    c.*,
                    row_number() OVER (
                        PARTITION BY c.neighbor_id
                        ORDER BY c.leaf_id, c.copy_edge_id
                    ) AS neighbor_rank,
                    row_number() OVER (
                        PARTITION BY c.copy_edge_id
                        ORDER BY c.leaf_id, c.neighbor_id
                    ) AS edge_rank
                FROM copy_candidates c
            ),
            -- Choose only single neighbor and e
            chosen_candidates AS (
                SELECT *
                    FROM candidate_ranks
                    WHERE neighbor_rank = 1 AND edge_rank = 1
            ),
            vertices_to_delete AS (
                SELECT leaf_id AS vertex_id
                    FROM chosen_candidates
                UNION
                SELECT neighbor_id AS vertex_id
                    FROM chosen_candidates
            ),
            -- Find vertices which connect to another to-be deleted one
            conflicting_neighbors AS (
                SELECT DISTINCT
                    c.neighbor_id
                    FROM chosen_candidates c
                    JOIN zx_edge e
                        ON c.neighbor_id IN (get_id_from_link(e.source), get_id_from_link(e.target))
                    JOIN vertices_to_delete deleted
                        ON deleted.vertex_id = CASE
                            WHEN get_id_from_link(e.source) = c.neighbor_id
                                THEN get_id_from_link(e.target)
                            ELSE get_id_from_link(e.source)
                    END
                    WHERE e.id <> c.copy_edge_id
            ),
            -- Drop the conflicting vertices
            non_conflicting_candidates AS (
                SELECT c.*
                    FROM chosen_candidates c
                    WHERE NOT EXISTS (
                        SELECT 1
                            FROM conflicting_neighbors n
                            WHERE n.neighbor_id = c.neighbor_id
                    )
            ),
            -- If there are no safe candidates, choose one to advance
            fallback_candidate AS (
                SELECT c.*
                    FROM copy_candidates c
                    WHERE NOT EXISTS (SELECT 1 FROM non_conflicting_candidates )
                    LIMIT 1
            ),
            final_candidates AS (
                SELECT
                        c.leaf_id,
                        c.neighbor_id,
                        c.copy_edge_id,
                        c.copy_type,
                        c.source_phase,
                        c.neighbor_qubit,
                        c.neighbor_row
                    FROM non_conflicting_candidates c
                UNION ALL
                SELECT
                        f.leaf_id,
                        f.neighbor_id,
                        f.copy_edge_id,
                        f.copy_type,
                        f.source_phase,
                        f.neighbor_qubit,
                        f.neighbor_row
                    FROM fallback_candidate f
            )
            SELECT
                    row_number() OVER (ORDER BY leaf_id, copy_edge_id) AS candidate_id,
                    leaf_id,
                    neighbor_id,
                    copy_edge_id,
                    copy_type,
                    source_phase,
                    neighbor_qubit,
                    neighbor_row
                FROM final_candidates
                ORDER BY leaf_id, copy_edge_id
        LOOP
            FOR replacement IN
                SELECT
                    CASE
                        WHEN get_id_from_link(e.source) = candidate.neighbor_id
                            THEN get_id_from_link(e.target)
                        ELSE get_id_from_link(e.source)
                    END AS other_id,
                    CASE
                        WHEN get_id_from_link(e.source) = candidate.neighbor_id
                            THEN get_type_from_link(e.target)
                        ELSE get_type_from_link(e.source)
                    END AS other_type,
                    e.type AS edge_type
                FROM zx_edge e
                WHERE e.id <> candidate.copy_edge_id
                  AND (
                        get_id_from_link(e.source) = candidate.neighbor_id
                        OR get_id_from_link(e.target) = candidate.neighbor_id
                      )
                ORDER BY e.id
            LOOP
                -- Insert and connect the copied vertex
                INSERT INTO zx_vertex (type, qubit, row, param)
                    VALUES (candidate.copy_type, candidate.neighbor_qubit, candidate.neighbor_row, candidate.source_phase)
                RETURNING id INTO new_vertex_id;

                PERFORM zx_merge_edge(
                    replacement.other_id,
                    replacement.other_type,
                    new_vertex_id,
                    candidate.copy_type,
                    replacement.edge_type
                );
            END LOOP;

            DELETE FROM zx_edge e
            WHERE get_id_from_link(e.source) IN (candidate.leaf_id, candidate.neighbor_id)
                OR get_id_from_link(e.target) IN (candidate.leaf_id, candidate.neighbor_id);

            DELETE FROM zx_vertex vertex
            WHERE vertex.id IN (candidate.leaf_id, candidate.neighbor_id);
            
            round_changed := true;
        END LOOP;
        IF NOT round_changed THEN
            EXIT;
        END IF;

        changed := true;

        rewrite_execution_count := rewrite_execution_count + 1;
    END LOOP;
    INSERT INTO public.zx_rewrite_runs (procedure_name, started_at, execution_count, elapsed_seconds)
    VALUES ('zx_copy_simp', rewrite_started_at, rewrite_execution_count,
            EXTRACT(EPOCH FROM clock_timestamp() - rewrite_started_at));
END;
$$;
-- Local complementation: remove proper-Clifford Z-spiders, toggling edges among their neighbours
CREATE OR REPLACE PROCEDURE zx_lcomp_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    batch_count integer;
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS lcomp_remaining_candidates (
        vertex_id bigint PRIMARY KEY,
        phase double precision
    ) ON COMMIT DROP;

    CREATE TEMP TABLE IF NOT EXISTS lcomp_chosen_neighbors (
        candidate_id bigint NOT NULL,
        candidate_phase double precision,
        neighbor_id bigint NOT NULL,
        neighbor_type smallint NOT NULL
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS lcomp_chosen_neighbors_candidate_id ON lcomp_chosen_neighbors(candidate_id, neighbor_id);

    LOOP
        TRUNCATE
            lcomp_remaining_candidates,
            lcomp_chosen_neighbors;

        INSERT INTO lcomp_remaining_candidates (vertex_id, phase)
        SELECT
                v.id,
                v.param
            FROM zx_vertex AS v
            WHERE v.type = zx_const_z_spider()
                AND zx_phase_is_proper_clifford(v.param)
                AND NOT EXISTS (
                    SELECT 1
                    FROM zx_incident_edges(v.id) AS ie
                    WHERE ie.edge_type <> zx_const_hadamard_edge()
                        OR ie.other_type <> zx_const_z_spider()
                );

        IF NOT FOUND THEN
            EXIT;
        END IF;

        -- Select maximal sets of candidates where none is part of another's neighbourhood
        LOOP
            WITH selected AS (
                SELECT
                    c.vertex_id AS candidate_id,
                    c.phase AS candidate_phase
                FROM lcomp_remaining_candidates AS c
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM zx_incident_edges(c.vertex_id) AS ie
                    JOIN lcomp_remaining_candidates AS lower_candidate
                        ON lower_candidate.vertex_id = ie.other_id
                    WHERE lower_candidate.vertex_id < c.vertex_id
                )
            ),
            selected_edges AS (
                SELECT
                    s.candidate_id,
                    s.candidate_phase,
                    ie.other_id,
                    ie.other_type
                FROM selected AS s
                CROSS JOIN LATERAL zx_incident_edges(s.candidate_id) AS ie
            ),
            inserted_neighbors AS (
                INSERT INTO lcomp_chosen_neighbors (
                    candidate_id,
                    candidate_phase,
                    neighbor_id,
                    neighbor_type
                )
                SELECT
                    candidate_id,
                    candidate_phase,
                    other_id,
                    other_type
                FROM selected_edges
            ),
            deleted_candidates AS (
                DELETE FROM lcomp_remaining_candidates AS c
                USING (
                    SELECT candidate_id AS vertex_id FROM selected
                    UNION
                    SELECT other_id AS vertex_id FROM selected_edges
                ) AS removed
                WHERE c.vertex_id = removed.vertex_id
            )
            SELECT COUNT(*) INTO batch_count FROM selected;

            EXIT WHEN batch_count = 0;
        END LOOP;

        IF NOT EXISTS (SELECT 1 FROM lcomp_chosen_neighbors) THEN
            EXIT;
        END IF;

        UPDATE zx_vertex AS v
        SET param = zx_normalize_phase(v.param - phase_updates.delta)
            FROM (
                SELECT
                    neighbor_id,
                    SUM(candidate_phase)::double precision AS delta
                FROM lcomp_chosen_neighbors
                GROUP BY neighbor_id
            ) AS phase_updates
            WHERE v.id = phase_updates.neighbor_id;

        DELETE FROM zx_edge AS e
        USING lcomp_chosen_neighbors AS ch
        WHERE get_id_from_link(e.source) = ch.candidate_id
            OR get_id_from_link(e.target) = ch.candidate_id;

        DELETE FROM zx_vertex AS v
        USING lcomp_chosen_neighbors AS ch
            WHERE v.id = ch.candidate_id;

        PERFORM zx_merge_edge(
            toggles.a_id,
            toggles.a_type,
            toggles.b_id,
            toggles.b_type,
            zx_const_hadamard_edge()
        )
        FROM (
            SELECT
                n1.neighbor_id AS a_id,
                MIN(n1.neighbor_type)::smallint AS a_type,
                n2.neighbor_id AS b_id,
                MIN(n2.neighbor_type)::smallint AS b_type
            FROM lcomp_chosen_neighbors AS n1
            JOIN lcomp_chosen_neighbors AS n2 ON n2.candidate_id = n1.candidate_id
                AND n1.neighbor_id < n2.neighbor_id
            GROUP BY n1.neighbor_id, n2.neighbor_id
            HAVING COUNT(*) % 2 = 1
        ) AS toggles;

        changed := true;
    END LOOP;
END;
$$;
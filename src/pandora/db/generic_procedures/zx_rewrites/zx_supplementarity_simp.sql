-- Remove pairs of non-Clifford Z-spiders that share a neighbourhood
CREATE OR REPLACE PROCEDURE zx_supplementarity_simp(INOUT changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS zx_supp_chosen (
        v_id bigint NOT NULL,
        w_id bigint NOT NULL,
        match_type smallint NOT NULL,
        v_phase real NOT NULL,
        w_phase real NOT NULL,
        neighbor_id bigint
    ) ON COMMIT DROP;

    CREATE INDEX IF NOT EXISTS zx_supp_chosen_v_idx
        ON zx_supp_chosen (v_id);

    CREATE INDEX IF NOT EXISTS zx_supp_chosen_w_idx
        ON zx_supp_chosen (w_id);

    CREATE INDEX IF NOT EXISTS zx_supp_chosen_neighbor_idx
        ON zx_supp_chosen (neighbor_id);

    LOOP
        TRUNCATE zx_supp_chosen;

        WITH candidates AS (
            SELECT
                v.id,
                v.param AS phase,
                COALESCE(
                    array_agg(ie.other_id ORDER BY ie.other_id, ie.edge_type)
                        FILTER (WHERE ie.other_id IS NOT NULL),
                    ARRAY[]::bigint[]
                ) AS nbr_ids,
                COALESCE(
                    array_agg(
                        ie.other_id::text || ':' || ie.edge_type::text
                        ORDER BY ie.other_id, ie.edge_type
                    ) FILTER (WHERE ie.other_id IS NOT NULL),
                    ARRAY[]::text[]
                ) AS nbr_key
            FROM zx_vertex AS v
            LEFT JOIN LATERAL zx_incident_edges(v.id) AS ie ON true
            WHERE v.type = zx_const_z_spider()
              AND NOT zx_phase_is_clifford(v.param)
            GROUP BY v.id, v.param
        ),
        potential AS (
            SELECT
                row_number() OVER (ORDER BY match_type, v_id, w_id) AS seq,
                v_id,
                w_id,
                match_type,
                v_phase,
                w_phase,
                neighbors,
                ARRAY[v_id, w_id]::bigint[] || neighbors AS blocked_ids
            FROM (
                SELECT
                    v.id AS v_id,
                    w.id AS w_id,
                    1::smallint AS match_type,
                    v.phase AS v_phase,
                    w.phase AS w_phase,
                    v.nbr_ids AS neighbors
                FROM candidates AS v
                JOIN candidates AS w
                  ON w.id > v.id
                 AND w.nbr_key = v.nbr_key
                WHERE zx_normalize_phase(v.phase - w.phase) = 1::real
                   OR zx_normalize_phase(v.phase + w.phase) = 1::real

                UNION ALL

                SELECT
                    v.id AS v_id,
                    w.id AS w_id,
                    2::smallint AS match_type,
                    v.phase AS v_phase,
                    w.phase AS w_phase,
                    (
                        SELECT COALESCE(array_agg(n.neighbor_id ORDER BY n.neighbor_id, n.edge_key), ARRAY[]::bigint[])
                        FROM unnest(v.nbr_ids, v.nbr_key) AS n(neighbor_id, edge_key)
                        WHERE n.neighbor_id <> w.id
                    ) AS neighbors
                FROM candidates AS v
                CROSS JOIN LATERAL unnest(v.nbr_ids, v.nbr_key) AS vn(w_id, edge_key)
                JOIN candidates AS w
                  ON w.id = vn.w_id
                 AND w.id > v.id
                WHERE (
                        SELECT COALESCE(array_agg(n.edge_key ORDER BY n.neighbor_id, n.edge_key), ARRAY[]::text[])
                        FROM unnest(v.nbr_ids, v.nbr_key) AS n(neighbor_id, edge_key)
                        WHERE n.neighbor_id <> w.id
                      ) = (
                        SELECT COALESCE(array_agg(n.edge_key ORDER BY n.neighbor_id, n.edge_key), ARRAY[]::text[])
                        FROM unnest(w.nbr_ids, w.nbr_key) AS n(neighbor_id, edge_key)
                        WHERE n.neighbor_id <> v.id
                      )
                  AND (
                        zx_normalize_phase(v.phase + w.phase) = 0::real
                     OR zx_normalize_phase(v.phase - w.phase) = 1::real
                  )
            ) AS raw_potential
        ),
        chosen AS (
            SELECT p.*
            FROM potential AS p
            WHERE NOT EXISTS (
                SELECT 1
                FROM potential AS earlier
                WHERE earlier.seq < p.seq
                  AND earlier.blocked_ids && p.blocked_ids
            )
        )
        INSERT INTO zx_supp_chosen (
            v_id,
            w_id,
            match_type,
            v_phase,
            w_phase,
            neighbor_id
        )
        SELECT
            ch.v_id,
            ch.w_id,
            ch.match_type,
            ch.v_phase,
            ch.w_phase,
            n.neighbor_id
        FROM chosen AS ch
        LEFT JOIN LATERAL unnest(ch.neighbors) AS n(neighbor_id) ON true;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        UPDATE zx_vertex AS z
        SET param = zx_normalize_phase(z.param + 1::real)
        FROM (
            SELECT DISTINCT neighbor_id
            FROM zx_supp_chosen
            WHERE neighbor_id IS NOT NULL
              AND (
                    (match_type = 1 AND zx_normalize_phase(v_phase + w_phase) = 1::real)
                 OR (match_type = 2 AND zx_normalize_phase(v_phase + w_phase) = 0::real)
              )
        ) AS phase_updates
        WHERE z.id = phase_updates.neighbor_id;

        DELETE FROM zx_edge AS e
        USING (
            SELECT DISTINCT v_id AS id FROM zx_supp_chosen
            UNION
            SELECT DISTINCT w_id AS id FROM zx_supp_chosen
        ) AS removed
            WHERE get_id_from_link(e.source) = removed.id;

        DELETE FROM zx_edge AS e
        USING (
            SELECT DISTINCT v_id AS id FROM zx_supp_chosen
            UNION
            SELECT DISTINCT w_id AS id FROM zx_supp_chosen
        ) AS removed
            WHERE get_id_from_link(e.target) = removed.id;

        DELETE FROM zx_vertex AS z
        USING (
            SELECT DISTINCT v_id AS id FROM zx_supp_chosen
            UNION
            SELECT DISTINCT w_id AS id FROM zx_supp_chosen
        ) AS removed
            WHERE z.id = removed.id;

        changed := true;
    END LOOP;

    IF changed THEN
        CALL zx_remove_isolated_vertices(changed);
    END IF;
END;
$$;

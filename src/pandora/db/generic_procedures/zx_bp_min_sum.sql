-- Min-sum message passing over a bipartite ZX graph.
CREATE OR REPLACE PROCEDURE zx_bp_min_sum(
    p_iters integer DEFAULT 10,
    p_variable_type smallint DEFAULT zx_const_x_spider()
)
LANGUAGE plpgsql
AS $$
DECLARE
    p_check_type smallint := CASE WHEN p_variable_type = zx_const_z_spider()
                                    THEN zx_const_x_spider()
                                ELSE zx_const_z_spider() END;
BEGIN
    IF NOT zx_is_bipartite() THEN
        RAISE EXCEPTION 'zx_bp_min_sum requires a bipartite ZX graph; run zx_remove_h_edges first';
    END IF;

    CREATE TEMP TABLE IF NOT EXISTS bp_msg (
        edge_id bigint NOT NULL,
        direction smallint NOT NULL,   -- 0 = variable -> check, 1 = check -> variable
        var_id bigint NOT NULL,
        check_id bigint NOT NULL,
        msg double precision NOT NULL,
        PRIMARY KEY (edge_id, direction)
    ) ON COMMIT DROP;
    CREATE INDEX IF NOT EXISTS bp_msg_var_dir ON bp_msg (var_id, direction);
    CREATE INDEX IF NOT EXISTS bp_msg_chk_dir ON bp_msg (check_id, direction);

    TRUNCATE bp_msg;
    TRUNCATE zx_bp_check_value;

    -- Seed one message row per direction for every variable <-> check edge.
    INSERT INTO bp_msg (edge_id, direction, var_id, check_id, msg)
    SELECT e.id, d.direction,
           CASE WHEN get_type_from_link(e.source) = p_variable_type
                    THEN get_id_from_link(e.source)
                ELSE get_id_from_link(e.target) END AS var_id,
           CASE WHEN get_type_from_link(e.source) = p_check_type
                    THEN get_id_from_link(e.source)
                ELSE get_id_from_link(e.target) END AS check_id,
           0::double precision
        FROM zx_edge e
        CROSS JOIN (VALUES (0::smallint), (1::smallint)) AS d(direction)
        WHERE e.type = zx_const_regular_edge()
            AND get_type_from_link(e.source) IN (p_variable_type, p_check_type)
            AND get_type_from_link(e.target) IN (p_variable_type, p_check_type)
            AND get_type_from_link(e.source) <> get_type_from_link(e.target);

    -- init: variable -> check messages carry the prior value. Pauli-phase
    -- variables get a smaller prior (10e-3) than non-Pauli ones (10e-2).
    UPDATE bp_msg m
        SET msg = CASE WHEN zx_phase_is_pauli(v.param) THEN 10e-3 ELSE 10e-2 END
        FROM zx_vertex v
        WHERE m.direction = 0 AND m.var_id = v.id;

    FOR i IN 1..p_iters LOOP
        -- Check-node update: new check -> variable messages from the variable -> check messages
        WITH incoming AS (
            SELECT check_id, edge_id,
                    CASE WHEN msg < 0 THEN -1 ELSE 1 END AS sgn,
                    abs(msg) AS mag
                FROM bp_msg
                WHERE direction = 0
        ),
        ranked AS (
            SELECT check_id, edge_id, mag, row_number() OVER (PARTITION BY check_id ORDER BY mag, edge_id) AS rank
                FROM incoming
        ),
        mins AS (
            SELECT check_id,
                   max(mag) FILTER (WHERE rank = 1) AS min1,
                   max(mag) FILTER (WHERE rank = 2) AS min2,
                   max(edge_id) FILTER (WHERE rank = 1) AS min1_edge
                FROM ranked
                GROUP BY check_id
        ),
        signs AS (
            SELECT
                    check_id,
                    -- No easy way to calculate product...
                    CASE WHEN sum(CASE WHEN sgn < 0 THEN 1 ELSE 0 END) % 2 = 1
                        THEN -1 ELSE 1 END AS sign_all
                FROM incoming
                GROUP BY check_id
        )
        UPDATE bp_msg m
            SET msg =
                    -- Normalized min-sum
                    -- 0.6 for Pauli-phase check nodes, non-Pauli checks are unscaled
                    (CASE WHEN zx_phase_is_pauli(cv.param) THEN 0.6 ELSE 1 END)
                    -- Product of signs with the current edge excluded
                    * (signs.sign_all * incoming.sgn)
                    -- Min magnitude with the current edge excluded
                    * (CASE WHEN m.edge_id = mins.min1_edge
                            THEN COALESCE(mins.min2, 0)
                        ELSE mins.min1 END)
            FROM incoming
            JOIN mins ON mins.check_id = incoming.check_id
            JOIN signs ON signs.check_id = incoming.check_id
            JOIN zx_vertex cv ON cv.id = incoming.check_id
            WHERE m.direction = 1 AND m.edge_id = incoming.edge_id;

        -- Variable-node update: new variable -> check messages from the check -> variable messages
        WITH incoming AS (
            SELECT var_id, edge_id, msg AS cin
                FROM bp_msg
                WHERE direction = 1
        ),
        var_total AS (
            SELECT i.var_id,
                max(CASE WHEN zx_phase_is_pauli(v.param) THEN 10e-3 ELSE 10e-2 END)
                    + sum(i.cin) AS total
                FROM incoming i
                JOIN zx_vertex v ON v.id = i.var_id
                GROUP BY i.var_id
        )
        UPDATE bp_msg m
            SET msg = vt.total - i.cin
            FROM incoming i
            JOIN var_total vt ON vt.var_id = i.var_id
            WHERE m.direction = 0 AND m.edge_id = i.edge_id;
    END LOOP;

    -- Per-check value: sum of the variable -> check messages arriving at the check.
    INSERT INTO zx_bp_check_value (vertex_id, value)
    SELECT check_id, sum(msg)
        FROM bp_msg
        WHERE direction = 0
        GROUP BY check_id;
END;
$$;

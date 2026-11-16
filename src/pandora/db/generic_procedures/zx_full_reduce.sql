
CREATE OR REPLACE PROCEDURE zx_interior_clifford_simp(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    round_changed boolean;
BEGIN
    CALL zx_spider_simp(changed);

    /* This is not needed as the zx_merge_edge does not create self loops
    CALL zx_remove_self_loops(changed);
    */

    CALL zx_x_to_z(changed);

    LOOP
        round_changed := false;

        CALL zx_id_simp(round_changed);

        CALL zx_spider_simp(round_changed);

        /* This is not needed as the zx_merge_edge does not create self loops
        CALL zx_remove_self_loops(round_changed);
        */

        CALL zx_pivot_simp(round_changed);

        CALL zx_lcomp_simp(round_changed);

        EXIT WHEN NOT round_changed;
        changed := true;
    END LOOP;
END;
$$;

CREATE OR REPLACE PROCEDURE zx_clifford_simp(inout changed boolean)
LANGUAGE plpgsql
AS $$
DECLARE
    round_changed boolean;
BEGIN
    LOOP
        round_changed := false;

        CALL zx_interior_clifford_simp(round_changed);

        CALL zx_pivot_boundary_simp(round_changed);

        EXIT WHEN NOT round_changed;
        changed := true;
    END LOOP;
END;
$$;

CREATE OR REPLACE PROCEDURE zx_full_reduce()
LANGUAGE plpgsql
AS $$
DECLARE
    t_call timestamp;
    body_changed boolean;
    bad smallint;
BEGIN
    SELECT type INTO bad
        FROM zx_vertex
        WHERE type IN (35, 36, 37, 38)
        LIMIT 1;

    IF bad IS NOT NULL THEN
        RAISE EXCEPTION
            'zx_full_reduce only supports Z/X spiders and boundary vertices; got type %', bad;
    END IF;

    CALL zx_interior_clifford_simp(body_changed);

    CALL zx_pivot_gadget_simp(body_changed);

    LOOP
        CALL zx_clifford_simp(body_changed);

        body_changed := false;

        CALL zx_gadget_simp(body_changed);

        CALL zx_interior_clifford_simp(body_changed);

        CALL zx_copy_simp(body_changed);

        CALL zx_supplementarity_simp(body_changed);

        CALL zx_pivot_gadget_simp(body_changed);

        CALL zx_remove_isolated_spiders(body_changed);

        IF NOT body_changed THEN
            COMMIT;
            RETURN;
        END IF;
    END LOOP;
    COMMIT;
END;
$$;

-- Run the PyZX basic simp equivalent
CREATE OR REPLACE PROCEDURE zx_basic_simp()
LANGUAGE plpgsql
AS $$
DECLARE
    round_changed boolean;
BEGIN
    CALL zx_spider_simp(round_changed);

    CALL zx_x_to_z(round_changed);

    LOOP
        round_changed := false;

        CALL zx_id_simp(round_changed);

        CALL zx_spider_simp(round_changed);

        /* This is not needed as the zx_merge_edge does not create self loops
        CALL zx_remove_self_loops(round_changed);
        */

        EXIT WHEN NOT round_changed;
    END LOOP;
    COMMIT;
END;
$$;

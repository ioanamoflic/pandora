-- Gets the last ZX vertex on the wire
CREATE OR REPLACE FUNCTION zx_load_get_wire_head(
    p_link bigint
)
RETURNS TABLE (
    qubit bigint,
    vertex_id bigint,
    next_free_row bigint
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_link IS NULL THEN
        RETURN QUERY
        SELECT
            NULL::bigint,
            NULL::bigint,
            NULL::bigint;
        RETURN;
    END IF;

    RETURN QUERY
        SELECT wh.qubit, wh.vertex_id, wh.next_free_row
            FROM wire_head wh
            WHERE wh.source_gate_id = get_id_from_link(p_link)
                AND wh.source_port = get_port_from_link(p_link);

    IF NOT FOUND THEN
        RAISE EXCEPTION 'linked_circuit_to_zx missing wire_head for gate';
    END IF;
END;
$$;

-- Stores the latest ZX position
CREATE OR REPLACE FUNCTION zx_load_set_wire_head(
    p_source_gate_id bigint,
    p_source_port integer,
    p_qubit bigint,
    p_vertex_id bigint,
    p_next_free_row bigint
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO wire_head(source_gate_id, source_port, qubit, vertex_id, next_free_row)
    	VALUES (p_source_gate_id, p_source_port, p_qubit, p_vertex_id, p_next_free_row);
END;
$$;

-- Inserts one ZX vertex and optionally connects it to the previous vertex on the wire.
CREATE OR REPLACE FUNCTION zx_load_append_vertex(
    p_type smallint,
    p_qubit bigint,
    p_row bigint,
    p_param double precision,
    p_prev_vertex_id bigint,
    p_edge_type smallint
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    new_vertex_id bigint;
BEGIN
    INSERT INTO zx_vertex(type, qubit, row, param)
		VALUES (p_type, p_qubit, p_row, COALESCE(p_param, 0)::double precision)
		RETURNING id INTO new_vertex_id;

    IF p_prev_vertex_id IS NOT NULL THEN
        INSERT INTO zx_edge(type, source, target)
			VALUES (
				p_edge_type::smallint,
				zx_vertex_ref(p_prev_vertex_id),
				create_link(new_vertex_id, 0, p_type)
			);
    END IF;

    RETURN new_vertex_id;
END;
$$;

-- Creates a double ZX fragment.
CREATE OR REPLACE FUNCTION zx_load_append_two_wire_gate(
    p_left_type smallint, p_right_type smallint, p_cross_edge_type smallint,
    p_left_qubit bigint, p_left_prev_vertex_id bigint, p_left_next_row bigint,
    p_right_qubit bigint, p_right_prev_vertex_id bigint, p_right_next_row bigint
)
RETURNS TABLE (
    left_vertex bigint,
    right_vertex bigint,
    next_row bigint
)
LANGUAGE plpgsql
AS $$
DECLARE
    row_nr bigint;
BEGIN
    row_nr := GREATEST(p_left_next_row, p_right_next_row);

    left_vertex := zx_load_append_vertex(
        p_left_type,
        p_left_qubit,
        row_nr,
        0,
        p_left_prev_vertex_id,
        zx_const_regular_edge()
    );

    right_vertex := zx_load_append_vertex(
        p_right_type,
        p_right_qubit,
        row_nr,
        0,
        p_right_prev_vertex_id,
        zx_const_regular_edge()
    );

    INSERT INTO zx_edge(type, source, target)
		VALUES (
			p_cross_edge_type,
			create_link(left_vertex, 0, p_left_type),
			create_link(right_vertex, 0, p_right_type)
		);

    next_row := row_nr + 1;
    RETURN NEXT;
END;
$$;

-- Ry(theta) = Rz(-pi/2) . Rx(theta) . Rz(pi/2)
CREATE OR REPLACE PROCEDURE zx_load_decompose_ry(
    p_gate_id bigint,
    p_gate_type smallint,
    p_param double precision,
    p_qubit bigint,
    p_pred_vertex_id bigint,
    p_pred_next_row bigint
)
LANGUAGE plpgsql
AS $$
DECLARE
    v1 bigint;
    v2 bigint;
    v3 bigint;
    phase double precision;
BEGIN
	-- Type 10 is Pauli Y which is Ry(pi)
    phase := CASE p_gate_type WHEN 10 THEN 1::double precision ELSE p_param END;

    v1 := zx_load_append_vertex(zx_const_z_spider(), p_qubit, p_pred_next_row,     -0.5,    p_pred_vertex_id,zx_const_regular_edge());
    v2 := zx_load_append_vertex(zx_const_x_spider(), p_qubit, p_pred_next_row + 1, phase, v1, 				zx_const_regular_edge());
    v3 := zx_load_append_vertex(zx_const_z_spider(), p_qubit, p_pred_next_row + 2, 0.5,   v2, 				zx_const_regular_edge());

    PERFORM zx_load_set_wire_head(p_gate_id, 0, p_qubit, v3, p_pred_next_row + 3);
END;
$$;

-- SWAP to CNOT decomposition
CREATE OR REPLACE PROCEDURE zx_load_decompose_swap(
    p_gate_id bigint,
    p_q1 bigint, p_pred1_vertex_id bigint, p_pred1_next_row bigint,
    p_q2 bigint, p_pred2_vertex_id bigint, p_pred2_next_row bigint
)
LANGUAGE plpgsql
AS $$
DECLARE
    v1 bigint;
    v2 bigint;
    row_nr bigint;
BEGIN
    SELECT left_vertex, right_vertex, next_row INTO v1, v2, row_nr
		FROM zx_load_append_two_wire_gate(
			zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
			p_q1, p_pred1_vertex_id, p_pred1_next_row,
			p_q2, p_pred2_vertex_id, p_pred2_next_row
		);

    SELECT left_vertex, right_vertex, next_row INTO v2, v1, row_nr
		FROM zx_load_append_two_wire_gate(
			zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
			p_q2, v2, row_nr,
			p_q1, v1, row_nr
		);

    SELECT left_vertex, right_vertex, next_row INTO v1, v2, row_nr
		FROM zx_load_append_two_wire_gate(
			zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
			p_q1, v1, row_nr,
			p_q2, v2, row_nr
		);

    PERFORM zx_load_set_wire_head(p_gate_id, 0, p_q1, v1, row_nr);
    PERFORM zx_load_set_wire_head(p_gate_id, 1, p_q2, v2, row_nr);
END;
$$;

-- Toffoli (CCX) via the standard 6-CNOT + 7-T-rotation decomposition
-- (Nielsen & Chuang Fig. 4.9), unrolled into 15 ZX-graph steps.
CREATE OR REPLACE PROCEDURE zx_load_decompose_toffoli(
    p_gate_id bigint,
    p_c1_q bigint, p_c1_vertex_id bigint, p_c1_next_row bigint,
    p_c2_q bigint, p_c2_vertex_id bigint, p_c2_next_row bigint,
    p_t_q  bigint, p_t_vertex_id  bigint, p_t_next_row  bigint
)
LANGUAGE plpgsql
AS $$
DECLARE
    c1_v bigint := p_c1_vertex_id;
    c2_v bigint := p_c2_vertex_id;
    t_v  bigint := p_t_vertex_id;
    c1_next bigint := p_c1_next_row;
    c2_next bigint := p_c2_next_row;
    t_next  bigint := p_t_next_row;
    row_nr bigint;
BEGIN
    -- 1) H on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, 0, t_v, zx_const_hadamard_edge());
    t_next := t_next + 1;

    -- 2) CNOT: control2 -> target
    SELECT left_vertex, right_vertex, next_row INTO c2_v, t_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c2_q, c2_v, c2_next, p_t_q, t_v, t_next
    );
    c2_next := row_nr; t_next := row_nr;

    -- 3) Z(-1/4) on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, -0.25, t_v, zx_const_regular_edge());
    t_next := t_next + 1;

    -- 4) CNOT: control1 -> target
    SELECT left_vertex, right_vertex, next_row INTO c1_v, t_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c1_q, c1_v, c1_next, p_t_q, t_v, t_next
    );
    c1_next := row_nr; t_next := row_nr;

    -- 5) Z(+1/4) on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, 0.25, t_v, zx_const_regular_edge());
    t_next := t_next + 1;

    -- 6) CNOT: control2 -> target
    SELECT left_vertex, right_vertex, next_row INTO c2_v, t_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c2_q, c2_v, c2_next, p_t_q, t_v, t_next
    );
    c2_next := row_nr; t_next := row_nr;

    -- 7) Z(-1/4) on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, -0.25, t_v, zx_const_regular_edge());
    t_next := t_next + 1;

    -- 8) CNOT: control1 -> target
    SELECT left_vertex, right_vertex, next_row INTO c1_v, t_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c1_q, c1_v, c1_next, p_t_q, t_v, t_next
    );
    c1_next := row_nr; t_next := row_nr;

    -- 9) Z(-1/4) on control2
    c2_v := zx_load_append_vertex(zx_const_z_spider(), p_c2_q, c2_next, -0.25, c2_v, zx_const_regular_edge());
    c2_next := c2_next + 1;

    -- 10) Z(+1/4) on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, 0.25, t_v, zx_const_regular_edge());
    t_next := t_next + 1;

    -- 11) CNOT: control1 -> control2
    SELECT left_vertex, right_vertex, next_row INTO c1_v, c2_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c1_q, c1_v, c1_next, p_c2_q, c2_v, c2_next
    );
    c1_next := row_nr; c2_next := row_nr;


    -- 12) Z(-1/4) on control2
    c2_v := zx_load_append_vertex(zx_const_z_spider(), p_c2_q, c2_next, -0.25, c2_v, zx_const_regular_edge());
    c2_next := c2_next + 1;

    -- 13) CNOT: control1 -> control2
    SELECT left_vertex, right_vertex, next_row INTO c1_v, c2_v, row_nr
    FROM zx_load_append_two_wire_gate(
        zx_const_z_spider(), zx_const_x_spider(), zx_const_regular_edge(),
        p_c1_q, c1_v, c1_next, p_c2_q, c2_v, c2_next
    );
    c1_next := row_nr; c2_next := row_nr;

    -- 14) Z(1/4) on control1
    c1_v := zx_load_append_vertex(zx_const_z_spider(), p_c1_q, c1_next, 0.25, c1_v, zx_const_regular_edge());
    c1_next := c1_next + 1;

    -- 15) Z(1/2) on control2
    c2_v := zx_load_append_vertex(zx_const_z_spider(), p_c2_q, c2_next, 0.5, c2_v, zx_const_regular_edge());
    c2_next := c2_next + 1;

    -- 16) final H on target
    t_v := zx_load_append_vertex(zx_const_z_spider(), p_t_q, t_next, 0, t_v, zx_const_hadamard_edge());
    t_next := t_next + 1;

    PERFORM zx_load_set_wire_head(p_gate_id, 0, p_c1_q, c1_v, c1_next);
    PERFORM zx_load_set_wire_head(p_gate_id, 1, p_c2_q, c2_v, c2_next);
    PERFORM zx_load_set_wire_head(p_gate_id, 2, p_t_q,  t_v,  t_next);
END;
$$;

CREATE OR REPLACE PROCEDURE linked_circuit_to_zx()
LANGUAGE plpgsql
AS $$
DECLARE
    in_gate RECORD;
    gate RECORD;
    pred1 RECORD;
    pred2 RECORD;
    pred3 RECORD;
    pred_type smallint;
    qubit_nr bigint := -1;
    row_nr bigint;
    vertex_1 bigint;
    vertex_2 bigint;
    tmp_phase real;
    depth_updates integer;
    t timestamp;
BEGIN
    -- If the linked_circuit is not altered, the gates are already in depth-order which allows for a fast single pass conversion below. This should be extended to support out-of-order linked_circuit in the future
    IF EXISTS (
        SELECT 1
            FROM linked_circuit c
            CROSS JOIN LATERAL (VALUES (c.prev_q1), (c.prev_q2), (c.prev_q3)) AS p(link)
        WHERE p.link IS NOT NULL
        AND get_id_from_link(p.link) >= c.id
    ) THEN
        RAISE EXCEPTION 'linked_circuit is not in depth-order';
    END IF;

    TRUNCATE TABLE zx_edge RESTART IDENTITY CASCADE;
    TRUNCATE TABLE zx_vertex RESTART IDENTITY CASCADE;

    CREATE TEMP TABLE wire_head (
        source_gate_id bigint NOT NULL,
        source_port integer NOT NULL,
        qubit bigint NOT NULL,
        vertex_id bigint NOT NULL,
        next_free_row bigint NOT NULL,
        PRIMARY KEY (source_gate_id, source_port)
    ) ON COMMIT DROP;

    -- Input gates
    FOR in_gate IN
        SELECT id
        FROM linked_circuit
        WHERE type = 0
        ORDER BY id
    LOOP
        qubit_nr := qubit_nr + 1;
        vertex_1 := zx_load_append_vertex(zx_const_input_type(), qubit_nr, 0, 0, NULL, zx_const_regular_edge());
        PERFORM zx_load_set_wire_head(in_gate.id, 0, qubit_nr, vertex_1, 1);
    END LOOP;

    -- Iterate the non-input linked_circuit gates in depth-order and convert each gate to ZX vertices
    FOR gate IN
        SELECT lc.*
        FROM linked_circuit lc
        WHERE lc.type <> 0
        ORDER BY lc.id
    LOOP
        SELECT * INTO pred1 FROM zx_load_get_wire_head(gate.prev_q1);

        -- Output gate
        IF gate.type = 1 THEN
            -- If the previous one was a measurement, it already terminated this wire
            SELECT type INTO pred_type
                FROM linked_circuit
                WHERE id = get_id_from_link(gate.prev_q1);

            IF pred_type = 14 THEN
                CONTINUE;
            END IF;

            PERFORM zx_load_append_vertex(
                zx_const_output_type(),
                pred1.qubit,
                pred1.next_free_row,
                0,
                pred1.vertex_id,
                zx_const_regular_edge()
            );
            CONTINUE;

        ELSIF gate.type = 8 THEN
            -- Hadamard is represented as a Z spider connected by a Hadamard edge.
			vertex_1 := zx_load_append_vertex(
                zx_const_z_spider(),
                pred1.qubit,
                pred1.next_free_row,
                0,
                pred1.vertex_id,
                zx_const_hadamard_edge()
			);

			PERFORM zx_load_set_wire_head(
				gate.id,
				0,
				pred1.qubit,
				vertex_1,
				pred1.next_free_row + 1
			);
            CONTINUE;

        ELSIF gate.type IN (4, 7, 11, 27, 28, 29, 30) THEN
            -- Z-family single-qubit gates become one phased Z spider.
            tmp_phase := CASE gate.type
                WHEN 11 THEN 1
                WHEN 27 THEN 0.5
                WHEN 28 THEN -0.5
                WHEN 29 THEN 0.25
                WHEN 30 THEN -0.25
                ELSE gate.param
            END;

			vertex_1 := zx_load_append_vertex(
                zx_const_z_spider(),
                pred1.qubit,
                pred1.next_free_row,
                tmp_phase,
                pred1.vertex_id,
                zx_const_regular_edge()
			);

			PERFORM zx_load_set_wire_head(
				gate.id,
				0,
				pred1.qubit,
				vertex_1,
				pred1.next_free_row + 1
			);
            CONTINUE;

        ELSIF gate.type IN (2, 5, 9) THEN
            -- X-family single-qubit gates become one phased X spider.
            tmp_phase := CASE gate.type
                WHEN 9 THEN 1
                ELSE gate.param
            END;

            vertex_1 := zx_load_append_vertex(
                zx_const_x_spider(),
                pred1.qubit,
                pred1.next_free_row,
                tmp_phase,
                pred1.vertex_id,
                zx_const_regular_edge()
            );

            PERFORM zx_load_set_wire_head(
                gate.id,
                0,
                pred1.qubit,
                vertex_1,
                pred1.next_free_row + 1
            );
            CONTINUE;

        ELSIF gate.type IN (3, 6, 10) THEN
            -- Ry-style rotations are decomposed to Z-X-Z chain.
            CALL zx_load_decompose_ry(
                gate.id, gate.type, gate.param,
                pred1.qubit, pred1.vertex_id, pred1.next_free_row
            );
            CONTINUE;
        END IF;

        -- Two qubit gates --
        SELECT * INTO pred2 FROM zx_load_get_wire_head(gate.prev_q2);

        IF gate.type IN (15, 18) THEN
            -- CNOT/CXPow act on two wires at one shared ZX row.  A zero cxpow exponent is an
            -- identity, while exponent 1 uses the standard Z-control/X-target fragment.
            IF gate.type = 18 AND COALESCE(gate.param, 1) = 0 THEN
                PERFORM zx_load_set_wire_head(gate.id, 0, pred1.qubit, pred1.vertex_id, pred1.next_free_row);
                PERFORM zx_load_set_wire_head(gate.id, 1, pred2.qubit, pred2.vertex_id, pred2.next_free_row);
                CONTINUE;
            END IF;
            IF gate.type = 18 AND COALESCE(gate.param, 1) <> 1 THEN
                RAISE EXCEPTION 'linked_circuit_to_zx does not support cxpow exponent %', gate.param;
            END IF;

            SELECT left_vertex, right_vertex, next_row
            INTO vertex_1, vertex_2, row_nr
            FROM zx_load_append_two_wire_gate(
                zx_const_z_spider(),
                zx_const_x_spider(),
                zx_const_regular_edge(),
                pred1.qubit,
                pred1.vertex_id,
                pred1.next_free_row,
                pred2.qubit,
                pred2.vertex_id,
                pred2.next_free_row
            );

            PERFORM zx_load_set_wire_head(gate.id, 0, pred1.qubit, vertex_1, row_nr);
            PERFORM zx_load_set_wire_head(gate.id, 1, pred2.qubit, vertex_2, row_nr);
            CONTINUE;

        ELSIF gate.type IN (16, 17) THEN
            -- CZ/CZPow use two Z spiders joined by a Hadamard edge.
            IF gate.type = 17 AND COALESCE(gate.param, 1) <> 1 THEN
                RAISE EXCEPTION 'linked_circuit_to_zx does not support czpow exponent %', gate.param;
            END IF;

            SELECT left_vertex, right_vertex, next_row
            INTO vertex_1, vertex_2, row_nr
            FROM zx_load_append_two_wire_gate(
                zx_const_z_spider(),
                zx_const_z_spider(),
                zx_const_hadamard_edge(),
                pred1.qubit,
                pred1.vertex_id,
                pred1.next_free_row,
                pred2.qubit,
                pred2.vertex_id,
                pred2.next_free_row
            );

            PERFORM zx_load_set_wire_head(gate.id, 0, pred1.qubit, vertex_1, row_nr);
            PERFORM zx_load_set_wire_head(gate.id, 1, pred2.qubit, vertex_2, row_nr);
            CONTINUE;

        ELSIF gate.type = 31 THEN
            -- SWAP expands into three alternating CNOT fragments.
            CALL zx_load_decompose_swap(
                gate.id,
                pred1.qubit, pred1.vertex_id, pred1.next_free_row,
                pred2.qubit, pred2.vertex_id, pred2.next_free_row
            );
            CONTINUE;
        END IF;

        -- Three qubit gates --
        SELECT * INTO pred3 FROM zx_load_get_wire_head(gate.prev_q3);

        IF gate.type = 23 THEN
            -- Toffoli expands through the helper into the fixed multi-step ZX decomposition.
            CALL zx_load_decompose_toffoli(
                gate.id,
                pred1.qubit, pred1.vertex_id, pred1.next_free_row,
                pred2.qubit, pred2.vertex_id, pred2.next_free_row,
                pred3.qubit, pred3.vertex_id, pred3.next_free_row
            );
            CONTINUE;
        END IF;

        RAISE EXCEPTION 'linked_circuit_to_zx does not support linked_circuit gate type %', gate.type;
    END LOOP;

    ANALYZE zx_vertex;
    ANALYZE zx_edge;

END;
$$;

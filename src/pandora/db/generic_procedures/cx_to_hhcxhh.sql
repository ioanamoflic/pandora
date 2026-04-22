create or replace procedure linked_cx_to_hhcxhh(pass_count int, timeout int)
    language plpgsql
as
$$
declare
    cx record;
    gate record;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_h_q1_id bigint;
	left_h_q2_id bigint;
	right_h_q1_id bigint;
	right_h_q2_id bigint;

    -- used for computing the links
    port_nr int;

    -- the links to the right and left
    left_q1_link bigint;
    left_q2_link bigint;
    right_q1_link bigint;
    right_q2_link bigint;

    cx_id_ctrl bigint;
    cx_id_tgt bigint;

    start_time timestamp;

    a record;
    b record;
    c record;
    d record;

    h_type smallint;
    cx_types smallint[];

begin
    port_nr := 0; -- single qubit gate has a single port with index 0

    select id into h_type from gate_types where name = 'h';
    select array_agg(id) into cx_types from gate_types where name in ('cx', 'cxpow');

    start_time := clock_timestamp();

    while pass_count > 0 loop
        for gate in
            select id from linked_circuit
                 where
                 type = any(cx_types)
        loop
            select * into cx from linked_circuit where id = gate.id for update skip locked;

            if cx.id is null
                or cx.type != all(cx_types)
            then
                commit;
                continue;
            end if;

            cx_prev_q1_id := get_id_from_link(cx.prev_q1);
            cx_prev_q2_id := get_id_from_link(cx.prev_q2);
            cx_next_q1_id := get_id_from_link(cx.next_q1);
            cx_next_q2_id := get_id_from_link(cx.next_q2);

            select * into a from linked_circuit where id = cx_prev_q1_id for update skip locked;
            select * into b from linked_circuit where id = cx_prev_q2_id for update skip locked;
            select * into c from linked_circuit where id = cx_next_q1_id for update skip locked;
            select * into d from linked_circuit where id = cx_next_q2_id for update skip locked;

            -- Lock the 4 neighbours
            if a.id is null or b.id is null or c.id is null or d.id is null then
                commit;
                continue;
            end if;

            cx_id_ctrl := create_link(cx.id, 0, cx.type);
            cx_id_tgt  := create_link(cx.id, 1, cx.type);

            insert into linked_circuit(prev_q1, type, param, next_q1, label) values (cx.prev_q1, h_type, 1, cx_id_tgt, cx.label)
                                                          returning id into left_h_q1_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, label) values (cx.prev_q2, h_type, 1, cx_id_ctrl, cx.label)
                                                          returning id into left_h_q2_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, label) values (cx_id_tgt, h_type, 1, cx.next_q1, cx.label)
                                                          returning id into right_h_q1_id;

            insert into linked_circuit(prev_q1, type, param, next_q1, label) values (cx_id_ctrl, h_type, 1, cx.next_q2, cx.label)
                                                          returning id into right_h_q2_id;

            -- These are the links that the margins and CNOT should use
            left_q1_link := create_link(left_h_q1_id, port_nr, h_type);
            left_q2_link := create_link(left_h_q2_id, port_nr, h_type);
            right_q1_link := create_link(right_h_q1_id, port_nr, h_type);
            right_q2_link := create_link(right_h_q2_id, port_nr, h_type);

            -- Update the CNOT: flip the switch value and set visited
            update linked_circuit set (prev_q1, prev_q2, next_q1, next_q2, switch) = (left_q2_link, left_q1_link, right_q2_link, right_q1_link, not cx.switch) where id = cx.id;

            if get_port_from_link(cx.prev_q1) = 0 then
                update linked_circuit set next_q1 = left_q1_link where id = cx_prev_q1_id;
            else
                update linked_circuit set next_q2 = left_q1_link where id = cx_prev_q1_id;
            end if;

            if get_port_from_link(cx.prev_q2) = 0 then
                update linked_circuit set next_q1 = left_q2_link where id = cx_prev_q2_id;
            else
                update linked_circuit set next_q2 = left_q2_link where id = cx_prev_q2_id;
            end if;

            if get_port_from_link(cx.next_q1) = 0 then
                update linked_circuit set prev_q1 = right_q1_link where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = right_q1_link where id = cx_next_q1_id;
            end if;

            if get_port_from_link(cx.next_q2) = 0 then
                update linked_circuit set prev_q1 = right_q2_link where id = cx_next_q2_id;
            else
                update linked_circuit set prev_q2 = right_q2_link where id = cx_next_q2_id;
            end if;

            commit; -- release locks

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop
end;$$;


create or replace procedure linked_hhcxhh_to_cx_seq(run_nr int)
    language plpgsql
as
$$
declare
    cx record;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;

    left_q1 record;
    left_q2 record;
    right_q1 record;
    right_q2 record;

    cx_id_ctrl bigint;
    cx_id_tgt bigint;

    left_q1_id bigint;
	left_q2_id bigint;
	right_q1_id bigint;
	right_q2_id bigint;

    h_type smallint;
    cx_types smallint[];

begin
    select id into h_type from gate_types where name = 'h';
    select array_agg(id) into cx_types from gate_types where name in ('cx', 'cxpow');

    while run_nr > 0 loop
        for cx in
            select * from linked_circuit where type = any(cx_types)
            and get_type_from_link(prev_q1) = h_type and get_type_from_link(prev_q2) = h_type
            and get_type_from_link(next_q1) = h_type and get_type_from_link(next_q2) = h_type
        loop
            if cx.id is not null
            then
                -- left gates on qubits 1,2
                cx_prev_q1_id := get_id_from_link(cx.prev_q1);
                cx_prev_q2_id := get_id_from_link(cx.prev_q2);
                cx_next_q1_id := get_id_from_link(cx.next_q1);
                cx_next_q2_id := get_id_from_link(cx.next_q2);

                select * into left_q1 from linked_circuit where id=cx_prev_q1_id;
                select * into left_q2 from linked_circuit where id=cx_prev_q2_id;
                select * into right_q1 from linked_circuit where id=cx_next_q1_id;
                select * into right_q2 from linked_circuit where id=cx_next_q2_id;

                if left_q1.type = h_type
                   and left_q2.type = h_type
                   and right_q1.type = h_type
                   and right_q2.type = h_type
                then

                    left_q1_id := get_id_from_link(left_q1.prev_q1);
                    left_q2_id := get_id_from_link(left_q2.prev_q1);
                    right_q1_id := get_id_from_link(right_q1.next_q1);
                    right_q2_id := get_id_from_link(right_q2.next_q1);

                    -- compute new link_ids for neighbouring gates
                    cx_id_ctrl := create_link(cx.id, 0, cx.type);
                    cx_id_tgt  := create_link(cx.id, 1, cx.type);

                    if get_port_from_link(left_q1.prev_q1) = 0 then
                        update linked_circuit set next_q1 = cx_id_tgt where id = left_q1_id;
                    else
                        update linked_circuit set next_q2 = cx_id_tgt where id = left_q1_id;
                    end if;

                    if get_port_from_link(left_q2.prev_q1) = 0 then
                        update linked_circuit set next_q1 = cx_id_ctrl where id = left_q2_id;
                    else
                        update linked_circuit set next_q2 = cx_id_ctrl where id = left_q2_id;
                    end if;

                    if get_port_from_link(right_q1.next_q1) = 0 then
                        update linked_circuit set prev_q1 = cx_id_tgt where id = right_q1_id;
                    else
                        update linked_circuit set prev_q2 = cx_id_tgt where id = right_q1_id;
                    end if;

                    if get_port_from_link(right_q2.next_q1) = 0 then
                        update linked_circuit set prev_q1 = cx_id_ctrl where id = right_q2_id;
                    else
                        update linked_circuit set prev_q2 = cx_id_ctrl where id = right_q2_id;
                    end if;

                    -- make sure to update the links for the cx
                    update linked_circuit set (switch, prev_q1, prev_q2, next_q1, next_q2)
                                = (not cx.switch, left_q2.prev_q1, left_q1.prev_q1, right_q2.next_q1, right_q1.next_q1) where id = cx.id;

                    delete from linked_circuit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id);

                end if;
            end if;
        end loop;

        run_nr = run_nr - 1;

    end loop;

    commit;

end;$$;



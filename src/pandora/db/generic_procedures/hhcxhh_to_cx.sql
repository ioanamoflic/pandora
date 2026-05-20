create or replace procedure linked_hhcxhh_to_cx(pass_count int, timeout int)
-- create or replace procedure linked_hhcxhh_to_cx(my_partition int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    cx record;
    gate record;
    left_q1 record;
    left_q2 record;
    right_q1 record;
    right_q2 record;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;

    cx_id_ctrl bigint;
    cx_id_tgt bigint;
    left_q1_id bigint;
	left_q2_id bigint;
	right_q1_id bigint;
	right_q2_id bigint;

    a record;
    b record;
    c record;
    d record;

	start_time timestamp;

    h_type smallint;
    cx_types smallint[];

begin
    start_time := clock_timestamp();

    select id into h_type from gate_types where name = 'h';
    select array_agg(id) into cx_types from gate_types where name in ('cx', 'cxpow');

    while pass_count > 0 loop
        for gate in
            select * from linked_circuit
                     where
                       type = any(cx_types)
                       and get_type_from_link(prev_q1) = h_type and get_type_from_link(prev_q2) = h_type
                       and get_type_from_link(next_q1) = h_type and get_type_from_link(next_q2) = h_type
                       -- and partition_id = my_partition
        loop
            select * into cx from linked_circuit where id = gate.id for update skip locked;

            if cx.id is null
                or cx.type != all(cx_types)
            then
                commit;
                continue;
            end if;

            -- Compute the Hadamard IDs
            cx_prev_q1_id := get_id_from_link(cx.prev_q1);
            cx_prev_q2_id := get_id_from_link(cx.prev_q2);
            cx_next_q1_id := get_id_from_link(cx.next_q1);
            cx_next_q2_id := get_id_from_link(cx.next_q2);

            -- Select the Hadamards
            select * into left_q1 from linked_circuit where id=cx_prev_q1_id for update skip locked;
            select * into left_q2 from linked_circuit where id=cx_prev_q2_id for update skip locked;
            select * into right_q1 from linked_circuit where id=cx_next_q1_id for update skip locked;
            select * into right_q2 from linked_circuit where id=cx_next_q2_id for update skip locked;

            if left_q1.id is null
                or left_q2.id is null
                or right_q1.id is null
                or right_q2.id is null
            then
                commit;
                continue;
            end if;

            if left_q1.type != h_type
               or left_q2.type != h_type
               or right_q1.type != h_type
               or right_q2.type != h_type
            then
                commit;
                continue;
            end if;

            -- Compute the IDs of the Hadamard neighbours
            left_q1_id := get_id_from_link(left_q1.prev_q1);
            left_q2_id := get_id_from_link(left_q2.prev_q1);
            right_q1_id := get_id_from_link(right_q1.next_q1);
            right_q2_id := get_id_from_link(right_q2.next_q1);

            select * into a from linked_circuit where id=left_q1_id for update skip locked;
            select * into b from linked_circuit where id=left_q2_id for update skip locked;
            select * into c from linked_circuit where id=right_q1_id for update skip locked;
            select * into d from linked_circuit where id=right_q2_id for update skip locked;

            if a.id is null
                or b.id is null
                or c.id is null
                or d.id is null
            then
                commit;
                continue;
            end if;

            -- compute new link_ids for neighbouring gates
            cx_id_ctrl := create_link(cx.id, 0, cx.type);
            cx_id_tgt  := create_link(cx.id, 1, cx.type);

            --- Works only for ports 1 and 2. not working for port 3

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

            commit; -- release the cx

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; --end pass loop

end;$$;



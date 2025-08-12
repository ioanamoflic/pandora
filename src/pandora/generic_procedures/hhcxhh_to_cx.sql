create or replace procedure linked_hhcxhh_to_cx(my_proc_id int, nprocs int, pass_count int, timeout int)
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

    h_type int;

    a record;
    b record;
    c record;
    d record;

	start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();
    h_type := 8;

    while pass_count > 0 loop
        for gate in
            select * from linked_circuit
                     where
                         id % nprocs = my_proc_id and
                         type = 18
                       and prev_q1 % 100 = 8 and prev_q2 % 100 = 8
                       and next_q1 % 100 = 8 and next_q2 % 100 = 8
        loop

            select * into cx from linked_circuit where id = gate.id for update skip locked;

            if cx.id is null then
                commit;
                continue;
            end if;

            -- Compute the Hadamard IDs
            cx_prev_q1_id := div(cx.prev_q1, 1000);
            cx_prev_q2_id := div(cx.prev_q2, 1000);
            cx_next_q1_id := div(cx.next_q1, 1000);
            cx_next_q2_id := div(cx.next_q2, 1000);

            -- Select the Hadamards
            select * into left_q1 from linked_circuit where id=cx_prev_q1_id for update skip locked;
            select * into left_q2 from linked_circuit where id=cx_prev_q2_id for update skip locked;
            select * into right_q1 from linked_circuit where id=cx_next_q1_id for update skip locked;
            select * into right_q2 from linked_circuit where id=cx_next_q2_id for update skip locked;

            if left_q1.id is null or left_q2.id is null or right_q1.id is null or right_q2.id is null then
                commit;
                continue;
            end if;

            if left_q1.type != h_type or left_q2.type != h_type or right_q1.type != h_type or right_q2.type != h_type then
                commit;
                continue;
            end if;

            -- Compute the IDs of the Hadamard neighbours
            left_q1_id := div(left_q1.prev_q1, 1000);
            left_q2_id := div(left_q2.prev_q1, 1000);
            right_q1_id := div(right_q1.next_q1, 1000);
            right_q2_id := div(right_q2.next_q1, 1000);

            select * into a from linked_circuit where id=left_q1_id for update skip locked;
            select * into b from linked_circuit where id=left_q2_id for update skip locked;
            select * into c from linked_circuit where id=right_q1_id for update skip locked;
            select * into d from linked_circuit where id=right_q2_id for update skip locked;

            if a.id is null or b.id is null or c.id is null or d.id is null then
                commit;
                continue;
            end if;

            -- compute new link_ids for neighbouring gates
            cx_id_ctrl := (cx.id * 10 + 0) * 100 + cx.type;
            cx_id_tgt  := (cx.id * 10 + 1) * 100 + cx.type;

            --- Works only for ports 1 and 2. not working for port 3

            if mod(div(left_q1.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = cx_id_tgt where id = left_q1_id;
            else
                update linked_circuit set next_q2 = cx_id_tgt where id = left_q1_id;
            end if;

            if mod(div(left_q2.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = cx_id_ctrl where id = left_q2_id;
            else
                update linked_circuit set next_q2 = cx_id_ctrl where id = left_q2_id;
            end if;

            if mod(div(right_q1.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = cx_id_tgt where id = right_q1_id;
            else
                update linked_circuit set prev_q2 = cx_id_tgt where id = right_q1_id;
            end if;

            if mod(div(right_q2.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = cx_id_ctrl where id = right_q2_id;
            else
                update linked_circuit set prev_q2 = cx_id_ctrl where id = right_q2_id;
            end if;

            -- make sure to update the links for the cx
            update linked_circuit set (switch, prev_q1, prev_q2, next_q1, next_q2, visited)
                        = (not cx.switch, left_q2.prev_q1, left_q1.prev_q1, right_q2.next_q1, right_q1.next_q1, my_proc_id) where id = cx.id;

            delete from linked_circuit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id);

            commit; -- release the cx

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; --end pass loop

end;$$;



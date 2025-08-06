create or replace procedure linked_cx_to_hhcxhh(my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    cx record;

    distinct_count int;
    distinct_existing int;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_h_q1_id bigint;
	left_h_q2_id bigint;
	right_h_q1_id bigint;
	right_h_q2_id bigint;

    left_q1_id bigint;
    left_q2_id bigint;
    right_q1_id bigint;
    right_q2_id bigint;
    cx_id_ctrl bigint;
    cx_id_tgt bigint;

    start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

    while pass_count > 0 loop
        for cx in
            select * from linked_circuit
                     where id % nprocs = my_proc_id
                     and type in (15, 18)
        loop
            if cx.id is null then
                continue;
            end if;

            cx_prev_q1_id := div(cx.prev_q1, 1000);
            cx_prev_q2_id := div(cx.prev_q2, 1000);
            cx_next_q1_id := div(cx.next_q1, 1000);
            cx_next_q2_id := div(cx.next_q2, 1000);

            select count(*) into distinct_count from
                (select distinct unnest(array[cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id])) as it;
            select count(*) into distinct_existing from
                (select * from linked_circuit where id in
                    (cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id) for update skip locked) as it;

            -- Lock the 4 neighbours
            if distinct_count != distinct_existing then
                commit;
                continue;
            end if;

            -- Lock the CX
            select count(*) into distinct_count from (select * from linked_circuit where id = cx.id for update skip locked) as it;
            if distinct_count != 1 then
                commit;
                continue;
            end if;

            cx_id_ctrl := (cx.id * 10 + 0) * 100 + cx.type;
            cx_id_tgt  := (cx.id * 10 + 1) * 100 + cx.type;

            insert into linked_circuit values (default, cx.prev_q1, null, null, 8, 1, 0, false, cx_id_tgt, null, null, my_proc_id, cx.label, false, null)
                                                          returning id into left_h_q1_id;
            insert into linked_circuit values (default, cx.prev_q2, null, null, 8, 1, 0, false, cx_id_ctrl, null, null, my_proc_id, cx.label, false, null)
                                                          returning id into left_h_q2_id;
            left_q1_id := (left_h_q1_id * 10 + 0) * 100 + 8;
            left_q2_id := (left_h_q2_id * 10 + 0) * 100 + 8;
            insert into linked_circuit values (default, cx_id_tgt, null, null, 8, 1, 0, false, cx.next_q1, null, null, my_proc_id, cx.label, false, null)
                                                          returning id into right_h_q1_id;
            insert into linked_circuit values (default, cx_id_ctrl, null, null, 8, 1, 0, false, cx.next_q2, null, null, my_proc_id, cx.label, false, null)
                                                          returning id into right_h_q2_id;
            right_q1_id := (right_h_q1_id * 10 + 0) * 100 + 8;
            right_q2_id := (right_h_q2_id * 10 + 0) * 100 + 8;

            -- flip the switch value and set visited
            update linked_circuit set (prev_q1, prev_q2, next_q1, next_q2, switch, visited) = (left_q2_id, left_q1_id, right_q2_id, right_q1_id, not cx.switch, my_proc_id) where id = cx.id;

            if mod(div(cx.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = left_q1_id where id = cx_prev_q1_id;
            else
                update linked_circuit set next_q2 = left_q1_id where id = cx_prev_q1_id;
            end if;

            if mod(div(cx.prev_q2, 100), 10) = 0 then
                update linked_circuit set next_q1 = left_q2_id where id = cx_prev_q2_id;
            else
                update linked_circuit set next_q2 = left_q2_id where id = cx_prev_q2_id;
            end if;

            if mod(div(cx.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = right_q1_id where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = right_q1_id where id = cx_next_q1_id;
            end if;

            if mod(div(cx.next_q2, 100), 10) = 0 then
                update linked_circuit set prev_q1 = right_q2_id where id = cx_next_q2_id;
            else
                update linked_circuit set prev_q2 = right_q2_id where id = cx_next_q2_id;
            end if;

            commit; -- release locks

        end loop; -- end gate loop

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop
end;$$;


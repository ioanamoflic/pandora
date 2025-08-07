create or replace procedure commute_single_control_left(single_type int, parameter float, my_proc_id int, nprocs int, pass_count int, timeout int)
   language plpgsql
as
$$
declare
    first record;
    second record;
    gate record;

    cx_next_q1 bigint;
    cx_prev_q1 bigint;
    sg_prev_id bigint;
    cx_next_q1_id bigint;

    new_next_for_sq bigint;
    new_prev_for_sq bigint;

    a record;
    b record;

    start_time timestamp with time zone;
begin

    start_time := clock_timestamp();

	while pass_count > 0 loop

        for gate in
            select * from linked_circuit
                     where
                     id % nprocs = my_proc_id
                     and type in (15, 16, 17, 18)
                     and mod(prev_q1, 100) = single_type
        loop
            select * into second from linked_circuit where id = gate.id for update skip locked;
            select * into first from linked_circuit where id = div(second.prev_q1, 1000) for update skip locked;

            if first.id is null or second.id is null then
                commit;
                continue;
            end if;

            if first.param != parameter or first.type != single_type
                or div(first.next_q1, 1000) != second.id then
                commit;
                continue;
            end if;

            sg_prev_id := div(first.prev_q1, 1000);
            cx_next_q1_id := div(second.next_q1, 1000);

            select * into a from linked_circuit where id = sg_prev_id for update skip locked;
            select * into b from linked_circuit where id = cx_next_q1_id for update skip locked;

            if a.id is null or b.id is null then
                commit;
                continue;
            end if;

            cx_next_q1 = second.next_q1;
            cx_prev_q1 = second.prev_q1;

            new_next_for_sq := (second.id * 10) * 100 + second.type;
            new_prev_for_sq := (first.id * 10) * 100 + first.type;

            if mod(div(first.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = new_next_for_sq where id = sg_prev_id;
            else
                update linked_circuit set next_q2 = new_next_for_sq where id = sg_prev_id;
            end if;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = new_prev_for_sq where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = new_prev_for_sq where id = cx_next_q1_id;
            end if;

            update linked_circuit set (next_q1, prev_q1, visited) = (new_prev_for_sq, first.prev_q1, my_proc_id) where id = second.id;
            update linked_circuit set (next_q1, prev_q1) = (cx_next_q1, new_next_for_sq) where id = first.id;

            commit; -- release locks

            if extract(epoch from (clock_timestamp() - start_time)) > timeout then
                exit;
            end if;

        end loop; -- end gate loop

-- 	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
--             exit;
--         end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop

end;$$;

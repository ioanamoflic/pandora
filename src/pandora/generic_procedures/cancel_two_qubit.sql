create or replace procedure cancel_two_qubit(type_1 int, type_2 int, param_1 float, param_2 float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    first record;
    second record;
    gate record;

    first_id_plus_one bigint;
    first_id_plus_zero bigint;
	first_prev_q1_id bigint;
	first_prev_q2_id bigint;
    second_next_q1_id bigint;
	second_next_q2_id bigint;

    a record;
    b record;
    c record;
    d record;

    start_time timestamp with time zone;

begin
    start_time := clock_timestamp();

	while pass_count > 0 loop

        for gate in
            select * from linked_circuit
                     where
                     id % nprocs = my_proc_id
                     and type=type_1
                     and param = param_1
                     and div(next_q1, 1000) = div(next_q2, 1000)
                     and mod(next_q1, 100) = type_2
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;
            select * into second from linked_circuit where id = div(first.next_q1, 1000) for update skip locked;

            if first.id is null or second.id is null then
                commit;
                continue;
            end if;

            if second.param != param_2 or second.type != type_2 then
--                 or second.switch != first.switch
                commit;
                continue;
            end if;

            first_id_plus_one := (first.id * 10 + 1) * 100 + first.type;
            first_id_plus_zero := (first.id * 10) * 100 + first.type;

            if second.prev_q1 != first_id_plus_zero or second.prev_q2 != first_id_plus_one then
                commit;
                continue;
            end if;

            first_prev_q1_id := div(first.prev_q1, 1000);
            first_prev_q2_id := div(first.prev_q2, 1000);
            second_next_q1_id := div(second.next_q1, 1000);
            second_next_q2_id := div(second.next_q2, 1000);

            select * into a from linked_circuit where id = first_prev_q1_id for update skip locked;
            select * into b from linked_circuit where id = first_prev_q2_id for update skip locked;
            select * into c from linked_circuit where id = second_next_q1_id for update skip locked;
            select * into d from linked_circuit where id = second_next_q2_id for update skip locked;

            -- Lock the 4 neighbours
            if a.id is null or b.id is null or c.id is null or d.id is null then
                commit;
                continue;
            end if;

            if mod(div(first.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = second.next_q1 where id = first_prev_q1_id;
            else
                update linked_circuit set next_q2 = second.next_q1 where id = first_prev_q1_id;
            end if;

            if mod(div(first.prev_q2, 100), 10) = 0 then
                update linked_circuit set next_q1 = second.next_q2 where id = first_prev_q2_id;
            else
                update linked_circuit set next_q2 = second.next_q2 where id = first_prev_q2_id;
            end if;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = first.prev_q1 where id = second_next_q1_id;
            else
                update linked_circuit set prev_q2 = first.prev_q1 where id = second_next_q1_id;
            end if;

            if mod(div(second.next_q2, 100), 10) = 0 then
                update linked_circuit set prev_q1 = first.prev_q2 where id = second_next_q2_id;
            else
                update linked_circuit set prev_q2 = first.prev_q2 where id = second_next_q2_id;
            end if;

            delete from linked_circuit lc where lc.id in (first.id, second.id);

            commit; -- release locks after applying template

            if extract(epoch from (clock_timestamp() - start_time)) > timeout then
                exit;
            end if;

        end loop; -- end gate loop

--         if extract(epoch from (clock_timestamp() - start_time)) > timeout then
--             exit;
--         end if;

        pass_count = pass_count - 1;

	end loop; --end pass loop

end;$$;

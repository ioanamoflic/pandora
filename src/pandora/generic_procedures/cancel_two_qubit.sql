create or replace procedure cancel_two_qubit(type_1 int, type_2 int, param_1 float, param_2 float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    distinct_count int;
    distinct_existing int;

    first record;
    second record;
    gate record;

    first_id_plus_one bigint;
    first_id_plus_zero bigint;
	first_prev_q1_id bigint;
	first_prev_q2_id bigint;
    second_next_q1_id bigint;
	second_next_q2_id bigint;

    pattern_count int;

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
            select * into first from linked_circuit where id = gate.id;

            select count(*) into pattern_count from (select * from linked_circuit
                                                     where id in (first.id, div(first.next_q1, 1000))
                                                     for update skip locked
                                                     ) as it;
            if pattern_count != 2 then
                commit;
                continue;
            end if;

            select * into second from linked_circuit where id = div(first.next_q1, 1000);

            if first.id is null or second.id is null or second.param != param_2 or second.type != type_2
--                 or second.switch != first.switch
                then
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

            select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1_id, first_prev_q2_id, second_next_q1_id, second_next_q2_id])) as it;
            select count(*) into distinct_existing from
            (select * from linked_circuit where id in (first_prev_q1_id, first_prev_q2_id, second_next_q1_id, second_next_q2_id) for update skip locked) as it;

            if distinct_count != distinct_existing then
                commit; -- release lock
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

        end loop; -- end gate loop

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

	end loop; --end pass loop

end;$$;

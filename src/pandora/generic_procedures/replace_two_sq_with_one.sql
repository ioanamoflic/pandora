-- does not include the replacement of global_phase
create or replace procedure fuse_single_qubit(type_1 int, type_2 int, type_replace int, param1 float, param2 float, param_replace float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    second_next_id bigint;
    first_prev_id bigint;

    first record;
    second record;
    gate record;

    distinct_count bigint;
    distinct_existing bigint;
    new_next bigint;

    pattern_count int;

    start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

	 while pass_count > 0 loop

        for gate in
            select * from linked_circuit --tablesample bernoulli(10)
            where id % nprocs = my_proc_id
            and type=type_1
            and mod(next_q1, 100) = type_2
            and param=param1
        loop
            select * into first from linked_circuit where id = gate.id;
            if first.id is null then
                continue;
            end if;

            select count(*) into pattern_count from (select * from linked_circuit
                                                     where id in (first.id, div(first.next_q1, 1000))
                                                     for update skip locked
                                                     ) as it;
            if pattern_count != 2 then
                commit;
                continue;
            end if;

			select * into second from linked_circuit where id = div(first.next_q1, 1000);

			if first.id is null or second.id is null or second.param != param2 or second.type != type_2 or
			       div(second.prev_q1, 1000) != first.id then
			    commit;
			    continue;
			end if;

            second_next_id := div(second.next_q1, 1000);
            first_prev_id := div(first.prev_q1, 1000);

            select count(*) into distinct_count from (select distinct unnest(array[first_prev_id, second_next_id])) as it;
            select count(*) into distinct_existing from (select id from linked_circuit where id in (first_prev_id, second_next_id)
                                                                                       for update skip locked) as it;
            if distinct_count != distinct_existing then
               commit;
               continue;
            end if;

            new_next := (first.id * 10) * 100 + first.type;

            update linked_circuit set (type, next_q1, param) = (type_replace, second.next_q1, param_replace) where id = first.id;
--             select param from linked_circuit where id = first.id;

            if mod(div(second.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = new_next where id = second_next_id;
            else
                update linked_circuit set prev_q2 = new_next where id = second_next_id;
            end if;

            delete from linked_circuit where id = second.id;

            commit;

        end loop; -- end gate loop

        pass_count = pass_count - 1;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

     end loop; -- end pass loop
end;$$;

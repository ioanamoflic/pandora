create or replace procedure cancel_single_qubit(type_1 int, type_2 int, param_1 float, param_2 float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    first_next_id bigint;
    first_prev_id bigint;
    second_next_id bigint;

    first record;
    second record;
    distinct_count int;
    distinct_existing int;

	start_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

	 while pass_count > 0 loop

        for first in
                select * from linked_circuit
                         where
                           id % nprocs = my_proc_id
                           and type = type_1
                           and param = param_1
                           and mod(next_q1, 100) = type_2
        loop
            if first.id is not null then
                first_next_id :=  div(first.next_q1, 1000);
                select * into second from linked_circuit where id = first_next_id;

                if second.id is not null and second.param=param_2 then
                     first_prev_id := div(first.prev_q1, 1000);
                     second_next_id := div(second.next_q1, 1000);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_id, second_next_id])) as it;
                    select count(*) into distinct_existing from (select * from linked_circuit
                                                                          where id in (first_prev_id, second_next_id)
                                                                          for update skip locked) as it;
                    -- Lock the two neighbours
                    if distinct_count != distinct_existing then
                        commit;
                        continue;
                    end if;

                    -- Lock the two gates
                    select count(*) into distinct_count from (select * from linked_circuit where id in (first.id, second.id)
                                                                                           for update skip locked) as it;
                    if distinct_count != 2 then
                        commit;
                        continue;
                    end if;

                    if mod(div(first.prev_q1, 100), 10) = 0 then
                        update linked_circuit set next_q1 = second.next_q1 where id = first_prev_id;
                    else
                        update linked_circuit set next_q2 = second.next_q1 where id = first_prev_id;
                    end if;

                    if mod(div(second.next_q1, 100), 10) = 0 then
                        update linked_circuit set prev_q1 = first.prev_q1 where id = second_next_id;
                    else
                        update linked_circuit set prev_q2 = first.prev_q1 where id = second_next_id;
                    end if;

                    delete from linked_circuit where id in (first.id, second.id);

                    commit; -- release the locks

                end if;

            end if; -- end first gate is pattern

        end loop; -- end gate loop

	    pass_count = pass_count - 1;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

    end loop; -- end pass loop
end;$$;

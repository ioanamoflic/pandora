create or replace procedure cancel_two_qubit_equiv(type_1 int, type_2 int, my_proc_id int, proc_count int, pass_count int, OUT elapsed_time INTERVAL)
    language plpgsql
as
$$
declare
    distinct_count int;
    distinct_existing int;

    first record;
    second record;
    compare record;
    gate record;

    first_id_plus_one bigint;
    first_id_plus_zero bigint;
	first_prev_q1_id bigint;
	first_prev_q2_id bigint;
    second_next_q1_id bigint;
	second_next_q2_id bigint;

    remaining_cnot_count bigint;

    start_time timestamp;
	end_time timestamp;

begin
    start_time := CLOCK_TIMESTAMP();

	while pass_count > 0 loop

        for gate in
            -- we sample from the table to make multithreading work by not having threads waiting on each other
            select * from linked_circuit
                     where
                     id % proc_count = my_proc_id and
                     type=type_1
                     and div(next_q1, 1000) = div(next_q2, 1000) -- two gates sharing the same wires
        loop
            select * into first from linked_circuit where id = gate.id for update skip locked;

            if first.id is not null then
                first_id_plus_one := (first.id * 10 + 1) * 100 + first.type;
                first_id_plus_zero := (first.id * 10) * 100 + first.type;

                select * into second from linked_circuit
                                     where prev_q1 = first_id_plus_zero
                                         and prev_q2 = first_id_plus_one
                                         and switch = first.switch
                                     for update skip locked;

                compare := second;

                if compare.id is null or compare.type != type_2 then
                    -- LOOK BACKWARD (second, first)
                    -- first becomes second
                    second := first;
                    -- select a different first from the database - LOOK BACKWARD
                    select * into first from linked_circuit
                                        where next_q1 = first_id_plus_zero
                                            and next_q2 = first_id_plus_one
                                            and switch = first.switch
                                        for update skip locked;

                    compare := first;
                end if;

                if compare.id is not null and compare.type=type_2 then
                    -- LOOK FORWARD (first, second)
                    first_prev_q1_id := div(first.prev_q1, 1000);
                    first_prev_q2_id := div(first.prev_q2, 1000);
                    second_next_q1_id := div(second.next_q1, 1000);
                    second_next_q2_id := div(second.next_q2, 1000);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1_id, first_prev_q2_id, second_next_q1_id, second_next_q2_id])) as it;
                    select count(*) into distinct_existing from
                    (select * from linked_circuit where id in (first_prev_q1_id, first_prev_q2_id, second_next_q1_id, second_next_q2_id) for update skip locked) as it;

                    -- Check that the number of locked neighbours is equal to the number of neighbours
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
                end if;
            else
                --
                -- finish this pass if we didn't find any cancellation
                --
                exit;
                commit; -- release lock
            end if;

        end loop; -- end gate loop

        commit; -- release lock

--         select count(*) into remaining_cnot_count from linked_circuit where type > 2;
--         if remaining_cnot_count = 0 then
--             pass_count = 0;
--         else
--             pass_count := pass_count - 1;
--         end if;

	    pass_count := pass_count - 1;

	end loop; --end pass loop

    -- Capture end time
    end_time := CLOCK_TIMESTAMP();
    -- Calculate and return elapsed time
    elapsed_time := end_time - start_time;

end;$$;

create or replace procedure cancel_two_qubit_equiv(type_1 int, type_2 int, my_proc_id int, proc_count int, qubit_count int, timeout int)
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

    found_match boolean;
    mismatch_count int;

    remaining_gate_count bigint;
    start_time timestamp with time zone;

begin
    start_time := clock_timestamp();
    mismatch_count := 0;

    select count(id) into remaining_gate_count from linked_circuit;

	while remaining_gate_count > 2 * qubit_count loop

        found_match := false;

        if mismatch_count >= 10000 then
            exit;
        end if;

        for gate in
            -- we sample from the table to make multithreading work by not having threads waiting on each other
            select * from linked_circuit
                     where
                     id % proc_count = my_proc_id
                     and type=type_1
                     and div(next_q1, 1000) = div(next_q2, 1000) -- two gates sharing the same wires
        loop
            select * into first from linked_circuit where id = gate.id; -- for update skip locked;

            if first.id is not null then
                first_id_plus_one := (first.id * 10 + 1) * 100 + first.type;
                first_id_plus_zero := (first.id * 10) * 100 + first.type;

                select * into second from linked_circuit
                                     where prev_q1 = first_id_plus_zero
                                     and prev_q2 = first_id_plus_one
                                     and switch = first.switch;

                if second.id is not null and second.type=type_2 then
                    -- LOOK FORWARD (first, second)
                    first_prev_q1_id := div(first.prev_q1, 1000);
                    first_prev_q2_id := div(first.prev_q2, 1000);
                    second_next_q1_id := div(second.next_q1, 1000);
                    second_next_q2_id := div(second.next_q2, 1000);

                    select count(*) into distinct_count from (select distinct unnest(array[first_prev_q1_id, first_prev_q2_id, first.id, second.id, second_next_q1_id, second_next_q2_id])) as it;
                    select count(*) into distinct_existing from
                    (select * from linked_circuit where id in (first_prev_q1_id, first_prev_q2_id, first.id, second.id, second_next_q1_id, second_next_q2_id) for update skip locked) as it;

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

                    commit; -- release locks after applying template

                    found_match = True;

                end if; -- end second gate is match

            end if; -- end first gate is match

        end loop; -- end gate loop

        if found_match is False then
            mismatch_count := mismatch_count + 1;
        end if;

	    select count(id) into remaining_gate_count from linked_circuit;

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

	end loop; --end pass loop

end;$$;

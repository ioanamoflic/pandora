create or replace procedure linked_hhcxhh_to_cx_parallel(my_proc_id int, nprocs int, max_rewrite_count int, pass_count int, OUT elapsed_time INTERVAL)
    language plpgsql
as
$$
declare
    distinct_count int;
    distinct_existing int;
    total_rewrite_count int;
    visited_count int;

    cx record;
    gate record;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_q1 record;
    left_q2 record;
    right_q1 record;
    right_q2 record;
    cx_id_ctrl bigint;
    cx_id_tgt bigint;
    left_q1_id bigint;
	left_q2_id bigint;
	right_q1_id bigint;
	right_q2_id bigint;

	start_time timestamp;
	end_time timestamp;
begin
    start_time := CLOCK_TIMESTAMP();

    while pass_count > 0 loop

        total_rewrite_count := 0;

        while total_rewrite_count < max_rewrite_count loop
            for gate in
                select * from linked_circuit
                         where
                             id % nprocs = my_proc_id and
                             type = 18
                           and prev_q1 % 100 = 8 and prev_q2 % 100 = 8
                           and next_q1 % 100 = 8 and next_q2 % 100 = 8
            loop
                if gate.id is null then
                    continue;
                end if;

                select * into cx from linked_circuit where id = gate.id;

                -- Compute the Hadamard IDs
                cx_prev_q1_id := div(cx.prev_q1, 1000);
                cx_prev_q2_id := div(cx.prev_q2, 1000);
                cx_next_q1_id := div(cx.next_q1, 1000);
                cx_next_q2_id := div(cx.next_q2, 1000);

                -- Select the Hadamards
                select * into left_q1 from linked_circuit where id=cx_prev_q1_id;
                select * into left_q2 from linked_circuit where id=cx_prev_q2_id;
                select * into right_q1 from linked_circuit where id=cx_next_q1_id;
                select * into right_q2 from linked_circuit where id=cx_next_q2_id;

                -- Compute the IDs of the Hadamard neighbours
                left_q1_id := div(left_q1.prev_q1, 1000);
                left_q2_id := div(left_q2.prev_q1, 1000);
                right_q1_id := div(right_q1.next_q1, 1000);
                right_q2_id := div(right_q2.next_q1, 1000);

                -- How many neighbours are there?
                select count(*) into distinct_count from (select distinct unnest(array[left_q1_id, left_q2_id, right_q1_id, right_q2_id])) as it;

                -- Lock the neighbours
                select count(*) into distinct_existing from
                                                               (select * from linked_circuit where id in (left_q1_id, left_q2_id, right_q1_id, right_q2_id) for update skip locked) as it;

                -- Check that the number of locked neighbours is equal to the number of neighbours
                if distinct_count != distinct_existing then
                    continue;
                end if;

                -- Lock the Hadamards and CX
                select count(*) into distinct_count from (select * from linked_circuit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id, cx.id) for update skip locked) as it;
                if distinct_count != 5 then
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

            end loop; -- end gate loop

            commit; -- release the cx

            select count(*) into total_rewrite_count from linked_circuit where visited != -1;

        end loop; -- end rewrite count loop

        pass_count = pass_count - 1;

    end loop; --end pass loop
    --
    -- check that the number of rewrites equals the number of visited
    --
    select count(*) into visited_count from linked_circuit where visited != -1;
    if visited_count != max_rewrite_count then
        raise exception 'Needed % != Visited %', max_rewrite_count, visited_count;
    end if;

    -- Capture end time
    end_time := CLOCK_TIMESTAMP();
    -- Calculate and return elapsed time
    elapsed_time := end_time - start_time;

end;$$;



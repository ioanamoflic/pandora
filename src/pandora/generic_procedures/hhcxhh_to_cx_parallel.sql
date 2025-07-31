create or replace procedure linked_hhcxhh_to_cx_parallel(my_proc_id int, sys_range int, max_rewrite_count int, pass_count int)
    language plpgsql
as
$$
declare
    gate record;
    distinct_count int;
    distinct_existing int;
    total_rewrite_count int;
    visited_count int;

    cx record;
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
begin

    while pass_count > 0 loop

        total_rewrite_count := 0;

        while total_rewrite_count < max_rewrite_count loop

            for cx in
                select * from linked_circuit --tablesample bernoulli(10)--bernoulli(100 / sys_range)
                         where
                             id % sys_range = my_proc_id and
                             type in (15, 18)
                           and prev_q1 % 100 = 8 and prev_q2 % 100 = 8
                           and next_q1 % 100 = 8 and next_q2 % 100 = 8
--                          order by random()
--                         for update skip locked
            loop
                -- left gates on qubits 1,2
                -- Compute the Hadamard IDs
                cx_prev_q1_id := div(cx.prev_q1, 1000);
                cx_prev_q2_id := div(cx.prev_q2, 1000);
                cx_next_q1_id := div(cx.next_q1, 1000);
                cx_next_q2_id := div(cx.next_q2, 1000);

                -- Select the Hadamards
                select * into left_q1 from linked_circuit where id=cx_prev_q1_id; --for update skip locked;
                select * into left_q2 from linked_circuit where id=cx_prev_q2_id; --for update skip locked;
                select * into right_q1 from linked_circuit where id=cx_next_q1_id; --for update skip locked;
                select * into right_q2 from linked_circuit where id=cx_next_q2_id; --for update skip locked;

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
--                     commit;
                    continue;
                end if;

                -- Lock the Hadamards and CX
                select count(*) into distinct_count from (select * from linked_circuit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id, cx.id) for update skip locked) as it;
                if distinct_count != 5 then
--                     commit;
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

                commit; -- release the cx?
            end loop; -- end gate loop

--             commit;
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

end;$$;



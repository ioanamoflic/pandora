create or replace procedure commute_single_control_right(single_type int, parameter float, my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    two_qubit_gate record;
    sg record;

    distinct_count int;
    distinct_existing int;

    cx_next_q1 bigint;
    sg_next_id bigint;
    cx_next_id bigint;
    cx_prev_id bigint;
    cx_prev_q1 bigint;

    new_next_for_sq bigint;
    new_prev_for_sq bigint;

    start_time timestamp with time zone;

begin
    start_time := clock_timestamp();

	while pass_count > 0 loop

        for two_qubit_gate in
            select * from linked_circuit
                     where
                     id % nprocs = my_proc_id
                     and type in (15, 16, 17, 18)
                     and mod(next_q1, 100) = single_type
        loop

            if two_qubit_gate.id is not null then
                cx_next_q1 = two_qubit_gate.next_q1;
                cx_prev_q1 = two_qubit_gate.prev_q1;

                cx_prev_id = div(two_qubit_gate.prev_q1, 1000);
                cx_next_id := div(two_qubit_gate.next_q1, 1000);

                select * into sg from linked_circuit where id = cx_next_id;

                if sg.id is not null and sg.param=parameter then
                     sg_next_id := div(sg.next_q1, 10);
                    select count(*) into distinct_count from (select distinct unnest(array[two_qubit_gate.id, sg_next_id, cx_next_id])) as it;
                    select count(*) into distinct_existing from (select * from linked_circuit where id in (two_qubit_gate.id, sg_next_id, cx_next_id)
                                                                                              for update skip locked) as it;

                    if distinct_count = distinct_existing then
                        commit;
                        continue;
                    end if;

                    new_next_for_sq := (two_qubit_gate.id * 10) * 100 + two_qubit_gate.type;
                    new_prev_for_sq := (sg.id * 10) * 100 + sg.type;

                    if mod(div(two_qubit_gate.prev_q1, 100), 10) = 0 then
                        update linked_circuit set next_q1 = new_prev_for_sq where id = cx_prev_id;
                    else
                        update linked_circuit set next_q2 = new_prev_for_sq where id = cx_prev_id;
                    end if;

                    if mod(div(sg.next_q1, 100), 10) = 0 then
                        update linked_circuit set prev_q1 = new_next_for_sq where id = sg_next_id;
                    else
                        update linked_circuit set prev_q2 = new_next_for_sq where id = sg_next_id;
                    end if;

                    update linked_circuit set (next_q1, prev_q1, visited) = (sg.next_q1, new_prev_for_sq, my_proc_id)
                                          where id = two_qubit_gate.id;
                    update linked_circuit set (next_q1, prev_q1) = (new_next_for_sq, cx_prev_q1) where id = sg.id;

                    commit; -- release locks

                end if; -- end second gate match

            end if; -- end first gate match

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop

-- 	while run_nr > 0 loop
-- 	    select st.stop into stop from stop_condition as st limit 1;
-- 	    if stop=True then
--             exit;
--         end if;
--
--     	select * into cx from (
--     	select * from linked_circuit lc tablesample system_rows(sys_range)) as it
--     	                 where it.type in (15, 16, 17, 18) for update skip locked limit 1;
--     	if cx.id is not null then
--     	    cx_next_q1 = cx.next_q1;
--     	    cx_prev_q1 = cx.prev_q1;
--     	    cx_prev_id = div(cx.prev_q1, 10);
--     	    cx_next_id := div(cx.next_q1, 10);
--             select * into sg from linked_circuit where id = cx_next_id for update skip locked;
--
--     	    if sg.id is not null and sg.type = single_type and sg.param=parameter then
--     	        sg_next_id := div(sg.next_q1, 10);
--     	        select count(*) into distinct_count from (select distinct unnest(array[sg_next_id, cx_next_id])) as it;
-- 			    select count(*) into distinct_existing from (select * from linked_circuit where id in (sg_next_id, cx_next_id) for update skip locked) as it;
--
--     	        if distinct_count = distinct_existing then
--     	            modulus_prev := 'next_q' || mod(cx.prev_q1, 10) + 1;
-- 			        modulus_next := 'prev_q' || mod(sg.next_q1, 10) + 1;
--
--                     execute 'update linked_circuit set ' || modulus_prev || ' = $1 where id = $2' using sg.id * 10, cx_prev_id;
-- 			        execute 'update linked_circuit set ' || modulus_next || ' = $1 where id = $2' using cx.id * 10, sg_next_id;
--
--                     update linked_circuit set (next_q1, prev_q1, visited) = (sg.next_q1, sg.id * 10, true) where id = cx.id;
--                     update linked_circuit set (next_q1, prev_q1) = (cx.id * 10, cx_prev_q1) where id = sg.id;
--                 end if;
--     	        run_nr = run_nr - 1;
-- 			end if;
--     	    commit;
-- 		end if;
-- 	end loop;
end;$$;

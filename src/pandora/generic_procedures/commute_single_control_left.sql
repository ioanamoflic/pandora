create or replace procedure commute_single_control_left(single_type int, parameter float, my_proc_id int, nprocs int, pass_count int, timeout int)
   language plpgsql
as
$$
declare
    two_qubit_gate record;
    sg record;
    gate record;

    distinct_count int;
    distinct_existing int;

    cx_next_q1 bigint;
    cx_prev_q1 bigint;
    sg_prev_id bigint;

    cx_next_q1_id bigint;
    cx_next_q2_id bigint;
    cx_prev_q2_id bigint;

    new_next_for_sq bigint;
    new_prev_for_sq bigint;

    pattern_count int;

    start_time timestamp with time zone;
begin

    start_time := clock_timestamp();

	while pass_count > 0 loop

        for gate in
            select * from linked_circuit --tablesample bernoulli(10)
                     where
                     id % nprocs = my_proc_id
                     and type in (15, 16, 17, 18)
                     and mod(prev_q1, 100) = single_type
        loop
            select * into two_qubit_gate from linked_circuit where id = gate.id;

            select count(*) into pattern_count from (select * from linked_circuit
                                                     where id in (div(two_qubit_gate.prev_q1, 1000), two_qubit_gate.id)
                                                     for update skip locked
                                                     ) as it;
            if pattern_count != 2 then
                commit;
                continue;
            end if;

            select * into sg from linked_circuit where id = div(two_qubit_gate.prev_q1, 1000);

            if two_qubit_gate.id is null or sg.id is null or sg.param != parameter or sg.type != single_type
                or div(sg.next_q1, 1000) != two_qubit_gate.id then
                commit;
                continue;
            end if;

            cx_next_q1_id := div(two_qubit_gate.next_q1, 1000);
--             cx_next_q2_id := div(two_qubit_gate.next_q2, 1000);
--             cx_prev_q2_id := div(two_qubit_gate.prev_q2, 1000);

            sg_prev_id := div(sg.prev_q1, 1000);

            select count(*) into distinct_count from (select distinct unnest(array[sg_prev_id, cx_next_q1_id
--                 ,cx_next_q2_id, cx_prev_q2_id
                ]
                )) as it;
            select count(*) into distinct_existing from (select * from linked_circuit where id in (sg_prev_id, cx_next_q1_id
--                 cx_next_q2_id, cx_prev_q2_id

                ) for update skip locked) as it;

            if distinct_count != distinct_existing then
                commit;
                continue;
            end if;

            cx_next_q1 = two_qubit_gate.next_q1;
            cx_prev_q1 = two_qubit_gate.prev_q1;

            new_next_for_sq := (two_qubit_gate.id * 10) * 100 + two_qubit_gate.type;
            new_prev_for_sq := (sg.id * 10) * 100 + sg.type;

            if mod(div(sg.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = new_next_for_sq where id = sg_prev_id;
            else
                update linked_circuit set next_q2 = new_next_for_sq where id = sg_prev_id;
            end if;

            if mod(div(two_qubit_gate.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = new_prev_for_sq where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = new_prev_for_sq where id = cx_next_q1_id;
            end if;

            update linked_circuit set (next_q1, prev_q1, visited) = (new_prev_for_sq, sg.prev_q1, my_proc_id) where id = two_qubit_gate.id;
            update linked_circuit set (next_q1, prev_q1) = (cx_next_q1, new_next_for_sq) where id = sg.id;

            commit; -- release locks

        end loop; -- end gate loop

	    if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop

end;$$;

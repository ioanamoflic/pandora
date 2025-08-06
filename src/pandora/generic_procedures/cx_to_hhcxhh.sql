create or replace procedure linked_cx_to_hhcxhh(my_proc_id int, nprocs int, pass_count int, timeout int)
    language plpgsql
as
$$
declare
    cx record;
    gate record;

    distinct_count int;
    distinct_existing int;

    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    left_h_q1_id bigint;
	left_h_q2_id bigint;
	right_h_q1_id bigint;
	right_h_q2_id bigint;

    -- used for computing the links
    port_nr bigint;
    gate_type bigint;

    -- the links to the right and left
    left_q1_link bigint;
    left_q2_link bigint;
    right_q1_link bigint;
    right_q2_link bigint;


    cx_id_ctrl bigint;
    cx_id_tgt bigint;

    start_time timestamp;

begin
    port_nr := 0; -- single qubit gate has a single port with index 0
    gate_type := 8; -- Hadamard

    start_time := CLOCK_TIMESTAMP();

    while pass_count > 0 loop
        for gate in
            select id from linked_circuit --tablesample bernoulli(10)
                     where id % nprocs = my_proc_id
                     and type in (15, 18)
        loop
            select * into cx from linked_circuit where id = gate.id for update skip locked;

            if cx.id is null then
                commit;
                continue;
            end if;

            select count(*) into distinct_count from
                (select distinct unnest(array[cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id])) as it;
            select count(*) into distinct_existing from
                (select * from linked_circuit where id in
                    (cx_prev_q1_id, cx_prev_q2_id, cx_next_q1_id, cx_next_q2_id) for update skip locked) as it;


            cx_prev_q1_id := div(cx.prev_q1, 1000);
            cx_prev_q2_id := div(cx.prev_q2, 1000);
            cx_next_q1_id := div(cx.next_q1, 1000);
            cx_next_q2_id := div(cx.next_q2, 1000);

            -- Lock the 4 neighbours
            if distinct_count != distinct_existing then
                commit;
                continue;
            end if;

            cx_id_ctrl := (cx.id * 10 + 0) * 100 + cx.type;
            cx_id_tgt  := (cx.id * 10 + 1) * 100 + cx.type;

            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (cx.prev_q1, gate_type, 1, cx_id_tgt, my_proc_id, cx.label)
                                                          returning id into left_h_q1_id;
            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (cx.prev_q2, gate_type, 1, cx_id_ctrl, my_proc_id, cx.label)
                                                          returning id into left_h_q2_id;
            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (cx_id_tgt, gate_type, 1, cx.next_q1, my_proc_id, cx.label)
                                                          returning id into right_h_q1_id;
            insert into linked_circuit(prev_q1, type, param, next_q1, visited, label) values (cx_id_ctrl, gate_type, 1, cx.next_q2,my_proc_id, cx.label)
                                                          returning id into right_h_q2_id;

            -- These are the links that the margins and CNOT should use
            left_q1_link := left_h_q1_id * 1000 + port_nr * 100 + gate_type;
            left_q2_link := left_h_q2_id * 1000 + port_nr * 100 + gate_type;
            right_q1_link := right_h_q1_id * 1000 + port_nr * 100 + gate_type;
            right_q2_link := right_h_q2_id * 1000 + port_nr * 100 + gate_type;

            -- Update the CNOT: flip the switch value and set visited
            update linked_circuit set (prev_q1, prev_q2, next_q1, next_q2, switch, visited) = (left_q2_link, left_q1_link, right_q2_link, right_q1_link, not cx.switch, my_proc_id) where id = cx.id;

            if mod(div(cx.prev_q1, 100), 10) = 0 then
                update linked_circuit set next_q1 = left_q1_link where id = cx_prev_q1_id;
            else
                update linked_circuit set next_q2 = left_q1_link where id = cx_prev_q1_id;
            end if;

            if mod(div(cx.prev_q2, 100), 10) = 0 then
                update linked_circuit set next_q1 = left_q2_link where id = cx_prev_q2_id;
            else
                update linked_circuit set next_q2 = left_q2_link where id = cx_prev_q2_id;
            end if;

            if mod(div(cx.next_q1, 100), 10) = 0 then
                update linked_circuit set prev_q1 = right_q1_link where id = cx_next_q1_id;
            else
                update linked_circuit set prev_q2 = right_q1_link where id = cx_next_q1_id;
            end if;

            if mod(div(cx.next_q2, 100), 10) = 0 then
                update linked_circuit set prev_q1 = right_q2_link where id = cx_next_q2_id;
            else
                update linked_circuit set prev_q2 = right_q2_link where id = cx_next_q2_id;
            end if;

            commit; -- release locks

        end loop; -- end gate loop

        if extract(epoch from (clock_timestamp() - start_time)) > timeout then
            exit;
        end if;

        pass_count = pass_count - 1;

    end loop; -- end pass loop
end;$$;


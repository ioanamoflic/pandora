create or replace procedure linked_hhcxhh_to_cx(sys_range int, run_nr int)
    language plpgsql
as
$$
declare
    cx record;
    cx_prev_q1_id bigint;
	cx_prev_q2_id bigint;
	cx_next_q1_id bigint;
	cx_next_q2_id bigint;
    modulus_left_h_q1 varchar(8);
    modulus_left_h_q2 varchar(8);
	modulus_right_h_q1 varchar(8);
	modulus_right_h_q2 varchar(8);
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
	start_time timestamptz;
    distinct_count int;
    distinct_existing int;
    stop boolean;
begin
    start_time := clock_timestamp();
    while run_nr > 0 loop
        select st.stop into stop from stop_condition as st limit 1;
	    if stop=True then
            exit;
        end if;
        select * into cx from (select * from linked_circuit_qubit lc tablesample system_rows(sys_range)) as it where type = 'CXPowGate' for update skip locked limit 1;
        if cx.id is not null then
            -- left gates on qubits 1,2
            cx_prev_q1_id := div(cx.prev_q1, 10);
            cx_prev_q2_id := div(cx.prev_q2, 10);
            cx_next_q1_id := div(cx.next_q1, 10);
            cx_next_q2_id := div(cx.next_q2, 10);

            select * into left_q1 from linked_circuit_qubit where id=cx_prev_q1_id for update skip locked;
            select * into left_q2 from linked_circuit_qubit where id=cx_prev_q2_id for update skip locked;
            select * into right_q1 from linked_circuit_qubit where id=cx_next_q1_id for update skip locked;
            select * into right_q2 from linked_circuit_qubit where id=cx_next_q2_id for update skip locked;

            left_q1_id := div(left_q1.prev_q1, 10);
            left_q2_id := div(left_q2.prev_q1, 10);
            right_q1_id := div(right_q1.next_q1, 10);
            right_q2_id := div(right_q2.next_q1, 10);

            select count(*) into distinct_count from (select distinct unnest(array[left_q1_id, left_q2_id, right_q1_id, right_q2_id])) as it;
            select count(*) into distinct_existing from
                                                           (select * from linked_circuit_qubit where id in (left_q1_id, left_q2_id, right_q1_id, right_q2_id) for update skip locked) as it;

            if distinct_count = distinct_existing then
                if left_q1.type = 'HPowGate' and left_q2.type = 'HPowGate' and right_q1.type = 'HPowGate' and right_q2.type = 'HPowGate' then
                    cx_id_ctrl := cx.id * 10;
                    cx_id_tgt := cx.id * 10 + 1;
                    modulus_left_h_q1 := 'next_q' || mod(left_q1.prev_q1, 10) + 1;
                    modulus_left_h_q2 := 'next_q' || mod(left_q2.prev_q1, 10) + 1;
                    modulus_right_h_q1 := 'prev_q' || mod(right_q1.next_q1, 10) + 1;
                    modulus_right_h_q2 := 'prev_q' || mod(right_q2.next_q1, 10) + 1;

                    execute 'update linked_circuit_qubit set ' || modulus_left_h_q1 || ' = $1 where id = $2' using cx_id_tgt, left_q1_id;
                    execute 'update linked_circuit_qubit set ' || modulus_left_h_q2 || ' = $1 where id = $2' using cx_id_ctrl, left_q2_id;
                    execute 'update linked_circuit_qubit set ' || modulus_right_h_q1 || ' = $1 where id = $2' using cx_id_tgt, right_q1_id;
                    execute 'update linked_circuit_qubit set ' || modulus_right_h_q2 || ' = $1 where id = $2' using cx_id_ctrl, right_q2_id;

                    -- make sure to update the links for the cx
                    update linked_circuit_qubit set (qub_1, qub_2, switch, prev_q1, prev_q2, next_q1, next_q2, visited)
                                = (cx.qub_2, cx.qub_1, not cx.switch, left_q2.prev_q1, left_q1.prev_q1, right_q2.next_q1, right_q1.next_q1, false) where id = cx.id;

                    delete from linked_circuit_qubit where id in (left_q1.id, left_q2.id, right_q1.id, right_q2.id);
                    run_nr = run_nr - 1;
                end if;
            end if;
            commit;
        end if;
    end loop;
    raise notice 'Time spent for all hhcxhh -> cx =%', clock_timestamp() - start_time;
end;$$;

